from __future__ import annotations

from dataclasses import dataclass

from packages.pipelines.contract_price_models import (
    MART_CONTRACT_PRICE_CURRENT_COLUMNS,
    MART_CONTRACT_PRICE_CURRENT_TABLE,
    MART_ELECTRICITY_PRICE_CURRENT_COLUMNS,
    MART_ELECTRICITY_PRICE_CURRENT_TABLE,
)
from packages.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
    CURRENT_DIM_CONTRACT_VIEW,
    DIM_CATEGORY,
    DIM_CONTRACT,
    MART_SUBSCRIPTION_SUMMARY_COLUMNS,
    MART_SUBSCRIPTION_SUMMARY_TABLE,
)
from packages.pipelines.transaction_models import (
    CURRENT_DIM_ACCOUNT_VIEW,
    CURRENT_DIM_COUNTERPARTY_VIEW,
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
    MART_MONTHLY_CASHFLOW_COLUMNS,
    MART_MONTHLY_CASHFLOW_TABLE,
    TRANSFORMATION_AUDIT_COLUMNS,
    TRANSFORMATION_AUDIT_TABLE,
)
from packages.pipelines.utility_models import (
    CURRENT_DIM_METER_VIEW,
    DIM_METER,
    MART_UTILITY_COST_SUMMARY_COLUMNS,
    MART_UTILITY_COST_SUMMARY_TABLE,
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
    MART_SUBSCRIPTION_SUMMARY_TABLE: PublicationRelation(
        relation_name=MART_SUBSCRIPTION_SUMMARY_TABLE,
        columns=MART_SUBSCRIPTION_SUMMARY_COLUMNS,
        order_by="contract_name",
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
}


CURRENT_DIMENSION_RELATIONS = {
    "dim_account": CURRENT_DIM_ACCOUNT_VIEW,
    "dim_counterparty": CURRENT_DIM_COUNTERPARTY_VIEW,
    "dim_contract": CURRENT_DIM_CONTRACT_VIEW,
    "dim_category": CURRENT_DIM_CATEGORY_VIEW,
    "dim_meter": CURRENT_DIM_METER_VIEW,
}
