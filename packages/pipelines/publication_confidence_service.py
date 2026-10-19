"""Publication confidence computation service.

Computes PublicationConfidenceSnapshot objects from lineage, source freshness,
and landing validation state, then stores them in the control plane.

Inputs per publication:

- **Contributing sources** come from source lineage targeting the publication
  key, keyed by the source asset each contributing run was landed for. The
  asset is read from the landing-layer lineage row that promotion records for
  the run (``target_kind="source_asset"``), so it matches the
  ``source_asset_id`` that source-freshness configs are keyed by. A run with
  no recorded asset falls back to the source the lineage row declares
  (``source_system``), else to the run's ``source_name`` from run metadata;
  such a fallback source is never matched against freshness configs and
  reads as unconfigured. The latest run per source is the contributing run.
- **Validation** reads the landing validation outcome recorded in run
  metadata for each contributing run, plus any landing attempt for the same
  source and dataset that was rejected after the contributing run and before
  ``as_of`` (newer data that failed validation). For an asset-attributed
  run, any rejected landing of the same dataset counts: a rejected run never
  reaches promotion, so it has no lineage naming its asset, and the free-text
  ``source_name`` of an upload is not a reliable stand-in for it.
- **Completeness** is the share of contributing sources whose contributing
  run is verifiably present: found in run metadata, passed validation and
  landed at least one row (and loaded at least one row when lineage records
  a row count).
- **Freshness** evaluates each configured source's contributing run against
  its freshness config. Runs record no coverage period, so for a scheduled
  (weekly/monthly/quarterly/annual) config the period the run covers is
  derived from its landing date with ``run_observation``, the same helper
  ``/control/source-freshness`` and ``/sources`` use. A scheduled source
  whose contributing run landed its expected period reads ``current``.

When run metadata is not available for a run, the validation and
completeness signals record it as unknown in ``quality_flags`` rather than
assuming a clean result; unknown inputs never upgrade the verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

from packages.platform.publication_confidence import (
    COMPLETENESS_COVERED_SOURCES_FLAG,
    COMPLETENESS_EXPECTED_SOURCES_FLAG,
    COMPLETENESS_UNKNOWN_SOURCES_FLAG,
    FRESHNESS_UNCONFIGURED_SOURCES_FLAG,
    REJECTED_RUNS_FLAG,
    VALIDATION_ERRORS_FLAG,
    VALIDATION_UNKNOWN_RUNS_FLAG,
    PublicationConfidenceSnapshot,
    SourceFreshnessSnapshot,
    compute_publication_freshness_state,
)
from packages.platform.source_freshness import (
    SourceFreshnessState,
    evaluate_source_freshness,
    run_observation,
)
from packages.storage.control_plane import PublicationConfidenceSnapshotCreate

if TYPE_CHECKING:
    from packages.platform.publication_keys import PublicationKeyResolver
    from packages.storage.control_plane import ControlPlaneStore
    from packages.storage.run_metadata import IngestionRunRecord

_FAILED_RUN_STATUSES = frozenset({"rejected", "failed"})


class _RunLookup(Protocol):
    def get_run(self, run_id: str) -> IngestionRunRecord: ...


_SOURCE_ASSET_TARGET_KIND = "source_asset"


@dataclass
class _ContributingSource:
    source_key: str
    run_id: str
    lineage_row_count: int | None
    declared: bool  # source named by lineage.source_system (vs resolved from run)
    source_asset_id: str | None = None  # asset the run was landed for, if recorded


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _status_value(status: Any) -> str:
    return str(getattr(status, "value", status)).lower()


class _RunResolver:
    """Cached run-metadata lookup; returns None when a run cannot be resolved."""

    def __init__(self, lookup: _RunLookup | None) -> None:
        self._lookup = lookup
        self._cache: dict[str, IngestionRunRecord | None] = {}

    @property
    def available(self) -> bool:
        return self._lookup is not None

    def get(self, run_id: str) -> IngestionRunRecord | None:
        if self._lookup is None:
            return None
        if run_id not in self._cache:
            try:
                self._cache[run_id] = self._lookup.get_run(run_id)
            except (KeyError, AttributeError, LookupError):
                self._cache[run_id] = None
        return self._cache[run_id]

    def later_failed_runs(
        self,
        run: IngestionRunRecord,
        *,
        as_of: datetime,
        match_source_name: bool = True,
    ) -> list[IngestionRunRecord]:
        """Rejected/failed landings of the same dataset after ``run``.

        With ``match_source_name`` (sources not attributed to an asset) the
        landing must also share the run's ``source_name``.
        """
        list_runs = getattr(self._lookup, "list_runs", None)
        if list_runs is None:
            return []
        run_created = _as_utc(run.created_at)
        as_of_utc = _as_utc(as_of)
        try:
            candidates = list_runs(dataset_name=run.dataset_name, from_date=run_created)
        except (TypeError, AttributeError):
            return []
        return [
            candidate
            for candidate in candidates
            if candidate.run_id != run.run_id
            and (not match_source_name or candidate.source_name == run.source_name)
            and _status_value(candidate.status) in _FAILED_RUN_STATUSES
            and run_created < _as_utc(candidate.created_at) <= as_of_utc
        ]


class _RunAssetResolver:
    """Cached run -> source asset lookup over landing-layer lineage."""

    def __init__(self, control_plane: Any) -> None:
        self._list_lineage = getattr(control_plane, "list_source_lineage", None)
        self._cache: dict[str, str | None] = {}

    def get(self, run_id: str) -> str | None:
        if self._list_lineage is None:
            return None
        if run_id not in self._cache:
            records = self._list_lineage(input_run_id=run_id, target_layer="landing")
            assets = [
                record.target_name
                for record in records
                if record.target_kind == _SOURCE_ASSET_TARGET_KIND and record.target_name
            ]
            # Records come in recorded_at order; a re-promotion repeats the row.
            self._cache[run_id] = assets[-1] if assets else None
        return self._cache[run_id]


def _resolve_contributing_sources(
    lineage_records: list[Any],
    resolver: _RunResolver,
    assets: _RunAssetResolver,
) -> dict[str, _ContributingSource]:
    """Latest contributing run per source, in lineage ``recorded_at`` order."""
    sources: dict[str, _ContributingSource] = {}
    for record in lineage_records:
        run_id = record.source_run_id or record.input_run_id
        if not run_id:
            continue
        source_asset_id = assets.get(run_id)
        if source_asset_id:
            source_key = source_asset_id
            declared = False
        elif record.source_system:
            source_key = record.source_system
            declared = True
        else:
            run = resolver.get(run_id)
            if run is None or not run.source_name:
                # Unattributable lineage: cannot tie the run to a source.
                continue
            source_key = run.source_name
            declared = False
        previous = sources.get(source_key)
        sources[source_key] = _ContributingSource(
            source_key=source_key,
            run_id=run_id,
            lineage_row_count=record.row_count,
            declared=declared or (previous.declared if previous else False),
            source_asset_id=source_asset_id,
        )
    return sources


def _validation_flags(
    sources: dict[str, _ContributingSource],
    resolver: _RunResolver,
    *,
    as_of: datetime,
) -> dict[str, int]:
    errors = 0
    rejected = 0
    unknown = 0
    checked = 0
    for source in sources.values():
        run = resolver.get(source.run_id)
        if run is None:
            unknown += 1
            continue
        checked += 1
        errors += len(run.issues)
        if not run.passed or _status_value(run.status) in _FAILED_RUN_STATUSES:
            rejected += 1
        later_failures = resolver.later_failed_runs(
            run,
            as_of=as_of,
            match_source_name=source.source_asset_id is None,
        )
        for later in later_failures:
            rejected += 1
            errors += len(later.issues)
    flags = {REJECTED_RUNS_FLAG: rejected, VALIDATION_UNKNOWN_RUNS_FLAG: unknown}
    if checked:
        # Only report an error count when at least one run was inspected;
        # absence of the key marks validation as unknown.
        flags[VALIDATION_ERRORS_FLAG] = errors
    return flags


def _completeness(
    sources: dict[str, _ContributingSource],
    resolver: _RunResolver,
) -> tuple[int, dict[str, int]]:
    expected = len(sources)
    covered = 0
    unknown = 0
    for source in sources.values():
        run = resolver.get(source.run_id)
        if run is None:
            unknown += 1
            continue
        loaded_ok = source.lineage_row_count is None or source.lineage_row_count > 0
        if run.passed and run.row_count > 0 and loaded_ok:
            covered += 1
    pct = (100 * covered) // expected if expected else 0
    return pct, {
        COMPLETENESS_EXPECTED_SOURCES_FLAG: expected,
        COMPLETENESS_COVERED_SOURCES_FLAG: covered,
        COMPLETENESS_UNKNOWN_SOURCES_FLAG: unknown,
    }


def compute_and_record_publication_confidence(
    publication_key: str,
    control_plane: ControlPlaneStore,
    storage_adapter,
    *,
    as_of: datetime | None = None,
    run_metadata_store: _RunLookup | None = None,
    key_resolver: PublicationKeyResolver | None = None,
) -> PublicationConfidenceSnapshot:
    """Compute confidence for a publication and record the snapshot.

    Args:
        publication_key: The publication to assess (e.g., "pub_financial_summary")
        control_plane: Control plane to query lineage/audit/freshness config
        storage_adapter: Warehouse adapter (reserved; not currently read)
        as_of: Timestamp to assess as of (default: now)
        run_metadata_store: Run metadata store holding landing validation
            outcomes. Falls back to ``control_plane`` when it exposes
            ``get_run``. Without either, validation and completeness are
            recorded as unknown.
        key_resolver: Canonicalizes ``publication_key`` (contract key or relation
            name) to the relation name that lineage and snapshots are keyed by.

    Returns:
        PublicationConfidenceSnapshot with verdict and metadata

    Side effect: Records the snapshot in publication_confidence_snapshot table
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    if key_resolver is not None:
        publication_key = key_resolver.snapshot_key(publication_key)

    lookup: _RunLookup | None = run_metadata_store
    if lookup is None and hasattr(control_plane, "get_run"):
        lookup = control_plane  # type: ignore[assignment]
    resolver = _RunResolver(lookup)

    lineage_records = (
        control_plane.list_source_lineage(target_name=publication_key)
        if hasattr(control_plane, "list_source_lineage")
        else []
    )
    sources = _resolve_contributing_sources(
        list(lineage_records), resolver, _RunAssetResolver(control_plane)
    )
    contributing_run_ids: list[str] = []
    for source in sources.values():
        if source.run_id not in contributing_run_ids:
            contributing_run_ids.append(source.run_id)

    # Evaluate freshness for each contributing source
    source_freshness_states: dict[str, SourceFreshnessSnapshot] = {}
    all_freshness_configs = {
        config.source_asset_id: config
        for config in control_plane.list_source_freshness_configs()
    }
    unconfigured_defaulted = 0

    for source_key, source in sources.items():
        if source.source_asset_id is not None or source.declared:
            freshness_config = all_freshness_configs.get(source_key)
        else:
            # A source_name fallback is not a source asset id; matching it against
            # configs could attach another asset's schedule.
            freshness_config = None

        if freshness_config is None:
            if source.declared and source.source_asset_id is None:
                # Lineage-declared sources without config keep the historical
                # CURRENT default; counted so the gap stays visible.
                unconfigured_defaulted += 1
                source_freshness_states[source_key] = SourceFreshnessSnapshot(
                    source_asset_id=source_key,
                    freshness_state=SourceFreshnessState.CURRENT,
                    last_ingest_at=as_of,
                )
            else:
                source_freshness_states[source_key] = SourceFreshnessSnapshot(
                    source_asset_id=source_key,
                    freshness_state=SourceFreshnessState.UNCONFIGURED,
                )
            continue

        run = resolver.get(source.run_id)
        # The run's landing date gives the period it covers for a scheduled
        # config (see ``run_observation``). Without run metadata there is no
        # observation, so the state comes from the schedule alone and an
        # unknown run can never read current.
        observations = (
            [
                run_observation(
                    freshness_config,
                    status=_status_value(run.status),
                    observed_at=run.created_at,
                    as_of=as_of,
                )
            ]
            if run is not None
            else []
        )

        assessment = evaluate_source_freshness(
            freshness_config,
            observations,
            as_of=as_of.date() if isinstance(as_of, datetime) else as_of,
        )

        source_freshness_states[source_key] = SourceFreshnessSnapshot(
            source_asset_id=source_key,
            freshness_state=assessment.state,
            last_ingest_at=assessment.last_ingest_at,
            covered_through=assessment.covered_through.isoformat()
            if assessment.covered_through
            else None,
        )

    completeness_pct, completeness_flags = _completeness(sources, resolver)
    quality_flags: dict[str, int] = {
        **_validation_flags(sources, resolver, as_of=as_of),
        **completeness_flags,
        FRESHNESS_UNCONFIGURED_SOURCES_FLAG: unconfigured_defaulted,
    }

    freshness_state = compute_publication_freshness_state(source_freshness_states)

    snapshot = PublicationConfidenceSnapshot.create(
        publication_key=publication_key,
        assessed_at=as_of,
        freshness_state=freshness_state,
        completeness_pct=completeness_pct,
        source_freshness_states=source_freshness_states,
        contributing_run_ids=contributing_run_ids,
        quality_flags=quality_flags,
    )

    create_entry = PublicationConfidenceSnapshotCreate(
        snapshot_id=snapshot.snapshot_id,
        publication_key=snapshot.publication_key,
        assessed_at=snapshot.assessed_at,
        freshness_state=str(snapshot.freshness_state),
        completeness_pct=snapshot.completeness_pct,
        confidence_verdict=str(snapshot.confidence_verdict),
        quality_flags=snapshot.quality_flags,
        contributing_run_ids=tuple(snapshot.contributing_run_ids) if snapshot.contributing_run_ids else (),
    )
    control_plane.record_publication_confidence_snapshot((create_entry,))

    return snapshot
