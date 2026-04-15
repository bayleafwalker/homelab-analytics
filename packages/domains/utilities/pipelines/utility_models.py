from __future__ import annotations

import hashlib
from typing import Any

from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

KNOWN_UTILITY_TYPES: frozenset[str] = frozenset({"electricity", "gas", "water"})

DIM_METER = DimensionDefinition(
    table_name="dim_meter",
    natural_key_columns=("meter_id",),
    attribute_columns=(
        DimensionColumn("meter_name", "VARCHAR"),
        DimensionColumn("utility_type", "VARCHAR"),
        DimensionColumn("location", "VARCHAR"),
        DimensionColumn("default_unit", "VARCHAR"),
    ),
)

CURRENT_DIM_METER_VIEW = "rpt_current_dim_meter"

FACT_UTILITY_USAGE_TABLE = "fact_utility_usage"

FACT_UTILITY_USAGE_COLUMNS: list[tuple[str, str]] = [
    ("usage_id", "VARCHAR PRIMARY KEY"),
    ("meter_id", "VARCHAR NOT NULL"),
    ("meter_name", "VARCHAR NOT NULL"),
    ("utility_type", "VARCHAR NOT NULL"),
    ("usage_start", "DATE NOT NULL"),
    ("usage_end", "DATE NOT NULL"),
    ("usage_quantity", "DECIMAL(18,4) NOT NULL"),
    ("usage_unit", "VARCHAR NOT NULL"),
    ("reading_source", "VARCHAR"),
    ("run_id", "VARCHAR"),
]

FACT_BILL_TABLE = "fact_bill"

FACT_BILL_COLUMNS: list[tuple[str, str]] = [
    ("bill_id", "VARCHAR PRIMARY KEY"),
    ("meter_id", "VARCHAR NOT NULL"),
    ("meter_name", "VARCHAR NOT NULL"),
    ("provider", "VARCHAR"),
    ("utility_type", "VARCHAR NOT NULL"),
    ("billing_period_start", "DATE NOT NULL"),
    ("billing_period_end", "DATE NOT NULL"),
    ("billed_amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("billed_quantity", "DECIMAL(18,4)"),
    ("usage_unit", "VARCHAR"),
    ("invoice_date", "DATE"),
    ("run_id", "VARCHAR"),
]

MART_UTILITY_COST_SUMMARY_TABLE = "mart_utility_cost_summary"

MART_UTILITY_COST_SUMMARY_COLUMNS: list[tuple[str, str]] = [
    ("period_start", "DATE NOT NULL"),
    ("period_end", "DATE NOT NULL"),
    ("period_day", "DATE NOT NULL"),
    ("period_month", "VARCHAR NOT NULL"),
    ("meter_id", "VARCHAR NOT NULL"),
    ("meter_name", "VARCHAR NOT NULL"),
    ("utility_type", "VARCHAR NOT NULL"),
    ("usage_quantity", "DECIMAL(18,4) NOT NULL"),
    ("usage_unit", "VARCHAR"),
    ("billed_amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR"),
    ("unit_cost", "DECIMAL(18,4)"),
    ("bill_count", "INTEGER NOT NULL"),
    ("usage_record_count", "INTEGER NOT NULL"),
    ("coverage_status", "VARCHAR NOT NULL"),
]

MART_UTILITY_COST_TREND_MONTHLY_TABLE = "mart_utility_cost_trend_monthly"

MART_UTILITY_COST_TREND_MONTHLY_COLUMNS: list[tuple[str, str]] = [
    ("billing_month", "VARCHAR NOT NULL"),
    ("utility_type", "VARCHAR NOT NULL"),
    ("total_cost", "DECIMAL(18,4) NOT NULL"),
    ("usage_amount", "DECIMAL(18,4) NOT NULL"),
    ("unit_price_effective", "DECIMAL(18,4)"),
    ("currency", "VARCHAR"),
    ("meter_count", "INTEGER NOT NULL"),
]

MART_USAGE_VS_PRICE_SUMMARY_TABLE = "mart_usage_vs_price_summary"

MART_USAGE_VS_PRICE_SUMMARY_COLUMNS: list[tuple[str, str]] = [
    ("utility_type", "VARCHAR NOT NULL"),
    ("period", "VARCHAR NOT NULL"),
    ("usage_change_pct", "DECIMAL(18,4)"),
    ("price_change_pct", "DECIMAL(18,4)"),
    ("cost_change_pct", "DECIMAL(18,4)"),
    ("dominant_driver", "VARCHAR"),   # price | usage | unknown
]

MART_CONTRACT_REVIEW_CANDIDATES_TABLE = "mart_contract_review_candidates"

MART_CONTRACT_REVIEW_CANDIDATES_COLUMNS: list[tuple[str, str]] = [
    ("contract_id", "VARCHAR NOT NULL"),
    ("provider", "VARCHAR NOT NULL"),
    ("utility_type", "VARCHAR NOT NULL"),
    ("reason", "VARCHAR NOT NULL"),
    ("score", "INTEGER NOT NULL"),
    ("current_price", "DECIMAL(18,4) NOT NULL"),
    ("market_reference", "DECIMAL(18,4)"),
    ("currency", "VARCHAR NOT NULL"),
]

MART_CONTRACT_RENEWAL_WATCHLIST_TABLE = "mart_contract_renewal_watchlist"

MART_CONTRACT_RENEWAL_WATCHLIST_COLUMNS: list[tuple[str, str]] = [
    ("contract_id", "VARCHAR NOT NULL"),
    ("contract_name", "VARCHAR NOT NULL"),
    ("provider", "VARCHAR NOT NULL"),
    ("utility_type", "VARCHAR NOT NULL"),
    ("renewal_date", "DATE NOT NULL"),
    ("days_until_renewal", "INTEGER NOT NULL"),
    ("current_price", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("contract_duration_days", "INTEGER"),
]


def extract_meters_from_usage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        seen[row["meter_id"]] = {
            "meter_id": row["meter_id"],
            "meter_name": row["meter_name"],
            "utility_type": row["utility_type"],
            "location": row.get("location"),
            "default_unit": row.get("usage_unit"),
        }
    return list(seen.values())


def extract_meters_from_bills(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        seen[row["meter_id"]] = {
            "meter_id": row["meter_id"],
            "meter_name": row["meter_name"],
            "utility_type": row["utility_type"],
            "location": row.get("location"),
            "default_unit": row.get("usage_unit"),
        }
    return list(seen.values())


def utility_usage_id(
    meter_id: str,
    usage_start: object,
    usage_end: object,
    usage_quantity: object,
) -> str:
    raw = f"{meter_id}|{usage_start}|{usage_end}|{usage_quantity}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def utility_bill_id(
    meter_id: str,
    billing_period_start: object,
    billing_period_end: object,
    provider: str,
    billed_amount: object,
) -> str:
    raw = f"{meter_id}|{billing_period_start}|{billing_period_end}|{provider}|{billed_amount}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
