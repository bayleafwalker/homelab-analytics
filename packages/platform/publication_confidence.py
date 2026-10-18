"""Publication confidence snapshot model and computation.

Provides deterministic confidence verdicts based on source freshness, completeness,
and validation state. Every publication refresh triggers a snapshot capture that
makes stale or degraded data degrade visibly rather than silently.

Signal semantics (see ``docs/architecture/semantic-contracts.md``):

- **Validation** comes from landing validation results recorded in run
  metadata for the runs that fed the publication. It is reported through
  ``quality_flags``: ``validation_errors`` (issue count), ``rejected_runs``
  and ``validation_unknown_runs``. A missing ``validation_errors`` key or a
  non-zero ``validation_unknown_runs`` means the signal is *unknown*.
- **Completeness** is the share of contributing sources whose latest input
  run is verifiably present (landed, passed, non-empty). Sources whose run
  metadata cannot be resolved count as not covered in ``completeness_pct``
  and are reported in ``completeness_unknown_sources``.
- An unknown signal never upgrades confidence: a snapshot is only
  ``trustworthy`` when every signal is known and clean.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Mapping

from packages.platform.source_freshness import SourceFreshnessState

if TYPE_CHECKING:
    from packages.storage.control_plane import ControlPlaneStore


class ConfidenceVerdict(StrEnum):
    """Confidence verdict for a publication snapshot."""

    TRUSTWORTHY = "trustworthy"  # All sources current, completeness 100%
    DEGRADED = "degraded"  # Some source staleness, but usable (>= 50% complete)
    UNRELIABLE = "unreliable"  # Significant source gaps or staleness (<50% complete)
    UNAVAILABLE = "unavailable"  # No data or all sources unconfigured


class SignalState(StrEnum):
    """Whether a confidence signal could be computed from real inputs."""

    KNOWN = "known"  # Fully computed from recorded inputs
    PARTIAL = "partial"  # Computed for some inputs; others unavailable
    UNKNOWN = "unknown"  # Inputs unavailable; signal not computed


# quality_flags keys written by the confidence service.
VALIDATION_ERRORS_FLAG = "validation_errors"
REJECTED_RUNS_FLAG = "rejected_runs"
VALIDATION_UNKNOWN_RUNS_FLAG = "validation_unknown_runs"
COMPLETENESS_EXPECTED_SOURCES_FLAG = "completeness_expected_sources"
COMPLETENESS_COVERED_SOURCES_FLAG = "completeness_covered_sources"
COMPLETENESS_UNKNOWN_SOURCES_FLAG = "completeness_unknown_sources"
FRESHNESS_UNCONFIGURED_SOURCES_FLAG = "freshness_unconfigured_sources"


class FreshnessState(StrEnum):
    """Publication-level freshness state derived from source freshness."""

    CURRENT = "current"  # All sources are current
    DUE_SOON = "due_soon"  # Next source ingest due soon
    STALE = "stale"  # At least one source is overdue or missing period
    UNAVAILABLE = "unavailable"  # All sources are unconfigured


@dataclass(frozen=True)
class SourceFreshnessSnapshot:
    """Freshness state of a contributing source at snapshot time."""

    source_asset_id: str
    freshness_state: SourceFreshnessState
    last_ingest_at: datetime | None = None
    covered_through: str | None = None  # ISO date string YYYY-MM-DD


@dataclass(frozen=True)
class PublicationConfidenceSnapshot:
    """Deterministic confidence snapshot for a publication at a point in time."""

    snapshot_id: str
    publication_key: str
    assessed_at: datetime
    freshness_state: FreshnessState
    # Percentage (0-100) of contributing sources whose latest input run is
    # verifiably present; unresolvable sources count as not covered.
    completeness_pct: int
    source_freshness_states: Mapping[str, SourceFreshnessSnapshot] = field(
        default_factory=dict
    )
    contributing_run_ids: list[str] = field(default_factory=list)
    quality_flags: dict[str, int] = field(
        default_factory=dict
    )  # e.g. {"validation_errors": 5, "rejected_runs": 1}; see module docstring
    confidence_verdict: ConfidenceVerdict = ConfidenceVerdict.TRUSTWORTHY

    @property
    def validation_state(self) -> SignalState:
        """Whether validation was evaluated for every contributing run."""
        return validation_signal_state(self.quality_flags)

    @property
    def completeness_state(self) -> SignalState:
        """Whether completeness was resolved for every contributing source."""
        return completeness_signal_state(self.quality_flags)

    @classmethod
    def create(
        cls,
        publication_key: str,
        assessed_at: datetime,
        freshness_state: FreshnessState,
        completeness_pct: int,
        source_freshness_states: Mapping[str, SourceFreshnessSnapshot] | None = None,
        contributing_run_ids: list[str] | None = None,
        quality_flags: dict[str, int] | None = None,
    ) -> PublicationConfidenceSnapshot:
        """Create a new confidence snapshot and compute verdict."""
        if source_freshness_states is None:
            source_freshness_states = {}
        if contributing_run_ids is None:
            contributing_run_ids = []
        if quality_flags is None:
            quality_flags = {}

        verdict = _compute_verdict(
            source_freshness_states, completeness_pct, quality_flags
        )

        return cls(
            snapshot_id=str(uuid.uuid4()),
            publication_key=publication_key,
            assessed_at=assessed_at,
            freshness_state=freshness_state,
            completeness_pct=completeness_pct,
            source_freshness_states=source_freshness_states,
            contributing_run_ids=contributing_run_ids,
            quality_flags=quality_flags,
            confidence_verdict=verdict,
        )


def validation_signal_state(quality_flags: Mapping[str, int] | None) -> SignalState:
    """Classify the validation signal recorded in ``quality_flags``.

    Snapshots without a ``validation_errors`` key carry no validation input
    and are UNKNOWN. A non-zero ``validation_unknown_runs`` makes it PARTIAL.
    """
    flags = quality_flags or {}
    if VALIDATION_ERRORS_FLAG not in flags:
        return SignalState.UNKNOWN
    if int(flags.get(VALIDATION_UNKNOWN_RUNS_FLAG, 0)) > 0:
        return SignalState.PARTIAL
    return SignalState.KNOWN


def completeness_signal_state(
    quality_flags: Mapping[str, int] | None,
) -> SignalState:
    """Classify the completeness signal recorded in ``quality_flags``.

    Snapshots that do not record ``completeness_unknown_sources`` predate
    proportional completeness and are treated as KNOWN (their stored
    ``completeness_pct`` is taken at face value).
    """
    flags = quality_flags or {}
    unknown = int(flags.get(COMPLETENESS_UNKNOWN_SOURCES_FLAG, 0))
    if unknown <= 0:
        return SignalState.KNOWN
    expected = int(flags.get(COMPLETENESS_EXPECTED_SOURCES_FLAG, unknown))
    if unknown >= expected:
        return SignalState.UNKNOWN
    return SignalState.PARTIAL


def _has_validation_errors(quality_flags: Mapping[str, int]) -> bool:
    return (
        int(quality_flags.get(VALIDATION_ERRORS_FLAG, 0)) > 0
        or int(quality_flags.get(REJECTED_RUNS_FLAG, 0)) > 0
    )


def _completeness_upper_bound(
    completeness_pct: int, quality_flags: Mapping[str, int]
) -> float:
    """Best possible completeness if every unknown source turned out covered."""
    unknown = int(quality_flags.get(COMPLETENESS_UNKNOWN_SOURCES_FLAG, 0))
    expected = int(quality_flags.get(COMPLETENESS_EXPECTED_SOURCES_FLAG, 0))
    if unknown <= 0 or expected <= 0:
        return float(completeness_pct)
    return min(100.0, completeness_pct + 100.0 * unknown / expected)


def _compute_verdict(
    source_freshness_states: Mapping[str, SourceFreshnessSnapshot],
    completeness_pct: int,
    quality_flags: Mapping[str, int] | None = None,
) -> ConfidenceVerdict:
    """Compute verdict from source freshness, completeness and validation.

    Logic (evaluated in order):
    - No sources, or all sources UNCONFIGURED → UNAVAILABLE
    - All sources CURRENT, completeness known and == 100%, validation known
      with zero errors and zero rejected runs → TRUSTWORTHY
    - Any source OVERDUE/MISSING_PERIOD, or validation errors present →
      UNRELIABLE when completeness is below 50% even counting every unknown
      source as covered, else DEGRADED
    - Otherwise → DEGRADED (this includes any unknown or partial signal)

    Unknown signals can never produce TRUSTWORTHY, and an unknown source is
    never counted toward the 50% threshold as missing (it cannot make a
    verdict UNRELIABLE on its own).
    """
    flags: Mapping[str, int] = quality_flags or {}
    if not source_freshness_states:
        return ConfidenceVerdict.UNAVAILABLE

    states = [snap.freshness_state for snap in source_freshness_states.values()]

    if all(state == SourceFreshnessState.UNCONFIGURED for state in states):
        return ConfidenceVerdict.UNAVAILABLE

    validation_state = validation_signal_state(flags)
    completeness_state = completeness_signal_state(flags)
    has_errors = _has_validation_errors(flags)

    if (
        all(state == SourceFreshnessState.CURRENT for state in states)
        and completeness_pct == 100
        and completeness_state == SignalState.KNOWN
        and validation_state == SignalState.KNOWN
        and not has_errors
    ):
        return ConfidenceVerdict.TRUSTWORTHY

    stale = any(
        state in (SourceFreshnessState.OVERDUE, SourceFreshnessState.MISSING_PERIOD)
        for state in states
    )
    if stale or has_errors:
        return (
            ConfidenceVerdict.UNRELIABLE
            if _completeness_upper_bound(completeness_pct, flags) < 50
            else ConfidenceVerdict.DEGRADED
        )

    return ConfidenceVerdict.DEGRADED


def compute_publication_freshness_state(
    source_freshness_states: Mapping[str, SourceFreshnessSnapshot],
) -> FreshnessState:
    """Compute publication-level freshness state from source states.

    Defaults to UNAVAILABLE if no sources.
    """
    if not source_freshness_states:
        return FreshnessState.UNAVAILABLE

    states = [snap.freshness_state for snap in source_freshness_states.values()]

    # If any source is overdue or missing, publication is stale
    if any(
        state in (SourceFreshnessState.OVERDUE, SourceFreshnessState.MISSING_PERIOD)
        for state in states
    ):
        return FreshnessState.STALE

    # If any source is due soon, publication is due soon
    if any(state == SourceFreshnessState.DUE_SOON for state in states):
        return FreshnessState.DUE_SOON

    # If all are current, publication is current
    if all(state == SourceFreshnessState.CURRENT for state in states):
        return FreshnessState.CURRENT

    # Otherwise unavailable
    return FreshnessState.UNAVAILABLE


def get_latest_publication_confidence(
    publication_key: str,
    control_plane: ControlPlaneStore,
) -> PublicationConfidenceSnapshot | None:
    """Retrieve the latest confidence snapshot for a publication.

    Args:
        publication_key: The publication key to look up
        control_plane: Control plane to query snapshots

    Returns:
        Latest PublicationConfidenceSnapshot, or None if not found
    """
    records = control_plane.list_publication_confidence_snapshots(
        publication_key=publication_key,
        limit=1,
    )
    if not records:
        return None

    record = records[0]
    return PublicationConfidenceSnapshot(
        snapshot_id=record.snapshot_id,
        publication_key=record.publication_key,
        assessed_at=record.assessed_at,
        freshness_state=FreshnessState(record.freshness_state),
        completeness_pct=record.completeness_pct,
        source_freshness_states={},  # Could hydrate from record if needed
        contributing_run_ids=list(record.contributing_run_ids),
        quality_flags=record.quality_flags or {},
        confidence_verdict=ConfidenceVerdict(record.confidence_verdict),
    )
