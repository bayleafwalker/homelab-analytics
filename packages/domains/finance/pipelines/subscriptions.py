"""Canonical subscription model and CSV loader.

Provides:
- ``CanonicalSubscription`` — immutable record representing one subscription contract.
- ``load_canonical_subscriptions_bytes`` — parse the landing CSV bytes into canonicals.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from packages.pipelines.contracts import build_contract_id


@dataclass(frozen=True)
class CanonicalSubscription:
    contract_id: str
    service_name: str
    provider: str
    billing_cycle: str       # monthly | annual | weekly | one-off
    amount: Decimal
    currency: str
    start_date: date
    end_date: date | None    # None = still active

    @property
    def monthly_equivalent(self) -> Decimal:
        """Normalise the charge to a per-month amount."""
        cycle = self.billing_cycle.lower()
        if cycle == "monthly":
            return self.amount
        if cycle == "annual":
            return (self.amount / 12).quantize(Decimal("0.0001"))
        if cycle == "weekly":
            return (self.amount * 52 / 12).quantize(Decimal("0.0001"))
        # Fallback — treat as monthly
        return self.amount


def load_canonical_subscriptions(source_path: Path) -> list[CanonicalSubscription]:
    return load_canonical_subscriptions_bytes(source_path.read_bytes())


def load_canonical_subscriptions_bytes(source_bytes: bytes) -> list[CanonicalSubscription]:
    source_text = source_bytes.decode("utf-8")
    reader = csv.DictReader(StringIO(source_text))
    result: list[CanonicalSubscription] = []

    for row in reader:
        end_date_raw = row.get("end_date", "").strip()
        end_date = date.fromisoformat(end_date_raw) if end_date_raw else None

        result.append(
            CanonicalSubscription(
                contract_id=build_contract_id(
                    row["service_name"].strip(),
                    row["provider"].strip(),
                    "subscription",
                ),
                service_name=row["service_name"].strip(),
                provider=row["provider"].strip(),
                billing_cycle=row.get("billing_cycle", "monthly").strip() or "monthly",
                amount=Decimal(row["amount"].strip()),
                currency=row["currency"].strip(),
                start_date=date.fromisoformat(row["start_date"].strip()),
                end_date=end_date,
            )
        )

    return result
