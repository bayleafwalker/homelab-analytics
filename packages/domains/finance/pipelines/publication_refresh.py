"""Finance-pack publication refresh handlers.

Each handler refreshes one reporting publication from this pack's
transformation functions; the household composition registers them with the
publication refresh registry.
"""

from __future__ import annotations

from packages.domains.finance.pipelines.transformation_assets import (
    refresh_asset_value,
    refresh_depreciation_schedule,
)
from packages.domains.finance.pipelines.transformation_budgets import (
    refresh_budget_envelope_drift,
    refresh_budget_progress_current,
    refresh_budget_variance,
)
from packages.domains.finance.pipelines.transformation_contract_prices import (
    refresh_contract_price_current,
)
from packages.domains.finance.pipelines.transformation_loans import (
    refresh_debt_overview,
    refresh_loan_overview,
    refresh_loan_repayment_variance,
    refresh_loan_schedule_projected,
)
from packages.domains.finance.pipelines.transformation_subscriptions import (
    refresh_subscription_changes,
    refresh_subscription_summary,
    refresh_upcoming_fixed_costs_30d,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    refresh_account_balance_trend,
    refresh_monthly_cashflow,
    refresh_monthly_cashflow_by_counterparty,
    refresh_recent_large_transactions,
    refresh_spend_by_category_monthly,
    refresh_transaction_anomalies_current,
)
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshHandler,
    StoreRefreshHandler,
)

FINANCE_PUBLICATION_REFRESH_HANDLERS: dict[str, PublicationRefreshHandler] = {
    "mart_monthly_cashflow": StoreRefreshHandler(refresh_monthly_cashflow),
    "mart_monthly_cashflow_by_counterparty": StoreRefreshHandler(refresh_monthly_cashflow_by_counterparty),
    "mart_spend_by_category_monthly": StoreRefreshHandler(refresh_spend_by_category_monthly),
    "mart_recent_large_transactions": StoreRefreshHandler(refresh_recent_large_transactions),
    "mart_account_balance_trend": StoreRefreshHandler(refresh_account_balance_trend),
    "mart_transaction_anomalies_current": StoreRefreshHandler(refresh_transaction_anomalies_current),
    "mart_subscription_summary": StoreRefreshHandler(refresh_subscription_summary),
    "mart_upcoming_fixed_costs_30d": StoreRefreshHandler(refresh_upcoming_fixed_costs_30d),
    "mart_subscription_changes": StoreRefreshHandler(refresh_subscription_changes),
    "mart_contract_price_current": StoreRefreshHandler(refresh_contract_price_current),
    "mart_electricity_price_current": StoreRefreshHandler(refresh_contract_price_current),
    "mart_budget_variance": StoreRefreshHandler(refresh_budget_variance),
    "mart_budget_envelope_drift": StoreRefreshHandler(refresh_budget_envelope_drift),
    "mart_budget_progress_current": StoreRefreshHandler(refresh_budget_progress_current),
    "mart_loan_schedule_projected": StoreRefreshHandler(refresh_loan_schedule_projected),
    "mart_loan_repayment_variance": StoreRefreshHandler(refresh_loan_repayment_variance),
    "mart_loan_overview": StoreRefreshHandler(refresh_loan_overview),
    "mart_debt_overview": StoreRefreshHandler(refresh_debt_overview),
    "mart_asset_value": StoreRefreshHandler(refresh_asset_value),
    "mart_depreciation_schedule": StoreRefreshHandler(refresh_depreciation_schedule),
}
