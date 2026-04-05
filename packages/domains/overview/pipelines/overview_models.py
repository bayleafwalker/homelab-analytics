"""Mart table schemas for the cross-domain overview composition layer."""
from __future__ import annotations

MART_HOUSEHOLD_OVERVIEW_TABLE = "mart_household_overview"

MART_HOUSEHOLD_OVERVIEW_COLUMNS: list[tuple[str, str]] = [
    ("current_month", "VARCHAR NOT NULL"),
    ("cashflow_income", "DECIMAL(18,4) NOT NULL"),
    ("cashflow_expense", "DECIMAL(18,4) NOT NULL"),
    ("cashflow_net", "DECIMAL(18,4) NOT NULL"),
    ("utility_cost_total", "DECIMAL(18,4) NOT NULL"),
    ("subscription_total_monthly", "DECIMAL(18,4) NOT NULL"),
    ("account_balance_direction", "VARCHAR NOT NULL"),  # up | down | flat
    ("balance_net_change", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
]

MART_OPEN_ATTENTION_ITEMS_TABLE = "mart_open_attention_items"

MART_OPEN_ATTENTION_ITEMS_COLUMNS: list[tuple[str, str]] = [
    ("item_id", "VARCHAR NOT NULL"),
    ("item_type", "VARCHAR NOT NULL"),   # anomaly | contract_review | contract_renewal | upcoming_cost
    ("title", "VARCHAR NOT NULL"),
    ("detail", "VARCHAR NOT NULL"),
    ("severity", "INTEGER NOT NULL"),    # 1=low, 2=medium, 3=high
    ("source_domain", "VARCHAR NOT NULL"),  # finance | utilities
]

MART_RECENT_SIGNIFICANT_CHANGES_TABLE = "mart_recent_significant_changes"

MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS: list[tuple[str, str]] = [
    ("change_type", "VARCHAR NOT NULL"),   # cashflow_net | category_spend | utility_cost
    ("period", "VARCHAR NOT NULL"),
    ("description", "VARCHAR NOT NULL"),
    ("current_value", "DECIMAL(18,4) NOT NULL"),
    ("previous_value", "DECIMAL(18,4) NOT NULL"),
    ("change_pct", "DECIMAL(18,4)"),
    ("direction", "VARCHAR NOT NULL"),     # up | down
]

MART_CURRENT_OPERATING_BASELINE_TABLE = "mart_current_operating_baseline"

MART_CURRENT_OPERATING_BASELINE_COLUMNS: list[tuple[str, str]] = [
    ("baseline_type", "VARCHAR NOT NULL"),   # monthly_spend | recurring_costs | utility_baseline | account_balance
    ("description", "VARCHAR NOT NULL"),
    ("value", "DECIMAL(18,4) NOT NULL"),
    ("period_label", "VARCHAR NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
]

MART_HOUSEHOLD_COST_MODEL_TABLE = "mart_household_cost_model"

MART_HOUSEHOLD_COST_MODEL_COLUMNS: list[tuple[str, str]] = [
    ("period_label", "VARCHAR NOT NULL"),     # YYYY-MM
    ("cost_type", "VARCHAR NOT NULL"),         # housing | utilities | transport | food | subscriptions | loans | discretionary | other
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("source_domain", "VARCHAR NOT NULL"),     # finance | utilities | subscriptions | loans
    ("currency", "VARCHAR NOT NULL"),
]

MART_COST_TREND_12M_TABLE = "mart_cost_trend_12m"

MART_COST_TREND_12M_COLUMNS: list[tuple[str, str]] = [
    ("period_label", "VARCHAR NOT NULL"),
    ("cost_type", "VARCHAR NOT NULL"),
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("prev_amount", "DECIMAL(18,4)"),
    ("change_pct", "DECIMAL(18,4)"),
    ("currency", "VARCHAR NOT NULL"),
]

MART_HOMELAB_ROI_TABLE = "mart_homelab_roi"

MART_HOMELAB_ROI_COLUMNS: list[tuple[str, str]] = [
    ("service_count", "INTEGER NOT NULL"),
    ("healthy_service_count", "INTEGER NOT NULL"),
    ("needs_attention_count", "INTEGER NOT NULL"),
    ("tracked_workload_count", "INTEGER NOT NULL"),
    ("healthy_service_share", "DECIMAL(18,4)"),
    ("monthly_workload_cost", "DECIMAL(18,4) NOT NULL"),
    ("cost_per_healthy_service", "DECIMAL(18,4)"),
    ("cost_per_tracked_workload", "DECIMAL(18,4)"),
    ("largest_workload_share", "DECIMAL(18,4)"),
    ("roi_score", "DECIMAL(18,6)"),
    ("roi_state", "VARCHAR NOT NULL"),      # empty | good | warning | needs_action
    ("decision_cue", "VARCHAR NOT NULL"),
]

MART_AFFORDABILITY_RATIOS_TABLE = "mart_affordability_ratios"

MART_AFFORDABILITY_RATIOS_COLUMNS: list[tuple[str, str]] = [
    ("ratio_name", "VARCHAR NOT NULL"),    # housing_to_income | total_cost_to_income | debt_service_ratio
    ("numerator", "DECIMAL(18,4) NOT NULL"),
    ("denominator", "DECIMAL(18,4) NOT NULL"),
    ("ratio", "DECIMAL(18,6) NOT NULL"),
    ("period_label", "VARCHAR NOT NULL"),
    ("assessment", "VARCHAR NOT NULL"),    # healthy | caution | critical
    ("state", "VARCHAR NOT NULL"),         # good | warning | needs_action
    ("currency", "VARCHAR NOT NULL"),
]

MART_RECURRING_COST_BASELINE_TABLE = "mart_recurring_cost_baseline"

MART_RECURRING_COST_BASELINE_COLUMNS: list[tuple[str, str]] = [
    ("cost_source", "VARCHAR NOT NULL"),       # subscription | utility_fixed | loan_payment
    ("counterparty_or_contract", "VARCHAR NOT NULL"),
    ("monthly_amount", "DECIMAL(18,4) NOT NULL"),
    ("confidence", "VARCHAR NOT NULL"),        # confirmed | estimated
    ("last_occurrence", "VARCHAR"),
    ("currency", "VARCHAR NOT NULL"),
]
