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
    FreshnessState,
    SignalState,
    get_latest_publication_confidence,
)
from packages.platform.source_freshness import SourceFreshnessState
from packages.storage.control_plane import SourceLineageCreate
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_catalog import SourceFreshnessConfigCreate
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


# --- Source-asset attribution (#2801) -------------------------------------
#
# Freshness configs are keyed by source_asset_id. Confidence attributes each
# contributing run to the asset recorded by its landing-layer lineage row,
# the row ReportingService.record_reporting_lineage writes on promotion.


class _FreshnessConfigured:
    """Control plane whose freshness configs are set in-test.

    The SQLite catalog enforces a source-asset foreign key on freshness
    configs; these tests only need the configs the service lists.
    """

    def __init__(self, inner: IngestionConfigRepository) -> None:
        self._inner = inner
        self.freshness_configs: list[SourceFreshnessConfigCreate] = []

    def list_source_freshness_configs(self) -> list[SourceFreshnessConfigCreate]:
        return list(self.freshness_configs)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


@pytest.fixture
def plane(control_plane: IngestionConfigRepository) -> _FreshnessConfigured:
    return _FreshnessConfigured(control_plane)


def _asset_lineage(
    plane: _FreshnessConfigured, run_id: str, source_asset_id: str
) -> None:
    plane.record_source_lineage(
        (
            SourceLineageCreate(
                lineage_id=uuid.uuid4().hex[:16],
                input_run_id=run_id,
                source_run_id=run_id,
                target_layer="landing",
                target_name=source_asset_id,
                target_kind="source_asset",
            ),
        )
    )


def _promoted(
    plane: _FreshnessConfigured,
    runs: RunMetadataRepository,
    run_id: str,
    source_asset_id: str,
    **land_kwargs,
) -> None:
    """A run as the DuckDB promotion path records it: reporting + landing rows."""
    _land(runs, run_id, **land_kwargs)
    _lineage(plane, run_id, source_system=None, row_count=None)
    _asset_lineage(plane, run_id, source_asset_id)


def _freshness_config(
    plane: _FreshnessConfigured,
    source_asset_id: str,
    *,
    expected_frequency: str = "ad_hoc",
    due_day_of_month: int | None = None,
    expected_window_days: int = 5,
) -> None:
    if due_day_of_month is None and expected_frequency == "monthly":
        due_day_of_month = 5
    plane.freshness_configs.append(
        SourceFreshnessConfigCreate(
            source_asset_id=source_asset_id,
            acquisition_mode="manual_export",
            expected_frequency=expected_frequency,
            coverage_kind="rolling_period",
            due_day_of_month=due_day_of_month,
            expected_window_days=expected_window_days,
            freshness_sla_days=40,
            sensitivity_class="financial",
            reminder_channel="dashboard",
            requires_human_action=True,
        )
    )


def test_configured_source_asset_yields_real_freshness_and_verdict(
    plane, runs
) -> None:
    """Regression: run source_name ("bank") never matched the asset-keyed config."""
    _promoted(plane, runs, "run-1", "bank_asset", source_name="bank")
    _freshness_config(plane, "bank_asset")

    snapshot = _compute(plane, runs)

    assert set(snapshot.source_freshness_states) == {"bank_asset"}
    state = snapshot.source_freshness_states["bank_asset"]
    assert state.freshness_state == SourceFreshnessState.CURRENT
    assert state.last_ingest_at is not None
    assert snapshot.freshness_state == FreshnessState.CURRENT
    assert snapshot.confidence_verdict == ConfidenceVerdict.TRUSTWORTHY
    assert snapshot.quality_flags["freshness_unconfigured_sources"] == 0


def test_configured_schedule_is_evaluated_for_the_asset(plane, runs) -> None:
    """A monthly schedule is evaluated, not skipped.

    The run landed on 30 April, so it covers March; as of 1 May the expected
    period is April, which has not landed yet.
    """
    _promoted(plane, runs, "run-1", "bank_asset")
    _freshness_config(plane, "bank_asset", expected_frequency="monthly")

    snapshot = _compute(plane, runs)

    state = snapshot.source_freshness_states["bank_asset"].freshness_state
    assert state in {SourceFreshnessState.DUE_SOON, SourceFreshnessState.OVERDUE}
    assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED


def test_unconfigured_source_asset_is_unavailable(plane, runs) -> None:
    _promoted(plane, runs, "run-1", "bank_asset")

    snapshot = _compute(plane, runs)

    assert (
        snapshot.source_freshness_states["bank_asset"].freshness_state
        == SourceFreshnessState.UNCONFIGURED
    )
    # Validation and completeness are still read from the run.
    assert snapshot.completeness_pct == 100
    assert snapshot.quality_flags["validation_errors"] == 0
    assert snapshot.confidence_verdict == ConfidenceVerdict.UNAVAILABLE


