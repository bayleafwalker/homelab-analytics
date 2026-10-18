"""Finance-pack mart readers served by ReportingService from the warehouse."""

from __future__ import annotations

from packages.domains.finance.pipelines.budget_models import (
    MART_BUDGET_ENVELOPE_DRIFT_TABLE,
    MART_BUDGET_PROGRESS_CURRENT_TABLE,
    MART_BUDGET_VARIANCE_TABLE,
)
from packages.domains.finance.pipelines.contract_price_models import (
    MART_CONTRACT_PRICE_CURRENT_TABLE,
    MART_ELECTRICITY_PRICE_CURRENT_TABLE,
)
from packages.domains.finance.pipelines.loan_models import (
    MART_LOAN_OVERVIEW_TABLE,
    MART_LOAN_REPAYMENT_VARIANCE_TABLE,
    MART_LOAN_SCHEDULE_PROJECTED_TABLE,
)
from packages.domains.finance.pipelines.subscription_models import (
    MART_SUBSCRIPTION_SUMMARY_TABLE,
    MART_UPCOMING_FIXED_COSTS_30D_TABLE,
)
from packages.domains.finance.pipelines.transaction_models import (
    MART_ACCOUNT_BALANCE_TREND_TABLE,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
    MART_MONTHLY_CASHFLOW_TABLE,
    MART_RECENT_LARGE_TRANSACTIONS_TABLE,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
    MART_SPEND_BY_WEEKDAY_HOUR_TABLE,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
    TRANSFORMATION_AUDIT_TABLE,
)
from packages.domains.finance.pipelines.transformation_budgets import (
    get_budget_envelope_drift,
    get_budget_progress_current,
    get_budget_variance,
)
from packages.domains.finance.pipelines.transformation_contract_prices import (
    get_contract_price_current,
    get_electricity_price_current,
)
from packages.domains.finance.pipelines.transformation_loans import (
    get_loan_overview,
    get_loan_repayment_variance,
    get_loan_schedule_projected,
)
from packages.domains.finance.pipelines.transformation_subscriptions import (
    get_subscription_summary,
    get_upcoming_fixed_costs_30d,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    get_account_balance_trend,
    get_monthly_cashflow,
    get_monthly_cashflow_by_counterparty,
    get_recent_large_transactions,
    get_spend_by_category_monthly,
    get_spend_by_weekday_hour,
    get_transaction_anomalies_current,
    get_transformation_audit,
)
from packages.pipelines.mart_read_registry import MartReader

FINANCE_MART_READERS: dict[str, MartReader] = {
    MART_MONTHLY_CASHFLOW_TABLE: get_monthly_cashflow,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE: get_monthly_cashflow_by_counterparty,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE: get_spend_by_category_monthly,
    MART_RECENT_LARGE_TRANSACTIONS_TABLE: get_recent_large_transactions,
    MART_ACCOUNT_BALANCE_TREND_TABLE: get_account_balance_trend,
    MART_SPEND_BY_WEEKDAY_HOUR_TABLE: get_spend_by_weekday_hour,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE: get_transaction_anomalies_current,
    TRANSFORMATION_AUDIT_TABLE: get_transformation_audit,
    MART_SUBSCRIPTION_SUMMARY_TABLE: get_subscription_summary,
    MART_UPCOMING_FIXED_COSTS_30D_TABLE: get_upcoming_fixed_costs_30d,
    MART_CONTRACT_PRICE_CURRENT_TABLE: get_contract_price_current,
    MART_ELECTRICITY_PRICE_CURRENT_TABLE: get_electricity_price_current,
    MART_BUDGET_VARIANCE_TABLE: get_budget_variance,
    MART_BUDGET_ENVELOPE_DRIFT_TABLE: get_budget_envelope_drift,
    MART_BUDGET_PROGRESS_CURRENT_TABLE: get_budget_progress_current,
    MART_LOAN_SCHEDULE_PROJECTED_TABLE: get_loan_schedule_projected,
    MART_LOAN_REPAYMENT_VARIANCE_TABLE: get_loan_repayment_variance,
    MART_LOAN_OVERVIEW_TABLE: get_loan_overview,
}
