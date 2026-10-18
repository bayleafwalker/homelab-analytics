"""Tests for publication confidence signals derived from real run metadata.

Covers compute_and_record_publication_confidence() validation and
completeness semantics: clean runs, validation failures, partial coverage,
and unknown inputs (no run metadata available).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.pipelines.csv_validation import ValidationIssue
from packages.pipelines.publication_confidence_service import (
    compute_and_record_publication_confidence,
)
from packages.pipelines.transformation_service import TransformationService
from packages.platform.publication_confidence import (
    ConfidenceVerdict,
    SignalState,
    get_latest_publication_confidence,
)
from packages.platform.source_freshness import SourceFreshnessState
from packages.storage.control_plane import SourceLineageCreate
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import (
    IngestionRunCreate,
    IngestionRunStatus,
    RunMetadataRepository,
)

PUBLICATION = "mart_test_publication"
AS_OF = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def control_plane(tmp_path: Path) -> IngestionConfigRepository:
    return IngestionConfigRepository(tmp_path / "config.db")


@pytest.fixture
def runs(tmp_path: Path) -> RunMetadataRepository:
    return RunMetadataRepository(tmp_path / "runs.db")


def _land(
    runs: RunMetadataRepository,
    run_id: str,
    *,
    source_name: str = "bank",
    dataset_name: str = "transactions",
    row_count: int = 2,
    issues: tuple[ValidationIssue, ...] = (),
    created_at: datetime = AS_OF - timedelta(days=1),
) -> None:
    passed = not issues
    runs.create_run(
        IngestionRunCreate(
            run_id=run_id,
            source_name=source_name,
            dataset_name=dataset_name,
            file_name=f"{run_id}.csv",
            raw_path=f"raw/{run_id}.csv",
            manifest_path=f"raw/{run_id}.json",
            sha256=uuid.uuid4().hex,
            row_count=row_count,
            header=("a", "b"),
            status=IngestionRunStatus.LANDED if passed else IngestionRunStatus.REJECTED,
            passed=passed,
            issues=issues,
            created_at=created_at,
        )
    )


def _lineage(
    control_plane: IngestionConfigRepository,
    run_id: str,
    *,
    source_system: str | None = "bank",
    row_count: int | None = 2,
    target_name: str = PUBLICATION,
) -> None:
    control_plane.record_source_lineage(
        (
            SourceLineageCreate(
                lineage_id=uuid.uuid4().hex[:16],
                input_run_id=run_id,
                source_run_id=run_id,
                source_system=source_system,
                target_layer="reporting",
                target_name=target_name,
                target_kind="mart",
                row_count=row_count,
            ),
        )
    )


def _issue(code: str = "missing_value") -> ValidationIssue:
    return ValidationIssue(code=code, message="bad row", column="a", row_number=2)


def _compute(control_plane, runs=None):
    return compute_and_record_publication_confidence(
        PUBLICATION, control_plane, None, as_of=AS_OF, run_metadata_store=runs
    )


def test_clean_run_is_trustworthy(control_plane, runs) -> None:
    _land(runs, "run-1")
    _lineage(control_plane, "run-1")

    snapshot = _compute(control_plane, runs)

    assert snapshot.confidence_verdict == ConfidenceVerdict.TRUSTWORTHY
    assert snapshot.completeness_pct == 100
    assert snapshot.quality_flags["validation_errors"] == 0
    assert snapshot.quality_flags["rejected_runs"] == 0
    assert snapshot.quality_flags["validation_unknown_runs"] == 0
    assert snapshot.validation_state == SignalState.KNOWN
    assert snapshot.completeness_state == SignalState.KNOWN
    assert snapshot.contributing_run_ids == ["run-1"]


def test_later_rejected_landing_degrades_verdict(control_plane, runs) -> None:
    _land(runs, "run-1", created_at=AS_OF - timedelta(days=2))
    _lineage(control_plane, "run-1")
    _land(
        runs,
        "run-2",
        issues=(_issue(), _issue("bad_date")),
        created_at=AS_OF - timedelta(hours=1),
    )

    snapshot = _compute(control_plane, runs)

    assert snapshot.quality_flags["validation_errors"] == 2
    assert snapshot.quality_flags["rejected_runs"] == 1
    assert snapshot.completeness_pct == 100
    assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED


def test_rejected_landing_after_as_of_or_other_source_is_ignored(
    control_plane, runs
) -> None:
    _land(runs, "run-1", created_at=AS_OF - timedelta(days=2))
    _lineage(control_plane, "run-1")
    _land(runs, "run-future", issues=(_issue(),), created_at=AS_OF + timedelta(hours=1))
    _land(
        runs,
        "run-other",
        source_name="other_bank",
        issues=(_issue(),),
        created_at=AS_OF - timedelta(hours=1),
    )

    snapshot = _compute(control_plane, runs)

    assert snapshot.quality_flags["validation_errors"] == 0
    assert snapshot.confidence_verdict == ConfidenceVerdict.TRUSTWORTHY


def test_rejected_contributing_run_is_unreliable(control_plane, runs) -> None:
    _land(runs, "run-1", issues=(_issue(),))
    _lineage(control_plane, "run-1")

    snapshot = _compute(control_plane, runs)

    assert snapshot.quality_flags["validation_errors"] == 1
    assert snapshot.quality_flags["rejected_runs"] == 1
    assert snapshot.completeness_pct == 0
    assert snapshot.confidence_verdict == ConfidenceVerdict.UNRELIABLE


def test_partial_coverage_degrades_verdict(control_plane, runs) -> None:
    _land(runs, "run-bank")
    _lineage(control_plane, "run-bank", source_system="bank")
    _land(runs, "run-card", source_name="card", row_count=0)
    _lineage(control_plane, "run-card", source_system="card", row_count=0)

    snapshot = _compute(control_plane, runs)

    assert snapshot.completeness_pct == 50
    assert snapshot.quality_flags["completeness_expected_sources"] == 2
    assert snapshot.quality_flags["completeness_covered_sources"] == 1
    assert snapshot.quality_flags["completeness_unknown_sources"] == 0
    assert snapshot.quality_flags["validation_errors"] == 0
    assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED


def test_latest_lineage_run_per_source_is_used(control_plane, runs) -> None:
    _land(runs, "run-old", row_count=0, created_at=AS_OF - timedelta(days=3))
    _lineage(control_plane, "run-old", row_count=0)
    _land(runs, "run-new", created_at=AS_OF - timedelta(days=1))
    _lineage(control_plane, "run-new")

    snapshot = _compute(control_plane, runs)

    assert snapshot.contributing_run_ids == ["run-new"]
    assert snapshot.completeness_pct == 100
    assert snapshot.confidence_verdict == ConfidenceVerdict.TRUSTWORTHY


def test_unknown_inputs_do_not_upgrade_confidence(control_plane) -> None:
    """Without run metadata, validation and completeness are unknown."""
    _lineage(control_plane, "run-1")

    snapshot = _compute(control_plane, runs=None)

    assert "validation_errors" not in snapshot.quality_flags
    assert snapshot.quality_flags["validation_unknown_runs"] == 1
    assert snapshot.quality_flags["completeness_unknown_sources"] == 1
    assert snapshot.completeness_pct == 0
    assert snapshot.validation_state == SignalState.UNKNOWN
    assert snapshot.completeness_state == SignalState.UNKNOWN
    # Not trustworthy, but unknown alone does not make it unreliable either.
    assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED


def test_partially_unknown_runs_are_partial(control_plane, runs) -> None:
    _land(runs, "run-bank")
    _lineage(control_plane, "run-bank", source_system="bank")
    _lineage(control_plane, "run-missing", source_system="card")

    snapshot = _compute(control_plane, runs)

    assert snapshot.quality_flags["validation_errors"] == 0
    assert snapshot.quality_flags["validation_unknown_runs"] == 1
    assert snapshot.validation_state == SignalState.PARTIAL
    assert snapshot.completeness_state == SignalState.PARTIAL
    assert snapshot.completeness_pct == 50
    assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED


def test_no_lineage_is_unavailable(control_plane, runs) -> None:
    snapshot = _compute(control_plane, runs)

    assert snapshot.confidence_verdict == ConfidenceVerdict.UNAVAILABLE
    assert snapshot.completeness_pct == 0
    assert "validation_errors" not in snapshot.quality_flags


def test_reporting_lineage_without_source_system_resolves_via_run(
    control_plane, runs
) -> None:
    """Sources resolved from run metadata without freshness config are UNCONFIGURED."""
    _land(runs, "run-1", source_name="bank")
    _lineage(control_plane, "run-1", source_system=None, row_count=None)

    snapshot = _compute(control_plane, runs)

    assert snapshot.contributing_run_ids == ["run-1"]
    assert (
        snapshot.source_freshness_states["bank"].freshness_state
        == SourceFreshnessState.UNCONFIGURED
    )
    assert snapshot.quality_flags["validation_errors"] == 0
    assert snapshot.quality_flags["freshness_unconfigured_sources"] == 0
    assert snapshot.confidence_verdict == ConfidenceVerdict.UNAVAILABLE


def test_quality_flags_round_trip_through_control_plane(control_plane, runs) -> None:
    _land(runs, "run-1", created_at=AS_OF - timedelta(days=2))
    _lineage(control_plane, "run-1")
    _land(runs, "run-2", issues=(_issue(),), created_at=AS_OF - timedelta(hours=1))
    recorded = _compute(control_plane, runs)

    latest = get_latest_publication_confidence(PUBLICATION, control_plane)

    assert latest is not None
    assert latest.confidence_verdict == recorded.confidence_verdict
    assert latest.quality_flags == recorded.quality_flags
    assert latest.validation_state == SignalState.KNOWN


def test_transformation_service_feeds_run_metadata_into_confidence(
    control_plane, runs
) -> None:
    _land(runs, "run-1")
    _lineage(control_plane, "run-1", target_name="mart_monthly_cashflow")
    service = TransformationService(
        DuckDBStore.memory(),
        control_plane_store=control_plane,
        run_metadata_store=runs,
    )

    service.refresh_publications(["mart_monthly_cashflow"])

    latest = get_latest_publication_confidence("mart_monthly_cashflow", control_plane)
    assert latest is not None
    assert latest.quality_flags["validation_errors"] == 0
    assert latest.quality_flags["validation_unknown_runs"] == 0
    assert latest.completeness_pct == 100
