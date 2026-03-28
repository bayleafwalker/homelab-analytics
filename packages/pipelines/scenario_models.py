"""Scenario storage table schemas — dim_scenario, compare sets, fact_scenario_assumption, proj tables.

Covers:
  - loan_what_if scenarios: proj_loan_schedule, proj_loan_repayment_variance
  - income_change scenarios: proj_income_cashflow
  - expense_shock / tariff_shock scenarios: proj_income_cashflow
  - homelab_cost_benefit scenarios: proj_homelab_cost_benefit_summary
  - scenario compare sets: dim_scenario_compare_set
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Dimension: dim_scenario
# ---------------------------------------------------------------------------

DIM_SCENARIO_TABLE = "dim_scenario"

DIM_SCENARIO_COLUMNS: list[tuple[str, str]] = [
    ("scenario_id", "VARCHAR NOT NULL"),
    ("scenario_type", "VARCHAR NOT NULL"),   # loan_what_if | income_change | expense_shock | tariff_shock
    ("subject_id", "VARCHAR NOT NULL"),      # loan_id (or other entity id)
    ("label", "VARCHAR NOT NULL"),
    ("status", "VARCHAR NOT NULL"),          # active | archived
    ("baseline_run_id", "VARCHAR"),          # run_id when scenario was computed
    ("created_at", "VARCHAR NOT NULL"),      # ISO timestamp
]

# ---------------------------------------------------------------------------
# Dimension: dim_scenario_compare_set
# ---------------------------------------------------------------------------

DIM_SCENARIO_COMPARE_SET_TABLE = "dim_scenario_compare_set"

DIM_SCENARIO_COMPARE_SET_COLUMNS: list[tuple[str, str]] = [
    ("compare_set_id", "VARCHAR NOT NULL"),
    ("label", "VARCHAR NOT NULL"),
    ("left_scenario_id", "VARCHAR NOT NULL"),
    ("right_scenario_id", "VARCHAR NOT NULL"),
    ("left_scenario_label", "VARCHAR NOT NULL"),
    ("right_scenario_label", "VARCHAR NOT NULL"),
    ("status", "VARCHAR NOT NULL"),          # active | archived
    ("created_at", "VARCHAR NOT NULL"),      # ISO timestamp
    ("updated_at", "VARCHAR NOT NULL"),      # ISO timestamp
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

# ---------------------------------------------------------------------------
# Projection: proj_income_cashflow (income_change scenario)
# ---------------------------------------------------------------------------

PROJ_INCOME_CASHFLOW_TABLE = "proj_income_cashflow"

PROJ_INCOME_CASHFLOW_COLUMNS: list[tuple[str, str]] = [
    ("scenario_id", "VARCHAR NOT NULL"),
    ("period", "INTEGER NOT NULL"),
    ("projected_month", "VARCHAR NOT NULL"),    # YYYY-MM
    ("baseline_income", "DECIMAL(18,4) NOT NULL"),
    ("scenario_income", "DECIMAL(18,4) NOT NULL"),
    ("baseline_expense", "DECIMAL(18,4) NOT NULL"),
    ("scenario_expense", "DECIMAL(18,4) NOT NULL"),
    ("baseline_net", "DECIMAL(18,4) NOT NULL"),
    ("scenario_net", "DECIMAL(18,4) NOT NULL"),
    ("net_delta", "DECIMAL(18,4) NOT NULL"),
]

# ---------------------------------------------------------------------------
# Projection summary: proj_homelab_cost_benefit_summary
# ---------------------------------------------------------------------------

PROJ_HOMELAB_COST_BENEFIT_SUMMARY_TABLE = "proj_homelab_cost_benefit_summary"

PROJ_HOMELAB_COST_BENEFIT_SUMMARY_COLUMNS: list[tuple[str, str]] = [
    ("scenario_id", "VARCHAR NOT NULL"),
    ("metric_key", "VARCHAR NOT NULL"),
    ("baseline_value", "DECIMAL(18,4)"),
    ("scenario_value", "DECIMAL(18,4)"),
    ("delta_value", "DECIMAL(18,4)"),
    ("unit", "VARCHAR"),
]
