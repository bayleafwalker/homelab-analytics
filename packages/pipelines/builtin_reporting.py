from __future__ import annotations

from dataclasses import dataclass

from packages.pipelines.contract_price_models import (
    MART_CONTRACT_PRICE_CURRENT_COLUMNS,
    MART_CONTRACT_PRICE_CURRENT_TABLE,
    MART_ELECTRICITY_PRICE_CURRENT_COLUMNS,
    MART_ELECTRICITY_PRICE_CURRENT_TABLE,
)
from packages.pipelines.overview_models import (
    MART_CURRENT_OPERATING_BASELINE_COLUMNS,
    MART_CURRENT_OPERATING_BASELINE_TABLE,
    MART_HOUSEHOLD_OVERVIEW_COLUMNS,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_COLUMNS,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
)
from packages.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
    CURRENT_DIM_CONTRACT_VIEW,
    DIM_CATEGORY,
    DIM_CONTRACT,
    MART_SUBSCRIPTION_SUMMARY_COLUMNS,
    MART_SUBSCRIPTION_SUMMARY_TABLE,
    MART_UPCOMING_FIXED_COSTS_30D_COLUMNS,
    MART_UPCOMING_FIXED_COSTS_30D_TABLE,
)
from packages.pipelines.transaction_models import (
    CURRENT_DIM_ACCOUNT_VIEW,
    CURRENT_DIM_COUNTERPARTY_VIEW,
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    MART_ACCOUNT_BALANCE_TREND_COLUMNS,
    MART_ACCOUNT_BALANCE_TREND_TABLE,
    MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
    MART_MONTHLY_CASHFLOW_COLUMNS,
    MART_MONTHLY_CASHFLOW_TABLE,
    MART_RECENT_LARGE_TRANSACTIONS_COLUMNS,
    MART_RECENT_LARGE_TRANSACTIONS_TABLE,
    MART_SPEND_BY_CATEGORY_MONTHLY_COLUMNS,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
    MART_TRANSACTION_ANOMALIES_CURRENT_COLUMNS,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
    TRANSFORMATION_AUDIT_COLUMNS,
    TRANSFORMATION_AUDIT_TABLE,
)
from packages.pipelines.utility_models import (
    CURRENT_DIM_METER_VIEW,
    DIM_METER,
    MART_CONTRACT_RENEWAL_WATCHLIST_COLUMNS,
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
    MART_CONTRACT_REVIEW_CANDIDATES_COLUMNS,
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
    MART_USAGE_VS_PRICE_SUMMARY_COLUMNS,
    MART_USAGE_VS_PRICE_SUMMARY_TABLE,
    MART_UTILITY_COST_SUMMARY_COLUMNS,
    MART_UTILITY_COST_SUMMARY_TABLE,
    MART_UTILITY_COST_TREND_MONTHLY_COLUMNS,
    MART_UTILITY_COST_TREND_MONTHLY_TABLE,
)
from packages.storage.duckdb_store import DimensionDefinition


@dataclass(frozen=True)
class PublicationRelation:
    relation_name: str
    columns: list[tuple[str, str]]
    order_by: str
    source_query: str | None = None


def _current_dimension_columns(defn: DimensionDefinition) -> list[tuple[str, str]]:
    return [
        (defn.surrogate_key_column, "VARCHAR NOT NULL"),
        *[(column, "VARCHAR NOT NULL") for column in defn.natural_key_columns],
        *[(column.name, column.dtype) for column in defn.attribute_columns],
    ]


