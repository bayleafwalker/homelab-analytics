"""Dimension and fact definitions for the account-transaction domain.

Provides concrete ``DimensionDefinition`` objects for:
- ``dim_account``   – SCD Type 2 account dimension
- ``dim_counterparty`` – SCD Type 2 counterparty dimension

And helpers to extract dimension rows from canonical landing data.
"""

from __future__ import annotations

from typing import Any

from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------

DIM_ACCOUNT = DimensionDefinition(
    table_name="dim_account",
    natural_key_columns=("account_id",),
    attribute_columns=(
        DimensionColumn("currency", "VARCHAR"),
    ),
)

DIM_COUNTERPARTY = DimensionDefinition(
    table_name="dim_counterparty",
    natural_key_columns=("counterparty_name",),
    attribute_columns=(
        DimensionColumn("category", "VARCHAR"),
    ),
)

CURRENT_DIM_ACCOUNT_VIEW = "rpt_current_dim_account"
CURRENT_DIM_COUNTERPARTY_VIEW = "rpt_current_dim_counterparty"

# ---------------------------------------------------------------------------
# Fact table schema
# ---------------------------------------------------------------------------

FACT_TRANSACTION_TABLE = "fact_transaction"

FACT_TRANSACTION_COLUMNS: list[tuple[str, str]] = [
    ("transaction_id", "VARCHAR PRIMARY KEY"),
    ("booked_at", "DATE NOT NULL"),
    ("booked_at_utc", "TIMESTAMPTZ NOT NULL"),
    ("booking_month", "VARCHAR NOT NULL"),
    ("account_id", "VARCHAR NOT NULL"),
    ("counterparty_name", "VARCHAR NOT NULL"),
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("normalized_currency", "VARCHAR NOT NULL"),
    ("description", "VARCHAR"),
    ("direction", "VARCHAR NOT NULL"),
    ("run_id", "VARCHAR"),
]

# ---------------------------------------------------------------------------
# Mart table schema
# ---------------------------------------------------------------------------

MART_MONTHLY_CASHFLOW_TABLE = "mart_monthly_cashflow"

MART_MONTHLY_CASHFLOW_COLUMNS: list[tuple[str, str]] = [
    ("booking_month", "VARCHAR NOT NULL"),
    ("income", "DECIMAL(18,4) NOT NULL"),
    ("expense", "DECIMAL(18,4) NOT NULL"),
    ("net", "DECIMAL(18,4) NOT NULL"),
    ("transaction_count", "INTEGER NOT NULL"),
]

MART_CASHFLOW_BY_COUNTERPARTY_TABLE = "mart_monthly_cashflow_by_counterparty"

MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS: list[tuple[str, str]] = [
    ("booking_month", "VARCHAR NOT NULL"),
    ("counterparty_name", "VARCHAR NOT NULL"),
    ("income", "DECIMAL(18,4) NOT NULL"),
    ("expense", "DECIMAL(18,4) NOT NULL"),
    ("net", "DECIMAL(18,4) NOT NULL"),
    ("transaction_count", "INTEGER NOT NULL"),
]

TRANSFORMATION_AUDIT_TABLE = "transformation_audit"

TRANSFORMATION_AUDIT_COLUMNS: list[tuple[str, str]] = [
    ("audit_id", "VARCHAR PRIMARY KEY"),
    ("input_run_id", "VARCHAR"),
    ("started_at", "TIMESTAMPTZ NOT NULL"),
    ("completed_at", "TIMESTAMPTZ NOT NULL"),
    ("duration_ms", "INTEGER NOT NULL"),
    ("fact_rows", "INTEGER NOT NULL"),
    ("accounts_upserted", "INTEGER NOT NULL"),
    ("counterparties_upserted", "INTEGER NOT NULL"),
]

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def extract_accounts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive distinct dim_account rows from transaction dicts.

    Each row must contain ``account_id`` and ``currency``.
    Returns deduplicated rows keyed by ``account_id``.
    """
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        aid = row["account_id"]
        if aid not in seen:
            seen[aid] = {"account_id": aid, "currency": row.get("currency", "")}
    return list(seen.values())


def extract_counterparties(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive distinct dim_counterparty rows from transaction dicts.

    ``category`` is left empty (to be enriched later).
    """
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["counterparty_name"]
        if name not in seen:
            seen[name] = {"counterparty_name": name, "category": None}
    return list(seen.values())
