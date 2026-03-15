from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def next_cron_occurrence(
    cron_expression: str,
    *,
    timezone: str,
    after: datetime,
) -> datetime:
    minute_field, hour_field, day_field, month_field, weekday_field = _parse_cron(
        cron_expression
    )
    zone = ZoneInfo(timezone)
    localized = after.astimezone(zone).replace(second=0, microsecond=0)
    candidate = localized + timedelta(minutes=1)

    deadline = candidate + timedelta(days=366)
    while candidate <= deadline:
        if (
            candidate.minute in minute_field
            and candidate.hour in hour_field
            and candidate.day in day_field
            and candidate.month in month_field
            and candidate.weekday() in weekday_field
        ):
            return candidate.astimezone(UTC)
        candidate += timedelta(minutes=1)

    raise ValueError(f"Unable to compute next cron occurrence for {cron_expression!r}")


def _parse_cron(expression: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError(
            "cron_expression must use five fields: minute hour day month weekday"
        )
    return (
        _parse_field(parts[0], 0, 59),
        _parse_field(parts[1], 0, 23),
        _parse_field(parts[2], 1, 31),
        _parse_field(parts[3], 1, 12),
        _parse_field(parts[4], 0, 6),
    )


def _parse_field(value: str, start: int, end: int) -> set[int]:
    if value == "*":
        return set(range(start, end + 1))
    values: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if part.startswith("*/"):
            step = int(part[2:])
            values.update(range(start, end + 1, step))
            continue
        parsed = int(part)
        if parsed < start or parsed > end:
            raise ValueError(f"Cron field value out of range: {part!r}")
        values.add(parsed)
    if not values:
        raise ValueError(f"Invalid cron field: {value!r}")
    return values
