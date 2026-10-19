"""Spend heatmap: expense totals folded into a day-of-week x hour matrix.

Built only from the published ``mart_spend_by_weekday_hour`` rows, so the web
Ops Console reads the reporting layer and never transaction facts or landing
payloads.

The matrix is 7 rows (ISO weekday, Monday first) by 24 columns (hour of day)
on the household clock (``HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE``). The mart
stores UTC booking dates and UTC hours; each timed row is converted at read
time, so its local weekday, hour and date (which decides window membership)
follow the zone's offset on that day, DST included. On a spring-forward day
the skipped local hour simply gets nothing; on a fall-back day both UTC hours
that read as the repeated local hour land in it. Zones with a fractional
offset (Asia/Kolkata, +05:30) are placed by the local hour each UTC hour
starts in, since the mart is hour-grained.

Most bank exports record a booking date without a time of day; that spend is
kept out of the hour columns and reported per weekday in ``untimed`` so the
grid never shows date-only purchases as if they happened at midnight.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from packages.shared.household_time import household_zone

SPEND_HEATMAP_PUBLICATIONS = ("mart_spend_by_weekday_hour",)
DEFAULT_WINDOW_DAYS = 28
MAX_WINDOW_DAYS = 366
DAYS = 7
HOURS = 24
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

ZERO = Decimal("0")
CENT = Decimal("0.01")


def _dec(value: Any) -> Decimal:
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT))


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def spend_heatmap_window(end: date, window_days: int) -> tuple[date, date]:
    """Inclusive ``(start, end)`` covering ``window_days`` booking days."""
    return end - timedelta(days=window_days - 1), end


def spend_heatmap_mart_range(end: date, window_days: int) -> tuple[date, date]:
    """UTC booking-date range to read from the mart for a local-date window.

    A local date can start up to 14 hours before or after its UTC date, so one
    day of padding either side covers every zone; ``build_spend_heatmap``
    drops what falls outside the local window.
    """
    start, end = spend_heatmap_window(end, window_days)
    return start - timedelta(days=1), end + timedelta(days=1)


def _local_slot(booked: date, hour: int, zone: ZoneInfo) -> tuple[date, int, int]:
    """(local date, ISO weekday, local hour) of the UTC hour ``booked`` ``hour``:00."""
    local = datetime.combine(booked, time(hour), tzinfo=UTC).astimezone(zone)
    return local.date(), local.isoweekday(), local.hour


def build_spend_heatmap(
    rows: Iterable[Mapping[str, Any]],
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    end: date | None = None,
    currency: str | None = None,
    timezone: str | None = None,
) -> dict[str, Any]:
    """Fold mart rows into the heatmap payload.

    ``timezone`` is the household IANA zone (default UTC). Timed rows are
    re-bucketed onto its clock; date-only rows keep their booking date, which
    has no time of day to convert. ``end`` and the window are local dates.

    ``end`` anchors the window; when omitted the window ends on the newest
    booking date present, so stale data still renders its last ``window_days``
    days and the payload says which days those are. Rows outside the window
    are ignored. An empty or fully sparse window yields an all-zero matrix,
    never an error.
    """
    if window_days < 1 or window_days > MAX_WINDOW_DAYS:
        raise ValueError(f"window_days must be between 1 and {MAX_WINDOW_DAYS}")

    zone = household_zone(timezone)
    zone_name = zone.key
    # (local date, ISO weekday, local hour or None, amount, count)
    slots: list[tuple[date, int, int | None, Decimal, int]] = []
    for row in rows:
        booked = _as_date(row["booked_at"])
        amount = _dec(row.get("total_expense"))
        count = int(row.get("transaction_count") or 0)
        hour = row.get("hour_of_day")
        if hour is None:
            slots.append((booked, int(row["day_of_week"]), None, amount, count))
            continue
        hour_index = int(hour)
        if not 0 <= hour_index < HOURS:
            continue
        local_day, weekday, local_hour = _local_slot(booked, hour_index, zone)
        slots.append((local_day, weekday, local_hour, amount, count))
    data_through = max((slot[0] for slot in slots), default=None)
    window_end = end or data_through
    window_start: date | None = None
    if window_end is not None:
        window_start, window_end = spend_heatmap_window(window_end, window_days)

    cells = [[ZERO] * HOURS for _ in range(DAYS)]
    counts = [[0] * HOURS for _ in range(DAYS)]
    untimed = [ZERO] * DAYS
    untimed_counts = [0] * DAYS
    active_days: set[date] = set()

    for booked, day_of_week, slot_hour, amount, count in slots:
        if window_start is None or window_end is None:
            continue
        if booked < window_start or booked > window_end:
            continue
        if not 1 <= day_of_week <= DAYS:
            continue
        day_index = day_of_week - 1
        active_days.add(booked)
        if slot_hour is None:
            untimed[day_index] += amount
            untimed_counts[day_index] += count
            continue
        cells[day_index][slot_hour] += amount
        counts[day_index][slot_hour] += count

    timed_expense = sum((value for row in cells for value in row), ZERO)
    untimed_expense = sum(untimed, ZERO)
    timed_count = sum(value for row in counts for value in row)
    untimed_count = sum(untimed_counts)
    max_cell = max((value for row in cells for value in row), default=ZERO)
    max_untimed = max(untimed, default=ZERO)

    if timed_count + untimed_count == 0:
        coverage = "empty"
    elif timed_count == 0:
        coverage = "date_only"
    elif untimed_count == 0:
        coverage = "timed"
    else:
        coverage = "mixed"

    return {
        "window_days": window_days,
        "window_start": window_start.isoformat() if window_start else None,
        "window_end": window_end.isoformat() if window_end else None,
        "data_through": data_through.isoformat() if data_through else None,
        "currency": currency,
        "hour_basis": "utc" if zone_name == "UTC" else "local",
        "timezone": zone_name,
        "day_labels": list(DAY_LABELS),
        "cells": [[_money(value) for value in row] for row in cells],
        "counts": counts,
        "untimed": [_money(value) for value in untimed],
        "untimed_counts": untimed_counts,
        "max_cell": _money(max_cell),
        "max_untimed": _money(max_untimed),
        "coverage": coverage,
        "totals": {
            "expense": _money(timed_expense + untimed_expense),
            "timed_expense": _money(timed_expense),
            "untimed_expense": _money(untimed_expense),
            "transaction_count": timed_count + untimed_count,
            "timed_count": timed_count,
            "untimed_count": untimed_count,
            "active_days": len(active_days),
        },
        "publications": list(SPEND_HEATMAP_PUBLICATIONS),
    }
