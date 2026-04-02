from __future__ import annotations

from datetime import UTC, date, datetime

from packages.platform.source_freshness import (
    SourceFreshnessRunObservation,
    SourceFreshnessState,
    evaluate_source_freshness,
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
