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
