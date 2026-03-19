"""Dimension and fact definitions for the subscription / recurring-services domain.

Provides concrete ``DimensionDefinition`` objects for:
- ``dim_category``  – SCD Type 2 shared category dimension (used across domains)
- ``dim_contract``  – SCD Type 2 generic contract dimension reused by subscriptions
  and contract-pricing domains

And fact / mart table schemas:
- ``fact_subscription_charge``   – one row per tracked subscription registration
- ``mart_subscription_summary``  – active subscription rollup with monthly equivalents
"""

from __future__ import annotations

import hashlib
from typing import Any

from packages.pipelines.contracts import build_contract_id
from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

# ---------------------------------------------------------------------------
# Shared dimension: dim_category
# ---------------------------------------------------------------------------

DIM_CATEGORY = DimensionDefinition(
    table_name="dim_category",
    natural_key_columns=("category_id",),
    attribute_columns=(
        DimensionColumn("name", "VARCHAR"),
        DimensionColumn("type", "VARCHAR"),           # income | expense | transfer | subscription
        DimensionColumn("parent_category_id", "VARCHAR"),
    ),
)

CURRENT_DIM_CATEGORY_VIEW = "rpt_current_dim_category"

# ---------------------------------------------------------------------------
# Shared contract dimension: dim_contract
# ---------------------------------------------------------------------------

DIM_CONTRACT = DimensionDefinition(
    table_name="dim_contract",
    natural_key_columns=("contract_id",),
    attribute_columns=(
        DimensionColumn("contract_name", "VARCHAR"),
        DimensionColumn("provider", "VARCHAR"),
        DimensionColumn("contract_type", "VARCHAR"),
        DimensionColumn("currency", "VARCHAR"),
        DimensionColumn("start_date", "DATE"),
        DimensionColumn("end_date", "DATE"),
    ),
)

CURRENT_DIM_CONTRACT_VIEW = "rpt_current_dim_contract"

# ---------------------------------------------------------------------------
# Fact table: fact_subscription_charge
# One row per subscription registration (contract + charge details).
# ---------------------------------------------------------------------------

FACT_SUBSCRIPTION_CHARGE_TABLE = "fact_subscription_charge"

FACT_SUBSCRIPTION_CHARGE_COLUMNS: list[tuple[str, str]] = [
    ("charge_id", "VARCHAR PRIMARY KEY"),
    ("contract_id", "VARCHAR NOT NULL"),
    ("contract_name", "VARCHAR NOT NULL"),
    ("provider", "VARCHAR NOT NULL"),
    ("billing_cycle", "VARCHAR NOT NULL"),
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("start_date", "DATE NOT NULL"),
    ("end_date", "DATE"),
    ("run_id", "VARCHAR"),
]

# ---------------------------------------------------------------------------
# Mart table: mart_subscription_summary
# Rebuilt from fact_subscription_charge with normalised monthly equivalents
# and an active/inactive status flag.
# ---------------------------------------------------------------------------

MART_SUBSCRIPTION_SUMMARY_TABLE = "mart_subscription_summary"

MART_SUBSCRIPTION_SUMMARY_COLUMNS: list[tuple[str, str]] = [
    ("contract_id", "VARCHAR NOT NULL"),
    ("contract_name", "VARCHAR NOT NULL"),
    ("provider", "VARCHAR NOT NULL"),
    ("billing_cycle", "VARCHAR NOT NULL"),
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("start_date", "DATE NOT NULL"),
    ("end_date", "DATE"),
    ("monthly_equivalent", "DECIMAL(18,4) NOT NULL"),
    ("status", "VARCHAR NOT NULL"),   # active | inactive
]

MART_UPCOMING_FIXED_COSTS_30D_TABLE = "mart_upcoming_fixed_costs_30d"

MART_UPCOMING_FIXED_COSTS_30D_COLUMNS: list[tuple[str, str]] = [
    ("contract_name", "VARCHAR NOT NULL"),
    ("provider", "VARCHAR NOT NULL"),
    ("frequency", "VARCHAR NOT NULL"),       # billing_cycle of source subscription
    ("expected_amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("expected_date", "DATE NOT NULL"),
    ("confidence", "VARCHAR NOT NULL"),      # high | estimated
]

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def extract_contracts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive distinct dim_contract rows from canonical subscription dicts.

    Deduplicates by ``contract_id`` — last writer wins for attribute columns,
    which is fine because SCD-2 will track attribute changes.
    """
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        contract_id = row.get("contract_id") or build_contract_id(
            row["service_name"],
            row.get("provider", ""),
            "subscription",
        )
        seen[contract_id] = {
            "contract_id": contract_id,
            "contract_name": row["service_name"],
            "provider": row.get("provider", ""),
            "contract_type": row.get("contract_type", "subscription"),
            "currency": row.get("currency", ""),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
        }
    return list(seen.values())


def subscription_charge_id(
    service_name: str,
    billing_cycle: str,
    start_date: object,
) -> str:
    """Deterministic charge_id derived from content fields."""
    raw = f"{service_name}|{billing_cycle}|{start_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
