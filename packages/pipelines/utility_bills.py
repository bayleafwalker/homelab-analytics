from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from packages.pipelines.normalization import normalize_currency_code, normalize_unit


@dataclass(frozen=True)
class CanonicalUtilityBill:
    meter_id: str
    meter_name: str
    provider: str
    utility_type: str
    location: str | None
    billing_period_start: date
    billing_period_end: date
    billed_amount: Decimal
    currency: str
    billed_quantity: Decimal | None
    usage_unit: str | None
    invoice_date: date | None


def load_canonical_utility_bills(source_path: Path) -> list[CanonicalUtilityBill]:
    return load_canonical_utility_bills_bytes(source_path.read_bytes())


def load_canonical_utility_bills_bytes(
    source_bytes: bytes,
) -> list[CanonicalUtilityBill]:
    reader = csv.DictReader(StringIO(source_bytes.decode("utf-8")))
    result: list[CanonicalUtilityBill] = []

    for row in reader:
        location_raw = (row.get("location") or "").strip()
        quantity_raw = (row.get("billed_quantity") or "").strip()
        usage_unit_raw = (row.get("usage_unit") or "").strip()
        invoice_date_raw = (row.get("invoice_date") or "").strip()
        usage_unit = normalize_unit(usage_unit_raw).value if usage_unit_raw else None

        result.append(
            CanonicalUtilityBill(
                meter_id=row["meter_id"].strip(),
                meter_name=row["meter_name"].strip(),
                provider=(row.get("provider") or "").strip(),
                utility_type=row["utility_type"].strip(),
                location=location_raw or None,
                billing_period_start=date.fromisoformat(
                    row["billing_period_start"].strip()
                ),
                billing_period_end=date.fromisoformat(
                    row["billing_period_end"].strip()
                ),
                billed_amount=Decimal(row["billed_amount"].strip()),
                currency=normalize_currency_code(row["currency"].strip()),
                billed_quantity=Decimal(quantity_raw) if quantity_raw else None,
                usage_unit=usage_unit,
                invoice_date=(
                    date.fromisoformat(invoice_date_raw) if invoice_date_raw else None
                ),
            )
        )

    return result
