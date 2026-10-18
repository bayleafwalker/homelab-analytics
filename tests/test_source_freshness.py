from __future__ import annotations

from datetime import UTC, date, datetime

from packages.platform.source_freshness import (
    SourceFreshnessRunObservation,
    SourceFreshnessState,
    derive_run_covered_through,
    evaluate_source_freshness,
    run_observation,
)
from packages.storage.ingestion_catalog import SourceFreshnessConfigCreate


def _monthly_config() -> SourceFreshnessConfigCreate:
    return SourceFreshnessConfigCreate(
        source_asset_id="op-common-account",
        acquisition_mode="manual_export",
        expected_frequency="monthly",
        coverage_kind="rolling_period",
        due_day_of_month=5,
        expected_window_days=5,
        freshness_sla_days=40,
        sensitivity_class="financial",
        reminder_channel="dashboard",
        requires_human_action=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_freshness_is_unconfigured_without_config() -> None:
    assessment = evaluate_source_freshness(None, (), as_of=date(2026, 3, 1))

    assert assessment.state == SourceFreshnessState.UNCONFIGURED
    assert assessment.last_ingest_at is None
    assert assessment.next_expected_at is None


def test_freshness_marks_parse_failed_when_latest_run_failed() -> None:
    assessment = evaluate_source_freshness(
        _monthly_config(),
        (
            SourceFreshnessRunObservation(
                status="landed",
                observed_at=datetime(2026, 3, 2, tzinfo=UTC),
                covered_from=date(2026, 2, 1),
                covered_through=date(2026, 2, 28),
            ),
            SourceFreshnessRunObservation(
                status="rejected",
                observed_at=datetime(2026, 3, 3, tzinfo=UTC),
            ),
        ),
        as_of=date(2026, 3, 4),
    )

    assert assessment.state == SourceFreshnessState.PARSE_FAILED
    assert assessment.last_ingest_at == datetime(2026, 3, 3, tzinfo=UTC)


def test_freshness_marks_current_when_latest_success_covers_previous_month() -> None:
    assessment = evaluate_source_freshness(
        _monthly_config(),
        (
            SourceFreshnessRunObservation(
                status="landed",
                observed_at=datetime(2026, 3, 2, tzinfo=UTC),
                covered_from=date(2026, 2, 1),
                covered_through=date(2026, 2, 28),
            ),
        ),
        as_of=date(2026, 3, 3),
    )

    assert assessment.state == SourceFreshnessState.CURRENT
    assert assessment.covered_through == date(2026, 2, 28)
    assert assessment.next_expected_at is not None


def test_freshness_marks_overdue_when_no_ingest_arrived_after_window() -> None:
    assessment = evaluate_source_freshness(
        _monthly_config(),
        (),
        as_of=date(2026, 3, 20),
    )

    assert assessment.state == SourceFreshnessState.OVERDUE
    assert assessment.next_expected_at is not None


def test_freshness_detects_missing_period_gaps_between_successful_runs() -> None:
    assessment = evaluate_source_freshness(
        _monthly_config(),
        (
            SourceFreshnessRunObservation(
                status="landed",
                observed_at=datetime(2026, 2, 1, tzinfo=UTC),
                covered_from=date(2026, 1, 1),
                covered_through=date(2026, 1, 31),
            ),
            SourceFreshnessRunObservation(
                status="landed",
                observed_at=datetime(2026, 4, 1, tzinfo=UTC),
                covered_from=date(2026, 3, 1),
                covered_through=date(2026, 3, 31),
            ),
        ),
        as_of=date(2026, 4, 2),
    )

    assert assessment.state == SourceFreshnessState.MISSING_PERIOD
    assert assessment.detail is not None


# Coverage derived from a run's landing date (``derive_run_covered_through``).


def _config(frequency: str, due_day: int | None = None) -> SourceFreshnessConfigCreate:
    return SourceFreshnessConfigCreate(
        source_asset_id="asset",
        acquisition_mode="manual_export",
        expected_frequency=frequency,
        coverage_kind="rolling_period",
        due_day_of_month=due_day,
        expected_window_days=3,
        freshness_sla_days=40,
        sensitivity_class="financial",
        reminder_channel="dashboard",
        requires_human_action=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_derived_coverage_is_the_last_complete_period_before_landing() -> None:
    landed = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)

    def covered(frequency: str) -> date | None:
        return derive_run_covered_through(
            _config(frequency), status="landed", observed_at=landed
        )

    assert covered("monthly") == date(2026, 9, 30)
    assert covered("quarterly") == date(2026, 9, 30)
    assert covered("annual") == date(2025, 12, 31)
    assert covered("weekly") == date(2026, 10, 5)
    assert covered("ad_hoc") is None


def test_derived_coverage_is_unknown_for_failed_late_or_unconfigured_runs() -> None:
    landed = datetime(2026, 10, 5, tzinfo=UTC)
    monthly = _config("monthly", 5)

    assert derive_run_covered_through(monthly, status="rejected", observed_at=landed) is None
    assert derive_run_covered_through(None, status="landed", observed_at=landed) is None
    assert (
        derive_run_covered_through(
            monthly, status="landed", observed_at=landed, as_of=date(2026, 10, 4)
        )
        is None
    )


def test_run_observation_lets_a_monthly_source_read_current() -> None:
    monthly = _config("monthly", 5)
    observation = run_observation(
        monthly, status="landed", observed_at=datetime(2026, 10, 2, tzinfo=UTC)
    )

    assessment = evaluate_source_freshness(monthly, [observation], as_of=date(2026, 10, 18))

    assert assessment.state == SourceFreshnessState.CURRENT
    assert assessment.covered_through == date(2026, 9, 30)
