from __future__ import annotations

from dataclasses import dataclass

from packages.domains.finance.pipelines.budget_models import (
    CURRENT_DIM_BUDGET_VIEW,
    DIM_BUDGET,
    MART_BUDGET_ENVELOPE_DRIFT_COLUMNS,
    MART_BUDGET_ENVELOPE_DRIFT_TABLE,
    MART_BUDGET_PROGRESS_CURRENT_COLUMNS,
    MART_BUDGET_PROGRESS_CURRENT_TABLE,
    MART_BUDGET_VARIANCE_COLUMNS,
    MART_BUDGET_VARIANCE_TABLE,
)
from packages.domains.finance.pipelines.contract_price_models import (
    MART_CONTRACT_PRICE_CURRENT_COLUMNS,
    MART_CONTRACT_PRICE_CURRENT_TABLE,
    MART_ELECTRICITY_PRICE_CURRENT_COLUMNS,
    MART_ELECTRICITY_PRICE_CURRENT_TABLE,
)
from packages.domains.finance.pipelines.loan_models import (
    CURRENT_DIM_LOAN_VIEW,
    DIM_LOAN,
    MART_LOAN_OVERVIEW_COLUMNS,
    MART_LOAN_OVERVIEW_TABLE,
    MART_LOAN_REPAYMENT_VARIANCE_COLUMNS,
    MART_LOAN_REPAYMENT_VARIANCE_TABLE,
    MART_LOAN_SCHEDULE_PROJECTED_COLUMNS,
    MART_LOAN_SCHEDULE_PROJECTED_TABLE,
)
from packages.domains.finance.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
    CURRENT_DIM_CONTRACT_VIEW,
    DIM_CATEGORY,
    DIM_CONTRACT,
    MART_SUBSCRIPTION_SUMMARY_COLUMNS,
    MART_SUBSCRIPTION_SUMMARY_TABLE,
    MART_UPCOMING_FIXED_COSTS_30D_COLUMNS,
    MART_UPCOMING_FIXED_COSTS_30D_TABLE,
)
from packages.domains.finance.pipelines.transaction_models import (
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
from packages.domains.homelab.pipelines.home_automation_models import (
    CURRENT_DIM_ENTITY_VIEW,
    DIM_ENTITY,
)
from packages.domains.homelab.pipelines.homelab_models import (
    CURRENT_DIM_SERVICE_VIEW,
    CURRENT_DIM_WORKLOAD_VIEW,
    DIM_SERVICE,
    DIM_WORKLOAD,
    MART_BACKUP_FRESHNESS_COLUMNS,
    MART_BACKUP_FRESHNESS_TABLE,
    MART_SERVICE_HEALTH_CURRENT_COLUMNS,
    MART_SERVICE_HEALTH_CURRENT_TABLE,
    MART_STORAGE_RISK_COLUMNS,
    MART_STORAGE_RISK_TABLE,
    MART_WORKLOAD_COST_7D_COLUMNS,
    MART_WORKLOAD_COST_7D_TABLE,
)
from packages.domains.homelab.pipelines.infrastructure_models import (
    CURRENT_DIM_DEVICE_VIEW,
    CURRENT_DIM_NODE_VIEW,
    DIM_DEVICE,
    DIM_NODE,
)
from packages.domains.overview.pipelines.overview_models import (
    MART_AFFORDABILITY_RATIOS_COLUMNS,
    MART_AFFORDABILITY_RATIOS_TABLE,
    MART_COST_TREND_12M_COLUMNS,
    MART_COST_TREND_12M_TABLE,
    MART_CURRENT_OPERATING_BASELINE_COLUMNS,
    MART_CURRENT_OPERATING_BASELINE_TABLE,
    MART_HOMELAB_ROI_COLUMNS,
    MART_HOMELAB_ROI_TABLE,
    MART_HOUSEHOLD_COST_MODEL_COLUMNS,
    MART_HOUSEHOLD_COST_MODEL_TABLE,
    MART_HOUSEHOLD_OVERVIEW_COLUMNS,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_COLUMNS,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
    MART_RECURRING_COST_BASELINE_COLUMNS,
    MART_RECURRING_COST_BASELINE_TABLE,
)
from packages.domains.utilities.pipelines.utility_models import (
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
from packages.pipelines.asset_models import (
    CURRENT_DIM_ASSET_VIEW,
    DIM_ASSET,
)
from packages.pipelines.household_models import (
    CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW,
    DIM_HOUSEHOLD_MEMBER,
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
    MART_LOAN_SCHEDULE_PROJECTED_TABLE: PublicationRelation(
        relation_name=MART_LOAN_SCHEDULE_PROJECTED_TABLE,
        columns=MART_LOAN_SCHEDULE_PROJECTED_COLUMNS,
        order_by="loan_id, period",
    ),
    MART_LOAN_REPAYMENT_VARIANCE_TABLE: PublicationRelation(
        relation_name=MART_LOAN_REPAYMENT_VARIANCE_TABLE,
        columns=MART_LOAN_REPAYMENT_VARIANCE_COLUMNS,
        order_by="loan_id, repayment_month",
    ),
    MART_LOAN_OVERVIEW_TABLE: PublicationRelation(
        relation_name=MART_LOAN_OVERVIEW_TABLE,
        columns=MART_LOAN_OVERVIEW_COLUMNS,
        order_by="loan_name",
    ),
    CURRENT_DIM_LOAN_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_LOAN_VIEW,
        columns=_current_dimension_columns(DIM_LOAN),
        order_by="loan_id",
    ),
    CURRENT_DIM_ASSET_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_ASSET_VIEW,
        columns=_current_dimension_columns(DIM_ASSET),
        order_by="asset_id",
    ),
    CURRENT_DIM_ENTITY_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_ENTITY_VIEW,
        columns=_current_dimension_columns(DIM_ENTITY),
        order_by="entity_id",
    ),
    CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW,
        columns=_current_dimension_columns(DIM_HOUSEHOLD_MEMBER),
        order_by="member_id",
    ),
    CURRENT_DIM_NODE_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_NODE_VIEW,
        columns=_current_dimension_columns(DIM_NODE),
        order_by="hostname",
    ),
    CURRENT_DIM_DEVICE_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_DEVICE_VIEW,
        columns=_current_dimension_columns(DIM_DEVICE),
        order_by="device_id",
    ),
    CURRENT_DIM_SERVICE_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_SERVICE_VIEW,
        columns=_current_dimension_columns(DIM_SERVICE),
        order_by="service_id",
    ),
    CURRENT_DIM_WORKLOAD_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_WORKLOAD_VIEW,
        columns=_current_dimension_columns(DIM_WORKLOAD),
        order_by="workload_id",
    ),
    MART_BUDGET_VARIANCE_TABLE: PublicationRelation(
        relation_name=MART_BUDGET_VARIANCE_TABLE,
        columns=MART_BUDGET_VARIANCE_COLUMNS,
        order_by="budget_name, period_label",
    ),
    MART_BUDGET_ENVELOPE_DRIFT_TABLE: PublicationRelation(
        relation_name=MART_BUDGET_ENVELOPE_DRIFT_TABLE,
        columns=MART_BUDGET_ENVELOPE_DRIFT_COLUMNS,
        order_by="budget_name, period_label",
    ),
    MART_BUDGET_PROGRESS_CURRENT_TABLE: PublicationRelation(
        relation_name=MART_BUDGET_PROGRESS_CURRENT_TABLE,
        columns=MART_BUDGET_PROGRESS_CURRENT_COLUMNS,
        order_by="budget_name, category_id",
    ),
    CURRENT_DIM_BUDGET_VIEW: PublicationRelation(
        relation_name=CURRENT_DIM_BUDGET_VIEW,
        columns=_current_dimension_columns(DIM_BUDGET),
        order_by="budget_id",
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
    MART_HOMELAB_ROI_TABLE: PublicationRelation(
        relation_name=MART_HOMELAB_ROI_TABLE,
        columns=MART_HOMELAB_ROI_COLUMNS,
        order_by="roi_state, service_count DESC",
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
    MART_HOUSEHOLD_COST_MODEL_TABLE: PublicationRelation(
        relation_name=MART_HOUSEHOLD_COST_MODEL_TABLE,
        columns=MART_HOUSEHOLD_COST_MODEL_COLUMNS,
        order_by="period_label, cost_type",
    ),
    MART_COST_TREND_12M_TABLE: PublicationRelation(
        relation_name=MART_COST_TREND_12M_TABLE,
        columns=MART_COST_TREND_12M_COLUMNS,
        order_by="period_label, cost_type",
    ),
    MART_AFFORDABILITY_RATIOS_TABLE: PublicationRelation(
        relation_name=MART_AFFORDABILITY_RATIOS_TABLE,
        columns=MART_AFFORDABILITY_RATIOS_COLUMNS,
        order_by="ratio_name",
    ),
    MART_RECURRING_COST_BASELINE_TABLE: PublicationRelation(
        relation_name=MART_RECURRING_COST_BASELINE_TABLE,
        columns=MART_RECURRING_COST_BASELINE_COLUMNS,
        order_by="cost_source, counterparty_or_contract",
    ),
    MART_SERVICE_HEALTH_CURRENT_TABLE: PublicationRelation(
        relation_name=MART_SERVICE_HEALTH_CURRENT_TABLE,
        columns=MART_SERVICE_HEALTH_CURRENT_COLUMNS,
        order_by="service_id",
    ),
    MART_BACKUP_FRESHNESS_TABLE: PublicationRelation(
        relation_name=MART_BACKUP_FRESHNESS_TABLE,
        columns=MART_BACKUP_FRESHNESS_COLUMNS,
        order_by="target",
    ),
    MART_STORAGE_RISK_TABLE: PublicationRelation(
        relation_name=MART_STORAGE_RISK_TABLE,
        columns=MART_STORAGE_RISK_COLUMNS,
        order_by="pct_used DESC",
    ),
    MART_WORKLOAD_COST_7D_TABLE: PublicationRelation(
        relation_name=MART_WORKLOAD_COST_7D_TABLE,
        columns=MART_WORKLOAD_COST_7D_COLUMNS,
        order_by="est_monthly_cost DESC NULLS LAST",
    ),
}


CURRENT_DIMENSION_RELATIONS = {
    "dim_account": CURRENT_DIM_ACCOUNT_VIEW,
    "dim_counterparty": CURRENT_DIM_COUNTERPARTY_VIEW,
    "dim_contract": CURRENT_DIM_CONTRACT_VIEW,
    "dim_category": CURRENT_DIM_CATEGORY_VIEW,
    "dim_meter": CURRENT_DIM_METER_VIEW,
    "dim_budget": CURRENT_DIM_BUDGET_VIEW,
    "dim_loan": CURRENT_DIM_LOAN_VIEW,
    "dim_asset": CURRENT_DIM_ASSET_VIEW,
    "dim_entity": CURRENT_DIM_ENTITY_VIEW,
    "dim_household_member": CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW,
    "dim_node": CURRENT_DIM_NODE_VIEW,
    "dim_device": CURRENT_DIM_DEVICE_VIEW,
    "dim_service": CURRENT_DIM_SERVICE_VIEW,
    "dim_workload": CURRENT_DIM_WORKLOAD_VIEW,
}
