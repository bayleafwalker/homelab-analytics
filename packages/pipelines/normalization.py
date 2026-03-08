from __future__ import annotations

from datetime import date, datetime, time, timezone
from enum import StrEnum


class MeasurementUnit(StrEnum):
    KWH = "kwh"
    LITER = "liter"


def normalize_timestamp_utc(
    value: str | date | datetime,
    *,
    default_timezone=timezone.utc,
) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("Timestamp value cannot be empty.")
        if "T" in raw or " " in raw:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.combine(date.fromisoformat(raw), time.min)
    else:
        raise TypeError(f"Unsupported timestamp value: {value!r}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_timezone)
    return dt.astimezone(timezone.utc)


def normalize_currency_code(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError(f"Invalid ISO currency code: {value!r}")
    return normalized


def normalize_unit(value: str) -> MeasurementUnit:
    normalized = value.strip().lower()
    aliases = {
        "kwh": MeasurementUnit.KWH,
        "kilowatt_hour": MeasurementUnit.KWH,
        "kilowatt_hours": MeasurementUnit.KWH,
        "liter": MeasurementUnit.LITER,
        "liters": MeasurementUnit.LITER,
        "litre": MeasurementUnit.LITER,
        "litres": MeasurementUnit.LITER,
        "l": MeasurementUnit.LITER,
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported unit value: {value!r}")
    return aliases[normalized]