def test_run_without_asset_never_matches_a_config_by_source_name(
    plane, runs
) -> None:
    """The source_name fallback reads as unconfigured even if an asset shares the name."""
    _land(runs, "run-1", source_name="bank")
    _lineage(plane, "run-1", source_system=None, row_count=None)
    _freshness_config(plane, "bank")

    snapshot = _compute(plane, runs)

    assert (
        snapshot.source_freshness_states["bank"].freshness_state
        == SourceFreshnessState.UNCONFIGURED
    )
    assert snapshot.confidence_verdict == ConfidenceVerdict.UNAVAILABLE


def test_recorded_asset_takes_precedence_over_declared_source(
    plane, runs
) -> None:
    _land(runs, "run-1")
    _lineage(plane, "run-1", source_system="bank")
    _asset_lineage(plane, "run-1", "bank_asset")

    snapshot = _compute(plane, runs)

    # Keyed by the asset; the declared-source CURRENT default does not apply.
    assert set(snapshot.source_freshness_states) == {"bank_asset"}
    assert (
        snapshot.source_freshness_states["bank_asset"].freshness_state
        == SourceFreshnessState.UNCONFIGURED
    )
    assert snapshot.quality_flags["freshness_unconfigured_sources"] == 0


def test_multi_asset_publication_keys_each_source_asset(plane, runs) -> None:
    _promoted(plane, runs, "run-bank", "bank_asset", source_name="upload")
    _promoted(plane, runs, "run-card", "card_asset", source_name="upload")
    _freshness_config(plane, "bank_asset")
    _freshness_config(plane, "card_asset")

    snapshot = _compute(plane, runs)

    # Same source_name, distinct assets: two contributing sources.
    assert set(snapshot.source_freshness_states) == {"bank_asset", "card_asset"}
    assert snapshot.contributing_run_ids == ["run-bank", "run-card"]
    assert snapshot.quality_flags["completeness_expected_sources"] == 2
    assert snapshot.confidence_verdict == ConfidenceVerdict.TRUSTWORTHY


def test_multi_asset_publication_with_one_unconfigured_asset_is_degraded(
    plane, runs
) -> None:
    _promoted(plane, runs, "run-bank", "bank_asset")
    _promoted(plane, runs, "run-card", "card_asset", source_name="card")
    _freshness_config(plane, "bank_asset")

    snapshot = _compute(plane, runs)

    states = {
        key: snap.freshness_state for key, snap in snapshot.source_freshness_states.items()
    }
    assert states == {
        "bank_asset": SourceFreshnessState.CURRENT,
        "card_asset": SourceFreshnessState.UNCONFIGURED,
    }
    # The unconfigured asset cannot upgrade the verdict to trustworthy.
    assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED


def test_latest_run_per_asset_is_used(plane, runs) -> None:
    _promoted(
        plane, runs, "run-old", "bank_asset", created_at=AS_OF - timedelta(days=3)
    )
    _promoted(
        plane, runs, "run-new", "bank_asset", created_at=AS_OF - timedelta(days=1)
    )
    _freshness_config(plane, "bank_asset")

    snapshot = _compute(plane, runs)

    assert snapshot.contributing_run_ids == ["run-new"]


def test_later_rejection_for_asset_dataset_counts_regardless_of_source_name(
    plane, runs
) -> None:
    """A rejected run has no asset lineage; its dataset is the asset's dataset."""
    _promoted(
        plane,
        runs,
        "run-1",
        "bank_asset",
        source_name="operator-upload",
        created_at=AS_OF - timedelta(days=2),
    )
    _freshness_config(plane, "bank_asset")
    _land(
        runs,
        "run-rejected",
        source_name="configured-upload",
        issues=(_issue(),),
        created_at=AS_OF - timedelta(hours=1),
    )
    _land(
        runs,
        "run-other-dataset",
        dataset_name="utility_bills",
        issues=(_issue(),),
        created_at=AS_OF - timedelta(hours=1),
    )

    snapshot = _compute(plane, runs)

    assert snapshot.quality_flags["rejected_runs"] == 1
    assert snapshot.quality_flags["validation_errors"] == 1
    assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED


def test_asset_attributed_run_without_run_metadata_stays_unknown(plane) -> None:
    _lineage(plane, "run-1", source_system=None, row_count=None)
    _asset_lineage(plane, "run-1", "bank_asset")
    _freshness_config(plane, "bank_asset")

    snapshot = _compute(plane, runs=None)

    assert snapshot.quality_flags["validation_unknown_runs"] == 1
    assert snapshot.quality_flags["completeness_unknown_sources"] == 1
    assert snapshot.confidence_verdict != ConfidenceVerdict.TRUSTWORTHY


