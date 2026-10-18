"""Finance-pack mart readers served by ReportingService from the warehouse."""

from __future__ import annotations

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
}
