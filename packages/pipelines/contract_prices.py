"""Canonical contract pricing model and CSV loader."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from packages.pipelines.contracts import build_contract_id


@dataclass(frozen=True)
class CanonicalContractPrice:
    contract_id: str
    contract_name: str
    provider: str
    contract_type: str
    price_component: str
    billing_cycle: str
    unit_price: Decimal
    currency: str
    quantity_unit: str | None
    valid_from: date
    valid_to: date | None


def load_canonical_contract_prices(source_path: Path) -> list[CanonicalContractPrice]:
    return load_canonical_contract_prices_bytes(source_path.read_bytes())


def load_canonical_contract_prices_bytes(
    source_bytes: bytes,
) -> list[CanonicalContractPrice]:
    reader = csv.DictReader(StringIO(source_bytes.decode("utf-8")))
    result: list[CanonicalContractPrice] = []

    for row in reader:
        contract_name = row["contract_name"].strip()
        provider = row["provider"].strip()
        contract_type = row.get("contract_type", "general").strip() or "general"
        valid_to_raw = (row.get("valid_to") or "").strip()
        quantity_unit_raw = (row.get("quantity_unit") or "").strip()

        result.append(
            CanonicalContractPrice(
                contract_id=build_contract_id(contract_name, provider, contract_type),
                contract_name=contract_name,
                provider=provider,
                contract_type=contract_type,
                price_component=row.get("price_component", "base").strip() or "base",
                billing_cycle=row.get("billing_cycle", "monthly").strip() or "monthly",
                unit_price=Decimal(row["unit_price"].strip()),
                currency=row["currency"].strip(),
                quantity_unit=quantity_unit_raw or None,
                valid_from=date.fromisoformat(row["valid_from"].strip()),
                valid_to=date.fromisoformat(valid_to_raw) if valid_to_raw else None,
            )
        )

    return result
