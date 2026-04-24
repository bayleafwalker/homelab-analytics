"""Publication confidence snapshot model and computation.

Provides deterministic confidence verdicts based on source freshness, completeness,
and validation state. Every publication refresh triggers a snapshot capture that
makes stale or degraded data degrade visibly rather than silently.
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
    completeness_pct: int  # 0 or 100: binary presence flag (lineage records exist or not).
    # TODO: replace with genuine proportional calculation (contributing runs / expected runs)
    source_freshness_states: Mapping[str, SourceFreshnessSnapshot] = field(
        default_factory=dict
    )
    contributing_run_ids: list[str] = field(default_factory=list)
    quality_flags: dict[str, int] = field(
        default_factory=dict
    )  # e.g. {"validation_errors": 5, "parse_failures": 0}
    confidence_verdict: ConfidenceVerdict = ConfidenceVerdict.TRUSTWORTHY

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

        verdict = _compute_verdict(source_freshness_states, completeness_pct)

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


def _compute_verdict(
    source_freshness_states: Mapping[str, SourceFreshnessSnapshot],
    completeness_pct: int,
) -> ConfidenceVerdict:
    """Compute verdict from source freshness and completeness.

    Logic:
    - All sources CURRENT and completeness == 100% → TRUSTWORTHY
    - Any source OVERDUE or MISSING_PERIOD → DEGRADED if >=50% complete, else UNRELIABLE
    - All sources UNCONFIGURED → UNAVAILABLE
    - Otherwise → DEGRADED
    """
    if not source_freshness_states:
        return ConfidenceVerdict.UNAVAILABLE

    states = [snap.freshness_state for snap in source_freshness_states.values()]

    # All current and fully complete
    if (
        all(state == SourceFreshnessState.CURRENT for state in states)
        and completeness_pct == 100
    ):
        return ConfidenceVerdict.TRUSTWORTHY

    # Any source overdue or with missing period
    if any(
        state in (SourceFreshnessState.OVERDUE, SourceFreshnessState.MISSING_PERIOD)
        for state in states
    ):
        return (
            ConfidenceVerdict.DEGRADED
            if completeness_pct >= 50
            else ConfidenceVerdict.UNRELIABLE
        )

    # All sources unconfigured
    if all(state == SourceFreshnessState.UNCONFIGURED for state in states):
        return ConfidenceVerdict.UNAVAILABLE

    # Default: degraded but usable
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
