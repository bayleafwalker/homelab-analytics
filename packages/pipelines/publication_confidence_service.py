"""Publication confidence computation service.

Computes PublicationConfidenceSnapshot objects from lineage, source freshness,
and validation state, then stores them in the control plane.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from packages.platform.publication_confidence import (
    PublicationConfidenceSnapshot,
    SourceFreshnessSnapshot,
    compute_publication_freshness_state,
)
from packages.platform.source_freshness import (
    SourceFreshnessRunObservation,
    SourceFreshnessState,
    evaluate_source_freshness,
)
from packages.storage.control_plane import PublicationConfidenceSnapshotCreate

if TYPE_CHECKING:
    from packages.storage.control_plane import ControlPlaneStore


def compute_and_record_publication_confidence(
    publication_key: str,
    control_plane: ControlPlaneStore,
    storage_adapter,
    *,
    as_of: datetime | None = None,
) -> PublicationConfidenceSnapshot:
    """Compute confidence for a publication and record the snapshot.

    Args:
        publication_key: The publication to assess (e.g., "pub_financial_summary")
        control_plane: Control plane to query lineage/audit/freshness config
        storage_adapter: Warehouse adapter to check validation state
        as_of: Timestamp to assess as of (default: now)

    Returns:
        PublicationConfidenceSnapshot with verdict and metadata

    Side effect: Records the snapshot in publication_confidence_snapshot table
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    # Query lineage for this publication
    lineage_records = control_plane.list_source_lineage(target_name=publication_key) if hasattr(control_plane, 'list_source_lineage') else []

    # Identify unique source systems and their latest runs
    source_runs: dict[str, str] = {}
    contributing_run_ids: list[str] = []
    for record in lineage_records:
        if record.source_system and record.source_run_id:
            source_runs[record.source_system] = record.source_run_id
            if record.source_run_id not in contributing_run_ids:
                contributing_run_ids.append(record.source_run_id)

    # Evaluate freshness for each contributing source
    source_freshness_states: dict[str, SourceFreshnessSnapshot] = {}
    all_freshness_configs = {
        config.source_asset_id: config
        for config in control_plane.list_source_freshness_configs()
    }

    for source_system in source_runs.keys():
        freshness_config = all_freshness_configs.get(source_system)

        # If no config exists, default to CURRENT (backwards compat)
        if freshness_config is None:
            source_freshness_states[source_system] = SourceFreshnessSnapshot(
                source_asset_id=source_system,
                freshness_state=SourceFreshnessState.CURRENT,
                last_ingest_at=as_of,
            )
            continue

        run_id = source_runs.get(source_system)
        if run_id and hasattr(control_plane, "get_run"):
            try:
                run = control_plane.get_run(run_id)
                observations = [
                    SourceFreshnessRunObservation(
                        status=str(run.status),
                        observed_at=run.created_at,
                        covered_from=None,
                        covered_through=None,
                    )
                ]
            except (KeyError, AttributeError):
                observations = []
        else:
            observations = []

        # Evaluate freshness using the source freshness engine
        assessment = evaluate_source_freshness(
            freshness_config,
            observations,
            as_of=as_of.date() if isinstance(as_of, datetime) else as_of,
        )

        source_freshness_states[source_system] = SourceFreshnessSnapshot(
            source_asset_id=source_system,
            freshness_state=assessment.state,
            last_ingest_at=assessment.last_ingest_at,
            covered_through=assessment.covered_through.isoformat()
            if assessment.covered_through
            else None,
        )

    # Binary presence flag until proportional calculation is implemented (TODO)
    completeness_pct = 100 if lineage_records else 0

    # Derive publication-level freshness state
    freshness_state = compute_publication_freshness_state(source_freshness_states)

    # Create snapshot
    snapshot = PublicationConfidenceSnapshot.create(
        publication_key=publication_key,
        assessed_at=as_of,
        freshness_state=freshness_state,
        completeness_pct=completeness_pct,
        source_freshness_states=source_freshness_states,
        contributing_run_ids=contributing_run_ids,
        quality_flags={"validation_errors": 0},  # TODO: Query actual validation state
    )

    # Record in control plane
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
