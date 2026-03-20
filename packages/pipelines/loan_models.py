"""Dimension, fact, and mart definitions for the loan domain."""

from __future__ import annotations

import hashlib

from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

# ---------------------------------------------------------------------------
# Dimension: dim_loan
# ---------------------------------------------------------------------------

DIM_LOAN = DimensionDefinition(
    table_name="dim_loan",
    natural_key_columns=("loan_id",),
    attribute_columns=(
        DimensionColumn("loan_name", "VARCHAR"),
        DimensionColumn("lender", "VARCHAR"),
        DimensionColumn("loan_type", "VARCHAR"),   # mortgage | personal | auto
        DimensionColumn("currency", "VARCHAR"),
        DimensionColumn("principal", "DECIMAL(18,4)"),
        DimensionColumn("annual_rate", "DECIMAL(18,6)"),
        DimensionColumn("term_months", "INTEGER"),
        DimensionColumn("start_date", "DATE"),
        DimensionColumn("payment_frequency", "VARCHAR"),  # monthly | fortnightly | weekly
    ),
)

CURRENT_DIM_LOAN_VIEW = "rpt_current_dim_loan"

# ---------------------------------------------------------------------------
# Fact table: fact_loan_repayment
# ---------------------------------------------------------------------------

FACT_LOAN_REPAYMENT_TABLE = "fact_loan_repayment"

FACT_LOAN_REPAYMENT_COLUMNS: list[tuple[str, str]] = [
    ("repayment_id", "VARCHAR PRIMARY KEY"),
    ("loan_id", "VARCHAR NOT NULL"),
    ("repayment_date", "DATE NOT NULL"),
    ("repayment_month", "VARCHAR NOT NULL"),   # YYYY-MM
    ("payment_amount", "DECIMAL(18,4) NOT NULL"),
    ("principal_portion", "DECIMAL(18,4)"),
    ("interest_portion", "DECIMAL(18,4)"),
    ("extra_amount", "DECIMAL(18,4)"),
    ("currency", "VARCHAR NOT NULL"),
    ("run_id", "VARCHAR"),
]

# ---------------------------------------------------------------------------
# Mart: mart_loan_schedule_projected
# ---------------------------------------------------------------------------

MART_LOAN_SCHEDULE_PROJECTED_TABLE = "mart_loan_schedule_projected"

MART_LOAN_SCHEDULE_PROJECTED_COLUMNS: list[tuple[str, str]] = [
    ("loan_id", "VARCHAR NOT NULL"),
    ("loan_name", "VARCHAR NOT NULL"),
    ("period", "INTEGER NOT NULL"),
    ("payment_date", "DATE NOT NULL"),
    ("payment", "DECIMAL(18,4) NOT NULL"),
    ("principal_portion", "DECIMAL(18,4) NOT NULL"),
    ("interest_portion", "DECIMAL(18,4) NOT NULL"),
    ("remaining_balance", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
]

# ---------------------------------------------------------------------------
# Mart: mart_loan_repayment_variance
# ---------------------------------------------------------------------------

MART_LOAN_REPAYMENT_VARIANCE_TABLE = "mart_loan_repayment_variance"

MART_LOAN_REPAYMENT_VARIANCE_COLUMNS: list[tuple[str, str]] = [
    ("loan_id", "VARCHAR NOT NULL"),
    ("loan_name", "VARCHAR NOT NULL"),
    ("repayment_month", "VARCHAR NOT NULL"),
    ("projected_payment", "DECIMAL(18,4) NOT NULL"),
    ("actual_payment", "DECIMAL(18,4) NOT NULL"),
    ("variance", "DECIMAL(18,4) NOT NULL"),
    ("projected_balance", "DECIMAL(18,4) NOT NULL"),
    ("actual_balance_estimate", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
]

# ---------------------------------------------------------------------------
# Mart: mart_loan_overview
# ---------------------------------------------------------------------------

MART_LOAN_OVERVIEW_TABLE = "mart_loan_overview"

MART_LOAN_OVERVIEW_COLUMNS: list[tuple[str, str]] = [
    ("loan_id", "VARCHAR NOT NULL"),
    ("loan_name", "VARCHAR NOT NULL"),
    ("lender", "VARCHAR NOT NULL"),
    ("original_principal", "DECIMAL(18,4) NOT NULL"),
    ("current_balance_estimate", "DECIMAL(18,4) NOT NULL"),
    ("monthly_payment", "DECIMAL(18,4) NOT NULL"),
    ("total_interest_projected", "DECIMAL(18,4) NOT NULL"),
    ("total_interest_paid", "DECIMAL(18,4) NOT NULL"),
    ("remaining_months", "INTEGER NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
]

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def extract_loan_dimensions(rows: list[dict]) -> list[dict]:
    """Derive distinct dim_loan rows from canonical repayment dicts.

    Deduplicates by loan_id — only present when loan definition columns exist.
    """
    seen: dict[str, dict] = {}
    for row in rows:
        loan_id = row.get("loan_id", "")
        if not loan_id or "loan_name" not in row:
            continue
        seen[loan_id] = {
            "loan_id": loan_id,
            "loan_name": row.get("loan_name", loan_id),
            "lender": row.get("lender", ""),
            "loan_type": row.get("loan_type", "personal"),
            "currency": row.get("currency", ""),
            "principal": row.get("principal", "0"),
            "annual_rate": row.get("annual_rate", "0"),
            "term_months": row.get("term_months", 0),
            "start_date": row.get("start_date"),
            "payment_frequency": row.get("payment_frequency", "monthly"),
        }
    return list(seen.values())


def loan_repayment_id(loan_id: str, repayment_date: str) -> str:
    """Deterministic repayment_id derived from loan + date."""
    raw = f"{loan_id}|{repayment_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
