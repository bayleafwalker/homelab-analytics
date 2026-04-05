"""Dimension and fact definitions for the account-transaction domain.

Provides concrete ``DimensionDefinition`` objects for:
- ``dim_account``   – SCD Type 2 account dimension
- ``dim_counterparty`` – SCD Type 2 counterparty dimension

And helpers to extract dimension rows from canonical landing data.
"""

from __future__ import annotations

from typing import Any

from packages.pipelines.identity_strategy import IdentityStrategy, IdentityTier
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
        # category_id is a FK into dim_category.category_id.
        # Nullable; populated via backfill from the free-text category bridge.
        # The free-text category column is retained for backward compatibility.
        DimensionColumn("category_id", "VARCHAR"),
    ),
)

CURRENT_DIM_ACCOUNT_VIEW = "rpt_current_dim_account"
CURRENT_DIM_COUNTERPARTY_VIEW = "rpt_current_dim_counterparty"

# ---------------------------------------------------------------------------
# Identity strategy
# ---------------------------------------------------------------------------

BANK_TRANSACTION_IDENTITY_STRATEGY = IdentityStrategy(
    strategy_id="bank_transaction_v1",
    tiers=(
        # Tier 1: provider-assigned reference (not yet in schema — reserved for
        # sources that supply a booking reference or archive ID).
        IdentityTier(
            tier=1,
            fields=("account_id", "provider_transaction_ref"),
        ),
        # Tier 2: composite business key available in all current bank CSVs.
        IdentityTier(
            tier=2,
            fields=("booked_at", "account_id", "amount", "currency", "counterparty_name"),
        ),
    ),
    fallback_mode="reject",
)

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

MART_SPEND_BY_CATEGORY_MONTHLY_TABLE = "mart_spend_by_category_monthly"

MART_SPEND_BY_CATEGORY_MONTHLY_COLUMNS: list[tuple[str, str]] = [
    ("booking_month", "VARCHAR NOT NULL"),
    ("counterparty_name", "VARCHAR NOT NULL"),
    ("category", "VARCHAR"),
    ("total_expense", "DECIMAL(18,4) NOT NULL"),
    ("transaction_count", "INTEGER NOT NULL"),
]

MART_RECENT_LARGE_TRANSACTIONS_TABLE = "mart_recent_large_transactions"

MART_RECENT_LARGE_TRANSACTIONS_COLUMNS: list[tuple[str, str]] = [
    ("transaction_id", "VARCHAR NOT NULL"),
    ("booked_at", "DATE NOT NULL"),
    ("booking_month", "VARCHAR NOT NULL"),
    ("account_id", "VARCHAR NOT NULL"),
    ("counterparty_name", "VARCHAR NOT NULL"),
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("description", "VARCHAR"),
    ("direction", "VARCHAR NOT NULL"),
]

MART_ACCOUNT_BALANCE_TREND_TABLE = "mart_account_balance_trend"

MART_ACCOUNT_BALANCE_TREND_COLUMNS: list[tuple[str, str]] = [
    ("booking_month", "VARCHAR NOT NULL"),
    ("account_id", "VARCHAR NOT NULL"),
    ("net_change", "DECIMAL(18,4) NOT NULL"),
    ("cumulative_balance", "DECIMAL(18,4) NOT NULL"),
    ("transaction_count", "INTEGER NOT NULL"),
]

MART_TRANSACTION_ANOMALIES_CURRENT_TABLE = "mart_transaction_anomalies_current"

MART_TRANSACTION_ANOMALIES_CURRENT_COLUMNS: list[tuple[str, str]] = [
    ("transaction_id", "VARCHAR NOT NULL"),
    ("booking_date", "DATE NOT NULL"),
    ("counterparty_name", "VARCHAR NOT NULL"),
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("direction", "VARCHAR NOT NULL"),
    ("anomaly_type", "VARCHAR NOT NULL"),
    ("anomaly_reason", "VARCHAR NOT NULL"),
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
# Immutable evidence layer (PR 2)
# ---------------------------------------------------------------------------

INGEST_BATCH_TABLE = "ingest_batch"

INGEST_BATCH_COLUMNS: list[tuple[str, str]] = [
    ("batch_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),          # links to control-plane ingestion_runs
    ("source_asset_id", "VARCHAR"),
    ("file_sha256", "VARCHAR"),
    ("row_count", "INTEGER NOT NULL"),
    ("landed_at", "TIMESTAMPTZ NOT NULL"),
]

TRANSACTION_OBSERVATION_TABLE = "transaction_observation"

TRANSACTION_OBSERVATION_COLUMNS: list[tuple[str, str]] = [
    ("observation_id", "VARCHAR PRIMARY KEY"),
    ("batch_id", "VARCHAR NOT NULL"),
    ("row_ordinal", "INTEGER NOT NULL"),
    # Identity resolution results (nullable until strategy resolves)
    ("entity_key", "VARCHAR"),
    ("match_tier", "INTEGER"),
    ("confidence", "DECIMAL(5,4)"),
    # Canonical parsed fields (denormalised for direct query)
    ("booked_at", "DATE NOT NULL"),
    ("account_id", "VARCHAR NOT NULL"),
    ("counterparty_name", "VARCHAR NOT NULL"),
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("description", "VARCHAR"),
    # Stable JSON encoding of the row for audit / dedup
    ("normalized_row_json", "VARCHAR NOT NULL"),
    ("observed_at", "TIMESTAMPTZ NOT NULL"),
]

# ---------------------------------------------------------------------------
# Entity + current-projection layer (PR 3)
# ---------------------------------------------------------------------------

TRANSACTION_ENTITY_TABLE = "transaction_entity"

TRANSACTION_ENTITY_COLUMNS: list[tuple[str, str]] = [
    ("entity_key", "VARCHAR PRIMARY KEY"),
    # Lifecycle status: active | superseded | reversed | ambiguous
    ("status", "VARCHAR NOT NULL DEFAULT 'active'"),
    ("first_seen_batch_id", "VARCHAR NOT NULL"),
    ("first_seen_at", "TIMESTAMPTZ NOT NULL"),
    ("last_seen_batch_id", "VARCHAR NOT NULL"),
    ("last_seen_at", "TIMESTAMPTZ NOT NULL"),
    ("observation_count", "INTEGER NOT NULL DEFAULT 1"),
    # Points to the "best" (richest / most recent) observation
    ("current_observation_id", "VARCHAR NOT NULL"),
]

FACT_TRANSACTION_CURRENT_TABLE = "fact_transaction_current"

FACT_TRANSACTION_CURRENT_COLUMNS: list[tuple[str, str]] = [
    ("entity_key", "VARCHAR PRIMARY KEY"),
    ("current_observation_id", "VARCHAR NOT NULL"),
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
    ("reconciled_at", "TIMESTAMPTZ NOT NULL"),
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


def extract_counterparties(
    rows: list[dict[str, Any]],
    *,
    category_resolver: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    """Derive distinct dim_counterparty rows from transaction dicts.

    If *category_resolver* is provided (a mapping of counterparty_name → category),
    the resolved category is assigned. Otherwise ``category`` is left as None.
    """
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["counterparty_name"]
        if name not in seen:
            category = (category_resolver or {}).get(name)
            seen[name] = {"counterparty_name": name, "category": category, "category_id": None}
    return list(seen.values())
