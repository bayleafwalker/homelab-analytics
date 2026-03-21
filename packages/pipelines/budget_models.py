"""Dimension, fact, and mart definitions for the budget domain.

Provides:
- ``DIM_BUDGET``   — SCD Type 2 budget dimension
- ``fact_budget_target``   — one row per budget target per period
- ``mart_budget_variance`` — budget vs actual by category and period
- ``mart_budget_progress_current`` — current month budget progress
"""

from __future__ import annotations

import hashlib
from typing import Any

from packages.pipelines.budgets import build_budget_id
from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

# ---------------------------------------------------------------------------
# Dimension: dim_budget
# ---------------------------------------------------------------------------

DIM_BUDGET = DimensionDefinition(
    table_name="dim_budget",
    natural_key_columns=("budget_id",),
    attribute_columns=(
        DimensionColumn("budget_name", "VARCHAR"),
        DimensionColumn("category_id", "VARCHAR"),
        DimensionColumn("period_type", "VARCHAR"),  # monthly | quarterly | annual
        DimensionColumn("currency", "VARCHAR"),
    ),
)

CURRENT_DIM_BUDGET_VIEW = "rpt_current_dim_budget"

# ---------------------------------------------------------------------------
# Fact table: fact_budget_target
# ---------------------------------------------------------------------------

FACT_BUDGET_TARGET_TABLE = "fact_budget_target"

FACT_BUDGET_TARGET_COLUMNS: list[tuple[str, str]] = [
    ("target_id", "VARCHAR PRIMARY KEY"),
    ("budget_id", "VARCHAR NOT NULL"),
    ("budget_name", "VARCHAR NOT NULL"),
    ("category_id", "VARCHAR NOT NULL"),
    ("period_type", "VARCHAR NOT NULL"),
    ("period_label", "VARCHAR NOT NULL"),  # e.g. "2026-01" or "2026-Q1"
    ("target_amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("run_id", "VARCHAR"),
]

# ---------------------------------------------------------------------------
# Mart: mart_budget_variance
# ---------------------------------------------------------------------------

MART_BUDGET_VARIANCE_TABLE = "mart_budget_variance"

MART_BUDGET_VARIANCE_COLUMNS: list[tuple[str, str]] = [
    ("budget_name", "VARCHAR NOT NULL"),
    ("category_id", "VARCHAR NOT NULL"),
    ("period_label", "VARCHAR NOT NULL"),
    ("target_amount", "DECIMAL(18,4) NOT NULL"),
    ("actual_amount", "DECIMAL(18,4) NOT NULL"),
    ("variance", "DECIMAL(18,4) NOT NULL"),
    ("variance_pct", "DECIMAL(18,4)"),
    ("status", "VARCHAR NOT NULL"),  # under_budget | on_budget | over_budget
    ("currency", "VARCHAR NOT NULL"),
]

# ---------------------------------------------------------------------------
# Mart: mart_budget_progress_current
# ---------------------------------------------------------------------------

MART_BUDGET_PROGRESS_CURRENT_TABLE = "mart_budget_progress_current"

MART_BUDGET_PROGRESS_CURRENT_COLUMNS: list[tuple[str, str]] = [
    ("budget_name", "VARCHAR NOT NULL"),
    ("category_id", "VARCHAR NOT NULL"),
    ("target_amount", "DECIMAL(18,4) NOT NULL"),
    ("spent_amount", "DECIMAL(18,4) NOT NULL"),
    ("remaining", "DECIMAL(18,4) NOT NULL"),
    ("utilization_pct", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
]

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def extract_budgets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive distinct dim_budget rows from canonical budget dicts."""
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        bid = row.get("budget_id") or build_budget_id(
            row["budget_name"], row["category_id"],
        )
        seen[bid] = {
            "budget_id": bid,
            "budget_name": row["budget_name"],
            "category_id": row["category_id"],
            "period_type": row.get("period_type", "monthly"),
            "currency": row.get("currency", ""),
        }
    return list(seen.values())


def budget_target_id(
    budget_name: str,
    category_id: str,
    period_label: str,
) -> str:
    """Deterministic target_id derived from content fields."""
    raw = f"{budget_name}|{category_id}|{period_label}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