PUBLICATION_RELATIONS: dict[str, PublicationRelation] = {
    MART_MONTHLY_CASHFLOW_TABLE: PublicationRelation(
        relation_name=MART_MONTHLY_CASHFLOW_TABLE,
        columns=MART_MONTHLY_CASHFLOW_COLUMNS,
        order_by="booking_month",
    ),
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE: PublicationRelation(
        relation_name=MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
        columns=MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
        order_by="booking_month, counterparty_name",
    ),
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE: PublicationRelation(
        relation_name=MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
        columns=MART_SPEND_BY_CATEGORY_MONTHLY_COLUMNS,
        order_by="booking_month, total_expense DESC",
    ),
    MART_RECENT_LARGE_TRANSACTIONS_TABLE: PublicationRelation(
        relation_name=MART_RECENT_LARGE_TRANSACTIONS_TABLE,
        columns=MART_RECENT_LARGE_TRANSACTIONS_COLUMNS,
        order_by="ABS(amount) DESC, booked_at DESC",
    ),
    MART_ACCOUNT_BALANCE_TREND_TABLE: PublicationRelation(
        relation_name=MART_ACCOUNT_BALANCE_TREND_TABLE,
        columns=MART_ACCOUNT_BALANCE_TREND_COLUMNS,
        order_by="booking_month, account_id",
    ),
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE: PublicationRelation(
        relation_name=MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
        columns=MART_TRANSACTION_ANOMALIES_CURRENT_COLUMNS,
        order_by="booking_date DESC, ABS(amount) DESC",
    ),
    MART_SUBSCRIPTION_SUMMARY_TABLE: PublicationRelation(
        relation_name=MART_SUBSCRIPTION_SUMMARY_TABLE,
        columns=MART_SUBSCRIPTION_SUMMARY_COLUMNS,
        order_by="contract_name",
    ),
    MART_UPCOMING_FIXED_COSTS_30D_TABLE: PublicationRelation(
        relation_name=MART_UPCOMING_FIXED_COSTS_30D_TABLE,
        columns=MART_UPCOMING_FIXED_COSTS_30D_COLUMNS,
        order_by="expected_date, contract_name",
    ),
    MART_CONTRACT_PRICE_CURRENT_TABLE: PublicationRelation(
        relation_name=MART_CONTRACT_PRICE_CURRENT_TABLE,
        columns=MART_CONTRACT_PRICE_CURRENT_COLUMNS,
        order_by="contract_type, contract_name, price_component, valid_from",
    ),
    MART_ELECTRICITY_PRICE_CURRENT_TABLE: PublicationRelation(
        relation_name=MART_ELECTRICITY_PRICE_CURRENT_TABLE,
        columns=MART_ELECTRICITY_PRICE_CURRENT_COLUMNS,
        order_by="contract_name, price_component, valid_from",
    ),
    MART_UTILITY_COST_SUMMARY_TABLE: PublicationRelation(
        relation_name=MART_UTILITY_COST_SUMMARY_TABLE,
        columns=MART_UTILITY_COST_SUMMARY_COLUMNS,
        order_by="period_start, meter_id",
    ),
    MART_UTILITY_COST_TREND_MONTHLY_TABLE: PublicationRelation(
        relation_name=MART_UTILITY_COST_TREND_MONTHLY_TABLE,
        columns=MART_UTILITY_COST_TREND_MONTHLY_COLUMNS,
        order_by="billing_month, utility_type",
    ),
    MART_USAGE_VS_PRICE_SUMMARY_TABLE: PublicationRelation(
        relation_name=MART_USAGE_VS_PRICE_SUMMARY_TABLE,
        columns=MART_USAGE_VS_PRICE_SUMMARY_COLUMNS,
        order_by="utility_type, period",
    ),
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE: PublicationRelation(
        relation_name=MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
        columns=MART_CONTRACT_REVIEW_CANDIDATES_COLUMNS,
        order_by="score DESC, contract_id",
    ),
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE: PublicationRelation(
        relation_name=MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
        columns=MART_CONTRACT_RENEWAL_WATCHLIST_COLUMNS,
        order_by="renewal_date, contract_id",
    ),
    CURRENT_DIM_ACCOUNT_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_ACCOUNT_VIEW,
        columns=_current_dimension_columns(DIM_ACCOUNT),
        order_by="account_id",
    ),
    CURRENT_DIM_COUNTERPARTY_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_COUNTERPARTY_VIEW,
        columns=_current_dimension_columns(DIM_COUNTERPARTY),
        order_by="counterparty_name",
    ),
    CURRENT_DIM_CONTRACT_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_CONTRACT_VIEW,
        columns=_current_dimension_columns(DIM_CONTRACT),
        order_by="contract_name",
    ),
    CURRENT_DIM_CATEGORY_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_CATEGORY_VIEW,
        columns=_current_dimension_columns(DIM_CATEGORY),
        order_by="category_id",
    ),
    CURRENT_DIM_METER_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_METER_VIEW,
        columns=_current_dimension_columns(DIM_METER),
        order_by="meter_id",
    ),
    TRANSFORMATION_AUDIT_TABLE: PublicationRelation(
        relation_name=TRANSFORMATION_AUDIT_TABLE,
        columns=TRANSFORMATION_AUDIT_COLUMNS,
        order_by="started_at DESC",
    ),
    MART_HOUSEHOLD_OVERVIEW_TABLE: PublicationRelation(
        relation_name=MART_HOUSEHOLD_OVERVIEW_TABLE,
        columns=MART_HOUSEHOLD_OVERVIEW_COLUMNS,
        order_by="current_month",
    ),
    MART_OPEN_ATTENTION_ITEMS_TABLE: PublicationRelation(
        relation_name=MART_OPEN_ATTENTION_ITEMS_TABLE,
        columns=MART_OPEN_ATTENTION_ITEMS_COLUMNS,
        order_by="severity DESC, item_type, title",
    ),
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE: PublicationRelation(
        relation_name=MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
        columns=MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS,
        order_by="ABS(COALESCE(change_pct, 0)) DESC",
    ),
    MART_CURRENT_OPERATING_BASELINE_TABLE: PublicationRelation(
        relation_name=MART_CURRENT_OPERATING_BASELINE_TABLE,
        columns=MART_CURRENT_OPERATING_BASELINE_COLUMNS,
        order_by="baseline_type",
    ),
}


CURRENT_DIMENSION_RELATIONS = {
    "dim_account": CURRENT_DIM_ACCOUNT_VIEW,
    "dim_counterparty": CURRENT_DIM_COUNTERPARTY_VIEW,
    "dim_contract": CURRENT_DIM_CONTRACT_VIEW,
    "dim_category": CURRENT_DIM_CATEGORY_VIEW,
    "dim_meter": CURRENT_DIM_METER_VIEW,
}
