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
from packages.platform.source_freshness import SourceFreshnessState
from packages.storage.control_plane import PublicationConfidenceSnapshotCreate

if TYPE_CHECKING:
    from packages.storage.control_plane import ControlPlane


def compute_and_record_publication_confidence(
    publication_key: str,
    control_plane: ControlPlane,
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
    # For now, assume CURRENT unless we have freshness config
    # (This will be enhanced when non-finance freshness configs are populated)
    source_freshness_states: dict[str, SourceFreshnessSnapshot] = {}
    for source_system in source_runs.keys():
        source_freshness_states[source_system] = SourceFreshnessSnapshot(
            source_asset_id=source_system,
            freshness_state=SourceFreshnessState.CURRENT,  # Default assumption
            last_ingest_at=as_of,
        )

    # Calculate completeness: for now assume 100% if we have lineage, else 0
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


def get_latest_publication_confidence(
    publication_key: str,
    control_plane: ControlPlane,
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
        freshness_state=str(record.freshness_state),  # type: ignore
        completeness_pct=record.completeness_pct,
        source_freshness_states={},  # Could hydrate from record if needed
        contributing_run_ids=list(record.contributing_run_ids),
        quality_flags=record.quality_flags or {},
        confidence_verdict=str(record.confidence_verdict),  # type: ignore
    )
