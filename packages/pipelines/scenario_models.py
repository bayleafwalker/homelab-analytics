"""Scenario storage table schemas — dim_scenario, fact_scenario_assumption, proj tables."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Dimension: dim_scenario
# ---------------------------------------------------------------------------

DIM_SCENARIO_TABLE = "dim_scenario"

DIM_SCENARIO_COLUMNS: list[tuple[str, str]] = [
    ("scenario_id", "VARCHAR NOT NULL"),
    ("scenario_type", "VARCHAR NOT NULL"),   # loan_what_if | future types
    ("subject_id", "VARCHAR NOT NULL"),      # loan_id (or other entity id)
    ("label", "VARCHAR NOT NULL"),
    ("status", "VARCHAR NOT NULL"),          # active | archived
    ("baseline_run_id", "VARCHAR"),          # run_id when scenario was computed
    ("created_at", "VARCHAR NOT NULL"),      # ISO timestamp
]

# ---------------------------------------------------------------------------
# Fact: fact_scenario_assumption
# ---------------------------------------------------------------------------

FACT_SCENARIO_ASSUMPTION_TABLE = "fact_scenario_assumption"

FACT_SCENARIO_ASSUMPTION_COLUMNS: list[tuple[str, str]] = [
    ("scenario_id", "VARCHAR NOT NULL"),
    ("assumption_key", "VARCHAR NOT NULL"),  # extra_repayment | annual_rate | term_months
    ("baseline_value", "VARCHAR"),           # stringified original value
    ("override_value", "VARCHAR NOT NULL"),  # stringified override value
    ("unit", "VARCHAR"),                     # e.g. currency code, "%" etc.
]

# ---------------------------------------------------------------------------
# Projection: proj_loan_schedule
# (mirrors mart_loan_schedule_projected columns + scenario_id)
# ---------------------------------------------------------------------------

PROJ_LOAN_SCHEDULE_TABLE = "proj_loan_schedule"

PROJ_LOAN_SCHEDULE_COLUMNS: list[tuple[str, str]] = [
    ("scenario_id", "VARCHAR NOT NULL"),
    ("loan_id", "VARCHAR NOT NULL"),
    ("loan_name", "VARCHAR NOT NULL"),
    ("period", "INTEGER NOT NULL"),
    ("payment_date", "DATE NOT NULL"),
    ("payment", "DECIMAL(18,4) NOT NULL"),
    ("principal_portion", "DECIMAL(18,4) NOT NULL"),
    ("interest_portion", "DECIMAL(18,4) NOT NULL"),
    ("extra_repayment", "DECIMAL(18,4) NOT NULL"),
    ("remaining_balance", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
]

# ---------------------------------------------------------------------------
# Projection: proj_loan_repayment_variance (scenario vs baseline)
# ---------------------------------------------------------------------------

PROJ_LOAN_REPAYMENT_VARIANCE_TABLE = "proj_loan_repayment_variance"

PROJ_LOAN_REPAYMENT_VARIANCE_COLUMNS: list[tuple[str, str]] = [
    ("scenario_id", "VARCHAR NOT NULL"),
    ("loan_id", "VARCHAR NOT NULL"),
    ("period", "INTEGER NOT NULL"),
    ("payment_date", "DATE NOT NULL"),
    ("baseline_payment", "DECIMAL(18,4)"),
    ("scenario_payment", "DECIMAL(18,4) NOT NULL"),
    ("baseline_balance", "DECIMAL(18,4)"),
    ("scenario_balance", "DECIMAL(18,4) NOT NULL"),
    ("payment_delta", "DECIMAL(18,4)"),
    ("balance_delta", "DECIMAL(18,4)"),
    ("currency", "VARCHAR NOT NULL"),
]
