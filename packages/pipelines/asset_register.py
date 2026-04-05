from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path


@dataclass(frozen=True)
class CanonicalAssetRegister:
    asset_name: str
    asset_type: str
    purchase_date: date
    purchase_price: Decimal
    currency: str
    location: str


def load_canonical_asset_register(source_path: Path) -> list[CanonicalAssetRegister]:
    return load_canonical_asset_register_bytes(source_path.read_bytes())


def load_canonical_asset_register_bytes(
    source_bytes: bytes,
) -> list[CanonicalAssetRegister]:
    reader = csv.DictReader(StringIO(source_bytes.decode("utf-8")))
    result: list[CanonicalAssetRegister] = []

    for row in reader:
        result.append(
            CanonicalAssetRegister(
                asset_name=row["asset_name"].strip(),
                asset_type=row.get("asset_type", "unknown").strip() or "unknown",
                purchase_date=date.fromisoformat(row["purchase_date"].strip()),
                purchase_price=Decimal(row["purchase_price"].strip()),
                currency=row["currency"].strip(),
                location=row["location"].strip(),
            )
        )

    return result
