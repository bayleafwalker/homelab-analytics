"""Freshness state computation for finance source assets."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Protocol, runtime_checkable


class SourceFreshnessState(StrEnum):
    CURRENT = "current"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    MISSING_PERIOD = "missing_period"
    PARSE_FAILED = "parse_failed"
    UNCONFIGURED = "unconfigured"


@runtime_checkable
class SourceFreshnessConfigLike(Protocol):
    acquisition_mode: str
    expected_frequency: str
    coverage_kind: str
    due_day_of_month: int | None
    expected_window_days: int
    freshness_sla_days: int
    sensitivity_class: str
    reminder_channel: str
    requires_human_action: bool


@dataclass(frozen=True)
class SourceFreshnessRunObservation:
    status: str
    observed_at: datetime
    covered_from: date | None = None
    covered_through: date | None = None
    dataset_name: str | None = None


@dataclass(frozen=True)
class SourceFreshnessAssessment:
    state: SourceFreshnessState
    last_ingest_at: datetime | None
    next_expected_at: datetime | None
    covered_from: date | None
    covered_through: date | None
    detail: str | None = None


def evaluate_source_freshness(
    config: SourceFreshnessConfigLike | None,
    observations: Sequence[SourceFreshnessRunObservation],
    *,
    as_of: date | datetime,
) -> SourceFreshnessAssessment:
    if config is None:
        return SourceFreshnessAssessment(
            state=SourceFreshnessState.UNCONFIGURED,
            last_ingest_at=None,
            next_expected_at=None,
            covered_from=None,
            covered_through=None,
            detail="source asset has no freshness config",
        )

    as_of_date = as_of.date() if isinstance(as_of, datetime) else as_of
    ordered = sorted(observations, key=lambda observation: observation.observed_at, reverse=True)
    latest = ordered[0] if ordered else None
    latest_success = _latest_successful_observation(ordered)

    if latest is not None and _is_failure_status(latest.status):
        return SourceFreshnessAssessment(
            state=SourceFreshnessState.PARSE_FAILED,
            last_ingest_at=latest.observed_at,
            next_expected_at=_next_expected_at(config, as_of_date, latest_success),
            covered_from=latest_success.covered_from if latest_success else None,
            covered_through=latest_success.covered_through if latest_success else None,
            detail=f"latest run status is {latest.status}",
        )

    if latest_success is None:
        state = _schedule_based_state(config, as_of_date)
        return SourceFreshnessAssessment(
            state=state,
            last_ingest_at=latest.observed_at if latest is not None else None,
            next_expected_at=_next_expected_at(config, as_of_date, None),
            covered_from=None,
            covered_through=None,
            detail="no successful ingest recorded",
        )

    if _has_coverage_gap(ordered):
        state = SourceFreshnessState.MISSING_PERIOD
        detail = "coverage gap detected between successful ingests"
    else:
        state = _schedule_based_state(config, as_of_date, latest_success)
        detail = None

    return SourceFreshnessAssessment(
        state=state,
        last_ingest_at=latest_success.observed_at,
        next_expected_at=_next_expected_at(config, as_of_date, latest_success),
        covered_from=latest_success.covered_from,
        covered_through=latest_success.covered_through,
        detail=detail,
    )


def _latest_successful_observation(
    observations: Sequence[SourceFreshnessRunObservation],
) -> SourceFreshnessRunObservation | None:
    for observation in observations:
        if _is_success_status(observation.status):
            return observation
    return None


def _is_success_status(status: str) -> bool:
    return status in {"landed", "passed", "success", "completed"}


def _is_failure_status(status: str) -> bool:
    return status in {"rejected", "failed"}


def _schedule_based_state(
    config: SourceFreshnessConfigLike,
    as_of_date: date,
    latest_success: SourceFreshnessRunObservation | None = None,
) -> SourceFreshnessState:
    if config.expected_frequency == "ad_hoc":
        return SourceFreshnessState.CURRENT

    expected_covered_through = _expected_covered_through(config, as_of_date)
    if latest_success is not None and latest_success.covered_through is not None:
        if latest_success.covered_through >= expected_covered_through:
            return SourceFreshnessState.CURRENT

    due_at = _due_date_for_cycle(config, as_of_date)
    window_end = due_at + timedelta(days=config.expected_window_days)
    if as_of_date <= window_end:
        return SourceFreshnessState.DUE_SOON
    return SourceFreshnessState.OVERDUE


def _has_coverage_gap(observations: Sequence[SourceFreshnessRunObservation]) -> bool:
    successful = [
        observation
        for observation in observations
        if _is_success_status(observation.status)
        and observation.covered_from is not None
        and observation.covered_through is not None
    ]
    if len(successful) < 2:
        return False

    successful.sort(key=lambda observation: observation.covered_from or date.min)
    previous = successful[0]
    for current in successful[1:]:
        assert previous.covered_through is not None
        assert current.covered_from is not None
        if current.covered_from > previous.covered_through + timedelta(days=1):
            return True
        if current.covered_through is not None and current.covered_through > previous.covered_through:
            previous = current
    return False


def _next_expected_at(
    config: SourceFreshnessConfigLike,
    as_of_date: date,
    latest_success: SourceFreshnessRunObservation | None,
) -> datetime | None:
    due_date = _due_date_for_cycle(config, as_of_date)
    if latest_success is None:
        return datetime.combine(due_date, datetime.min.time())

    if config.expected_frequency == "monthly":
        next_due = _add_months(due_date, 1)
    elif config.expected_frequency == "quarterly":
        next_due = _add_months(due_date, 3)
    elif config.expected_frequency == "annual":
        next_due = date(due_date.year + 1, due_date.month, min(due_date.day, monthrange(due_date.year + 1, due_date.month)[1]))
    else:
        next_due = due_date + timedelta(days=config.freshness_sla_days)
    return datetime.combine(next_due, datetime.min.time())


def _due_date_for_cycle(config: SourceFreshnessConfigLike, as_of_date: date) -> date:
    if config.expected_frequency == "weekly":
        return as_of_date
    if config.expected_frequency == "quarterly":
        month = ((as_of_date.month - 1) // 3 + 1) * 3
        year = as_of_date.year
        last_day = monthrange(year, month)[1]
        return date(year, month, min(config.due_day_of_month or last_day, last_day))
    if config.expected_frequency == "annual":
        last_day = monthrange(as_of_date.year, 12)[1]
        return date(as_of_date.year, 12, min(config.due_day_of_month or last_day, last_day))
    if config.due_day_of_month is None:
        return as_of_date

    last_day = monthrange(as_of_date.year, as_of_date.month)[1]
    due_day = min(config.due_day_of_month, last_day)
    return date(as_of_date.year, as_of_date.month, due_day)


def _expected_covered_through(
    config: SourceFreshnessConfigLike,
    as_of_date: date,
) -> date:
    if config.expected_frequency == "weekly":
        return as_of_date - timedelta(days=7)
    if config.expected_frequency == "quarterly":
        month = ((as_of_date.month - 1) // 3) * 3
        if month == 0:
            year = as_of_date.year - 1
            month = 12
        else:
            year = as_of_date.year
        return date(year, month, monthrange(year, month)[1])
    if config.expected_frequency == "annual":
        return date(as_of_date.year - 1, 12, 31)
    return _last_day_of_previous_month(as_of_date)


def _last_day_of_previous_month(as_of_date: date) -> date:
    if as_of_date.month == 1:
        return date(as_of_date.year - 1, 12, 31)
    previous_month = as_of_date.month - 1
    return date(as_of_date.year, previous_month, monthrange(as_of_date.year, previous_month)[1])


def _add_months(source_date: date, months: int) -> date:
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, monthrange(year, month)[1])
    return date(year, month, day)