# Scheduled configs: the contributing run's landing date gives the period it
# covers (``run_observation``), so a source that has landed its expected
# period reads CURRENT. ``(as_of, landed_at, state)`` per case.
_MONTHLY_CASES = [
    # Landed 2 October: covers September, the expected period on 18 October.
    (datetime(2026, 10, 18, tzinfo=UTC), datetime(2026, 10, 2, tzinfo=UTC), "current"),
    # Landed 20 September: covers August. On 3 October September is due on
    # the 5th (window 3 days), so it is due soon...
    (datetime(2026, 10, 3, tzinfo=UTC), datetime(2026, 9, 20, tzinfo=UTC), "due_soon"),
    # ...and past 8 October it is overdue.
    (datetime(2026, 10, 18, tzinfo=UTC), datetime(2026, 9, 20, tzinfo=UTC), "overdue"),
]
_QUARTERLY_CASES = [
    # Landed 5 October: covers Q3 (through 30 September), expected on 18 October.
    (datetime(2026, 10, 18, tzinfo=UTC), datetime(2026, 10, 5, tzinfo=UTC), "current"),
    # Landed 15 September: covers Q2. Q3 is due 10 December (window 3 days):
    # due soon in November...
    (datetime(2026, 11, 20, tzinfo=UTC), datetime(2026, 9, 15, tzinfo=UTC), "due_soon"),
    # ...and overdue after 13 December.
    (datetime(2026, 12, 20, tzinfo=UTC), datetime(2026, 9, 15, tzinfo=UTC), "overdue"),
]
_PUBLICATION_FRESHNESS = {
    "current": FreshnessState.CURRENT,
    "due_soon": FreshnessState.DUE_SOON,
    "overdue": FreshnessState.STALE,
}


@pytest.mark.parametrize(
    ("frequency", "due_day", "as_of", "landed_at", "expected"),
    [("monthly", 5, *case) for case in _MONTHLY_CASES]
    + [("quarterly", 10, *case) for case in _QUARTERLY_CASES],
)
def test_scheduled_config_reads_state_from_the_period_the_run_landed(
    plane, runs, frequency, due_day, as_of, landed_at, expected
) -> None:
    _promoted(plane, runs, "run-1", "bank_asset", created_at=landed_at)
    _freshness_config(
        plane,
        "bank_asset",
        expected_frequency=frequency,
        due_day_of_month=due_day,
        expected_window_days=3,
    )

    snapshot = compute_and_record_publication_confidence(
        PUBLICATION, plane, None, as_of=as_of, run_metadata_store=runs
    )

    state = snapshot.source_freshness_states["bank_asset"]
    assert state.freshness_state == SourceFreshnessState(expected)
    assert snapshot.freshness_state == _PUBLICATION_FRESHNESS[expected]
    if expected == "current":
        assert snapshot.confidence_verdict == ConfidenceVerdict.TRUSTWORTHY
    else:
        assert snapshot.confidence_verdict != ConfidenceVerdict.TRUSTWORTHY


def test_scheduled_config_without_run_metadata_never_reads_current(plane) -> None:
    """Unknown never upgrades: no run metadata means no landed period."""
    _lineage(plane, "run-1", source_system=None, row_count=None)
    _asset_lineage(plane, "run-1", "bank_asset")
    _freshness_config(plane, "bank_asset", expected_frequency="monthly")

    snapshot = compute_and_record_publication_confidence(
        PUBLICATION,
        plane,
        None,
        as_of=datetime(2026, 10, 18, tzinfo=UTC),
        run_metadata_store=None,
    )

    state = snapshot.source_freshness_states["bank_asset"].freshness_state
    assert state != SourceFreshnessState.CURRENT
    assert snapshot.confidence_verdict != ConfidenceVerdict.TRUSTWORTHY


def test_scheduled_config_ignores_a_run_landed_after_as_of(plane, runs) -> None:
    """A run landed after the assessment date cannot vouch for it."""
    _promoted(
        plane, runs, "run-1", "bank_asset", created_at=datetime(2026, 10, 20, tzinfo=UTC)
    )
    _freshness_config(plane, "bank_asset", expected_frequency="monthly")

    snapshot = compute_and_record_publication_confidence(
        PUBLICATION,
        plane,
        None,
        as_of=datetime(2026, 10, 18, tzinfo=UTC),
        run_metadata_store=runs,
    )

    state = snapshot.source_freshness_states["bank_asset"].freshness_state
    assert state != SourceFreshnessState.CURRENT
