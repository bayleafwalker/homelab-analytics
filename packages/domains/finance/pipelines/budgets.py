"""Canonical budget model and CSV loader.

Provides:
- ``CanonicalBudget`` — immutable record representing one budget target.
- ``load_canonical_budgets_bytes`` — parse the landing CSV bytes into canonicals.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO
from pathlib import Path


def build_budget_id(budget_name: str, category_id: str) -> str:
    raw = f"budget|{budget_name.strip().lower()}|{category_id.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class CanonicalBudget:
    budget_id: str
    budget_name: str
    category_id: str  # stable slug matching dim_category.category_id
    period_type: str  # monthly | quarterly | annual
    target_amount: Decimal
    currency: str
    effective_from: str  # ISO date or period label e.g. "2026-01"
    effective_to: str | None  # None = open-ended


def load_canonical_budgets(source_path: Path) -> list[CanonicalBudget]:
    return load_canonical_budgets_bytes(source_path.read_bytes())


def load_canonical_budgets_bytes(source_bytes: bytes) -> list[CanonicalBudget]:
    source_text = source_bytes.decode("utf-8")
    reader = csv.DictReader(StringIO(source_text))
    result: list[CanonicalBudget] = []

    for row in reader:
        budget_name = row["budget_name"].strip()
        category_id = row["category"].strip().lower()  # normalise to slug; CSV column stays "category"
        effective_to_raw = row.get("effective_to", "").strip()

        result.append(
            CanonicalBudget(
                budget_id=build_budget_id(budget_name, category_id),
                budget_name=budget_name,
                category_id=category_id,
                period_type=row.get("period_type", "monthly").strip() or "monthly",
                target_amount=Decimal(row["target_amount"].strip()),
                currency=row["currency"].strip(),
                effective_from=row["effective_from"].strip(),
                effective_to=effective_to_raw or None,
            )
        )

    return result
