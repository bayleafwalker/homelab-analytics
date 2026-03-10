from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from packages.pipelines.normalization import normalize_unit


@dataclass(frozen=True)
class CanonicalUtilityUsage:
    meter_id: str
    meter_name: str
    utility_type: str
    location: str | None
    usage_start: date
    usage_end: date
    usage_quantity: Decimal
    usage_unit: str
    reading_source: str | None


def load_canonical_utility_usage(source_path: Path) -> list[CanonicalUtilityUsage]:
    return load_canonical_utility_usage_bytes(source_path.read_bytes())


def load_canonical_utility_usage_bytes(
    source_bytes: bytes,
) -> list[CanonicalUtilityUsage]:
    reader = csv.DictReader(StringIO(source_bytes.decode("utf-8")))
    result: list[CanonicalUtilityUsage] = []

    for row in reader:
        location_raw = (row.get("location") or "").strip()
        reading_source_raw = (row.get("reading_source") or "").strip()
        usage_unit = normalize_unit(row["usage_unit"].strip()).value

        result.append(
            CanonicalUtilityUsage(
                meter_id=row["meter_id"].strip(),
                meter_name=row["meter_name"].strip(),
                utility_type=row["utility_type"].strip(),
                location=location_raw or None,
                usage_start=date.fromisoformat(row["usage_start"].strip()),
                usage_end=date.fromisoformat(row["usage_end"].strip()),
                usage_quantity=Decimal(row["usage_quantity"].strip()),
                usage_unit=usage_unit,
                reading_source=reading_source_raw or None,
            )
        )

    return result
