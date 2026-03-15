from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Callable

from packages.pipelines.contract_price_models import (
    MART_CONTRACT_PRICE_CURRENT_COLUMNS,
    MART_CONTRACT_PRICE_CURRENT_TABLE,
    MART_ELECTRICITY_PRICE_CURRENT_COLUMNS,
    MART_ELECTRICITY_PRICE_CURRENT_TABLE,
)
from packages.pipelines.promotion import PromotionResult
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
from packages.pipelines.transformation_service import TransformationService
from packages.pipelines.utility_models import (
    CURRENT_DIM_METER_VIEW,
    DIM_METER,
    MART_UTILITY_COST_SUMMARY_COLUMNS,
    MART_UTILITY_COST_SUMMARY_TABLE,
)
from packages.shared.extensions import ExtensionRegistry
from packages.storage.control_plane import (
    PublicationAuditCreate,
    PublicationAuditStore,
    SourceLineageCreate,
    SourceLineageStore,
)
from packages.storage.duckdb_store import DimensionDefinition
from packages.storage.postgres_reporting import PostgresReportingStore


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
_AUDIT_TRIGGER_MARTS = frozenset(
    {"mart_monthly_cashflow", "mart_monthly_cashflow_by_counterparty"}
)


class ReportingAccessMode(StrEnum):
    PREFER_PUBLISHED = "prefer_published"
    PUBLISHED = "published"
    WAREHOUSE = "warehouse"


def publish_promotion_reporting(
    reporting_service: "ReportingService | None",
    promotion: PromotionResult | None,
) -> list[str]:
    if reporting_service is None or promotion is None:
        return []

    try:
        published = reporting_service.publish_publications(
            promotion.publication_keys,
            run_id=promotion.run_id,
        )
    except TypeError:
        published = reporting_service.publish_publications(promotion.publication_keys)
    if _AUDIT_TRIGGER_MARTS & set(promotion.marts_refreshed):
        try:
            published.extend(
                reporting_service.publish_auxiliary_relations(
                    [TRANSFORMATION_AUDIT_TABLE],
                    run_id=promotion.run_id,
                )
            )
        except TypeError:
            published.extend(
                reporting_service.publish_auxiliary_relations(
                    [TRANSFORMATION_AUDIT_TABLE]
                )
            )
    if hasattr(reporting_service, "record_reporting_lineage"):
        reporting_service.record_reporting_lineage(
            run_id=promotion.run_id,
            relation_names=published,
        )
    return published


class ReportingService:
    def __init__(
        self,
        transformation_service: TransformationService,
        publication_store: PostgresReportingStore | None = None,
        extension_registry: ExtensionRegistry | None = None,
        access_mode: ReportingAccessMode = ReportingAccessMode.PREFER_PUBLISHED,
        control_plane_store: SourceLineageStore | PublicationAuditStore | None = None,
    ) -> None:
        self._transformation_service = transformation_service
        self._publication_store = publication_store
        self._extension_registry = extension_registry
        self._access_mode = access_mode
        self._control_plane_store = control_plane_store
        _validate_extension_publication_conflicts(extension_registry)

    def publish_publications(
        self,
        publication_keys: list[str],
        *,
        run_id: str | None = None,
    ) -> list[str]:
        if self._publication_store is None:
            return []

        published: list[str] = []
        for publication_key in publication_keys:
            self._publish_relation(publication_key)
            published.append(publication_key)
            self._record_publication_audit(
                publication_key=publication_key,
                relation_name=publication_key,
                run_id=run_id,
                status="published",
            )
        return published

    def publish_auxiliary_relations(
        self,
        relation_names: list[str],
        *,
        run_id: str | None = None,
    ) -> list[str]:
        if self._publication_store is None:
            return []
        published: list[str] = []
        for relation_name in relation_names:
            self._publish_relation(relation_name)
            published.append(relation_name)
            self._record_publication_audit(
                publication_key=relation_name,
                relation_name=relation_name,
                run_id=run_id,
                status="published",
            )
        return published

    def get_monthly_cashflow(
        self,
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_MONTHLY_CASHFLOW_TABLE,
            lambda: self._transformation_service.get_monthly_cashflow(
                from_month=from_month,
                to_month=to_month,
            ),
            _build_where_clause(
                ("booking_month >= %s", from_month),
                ("booking_month <= %s", to_month),
            ),
            "ORDER BY booking_month",
        )

    def get_monthly_cashflow_by_counterparty(
        self,
        *,
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty_name: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
            lambda: self._transformation_service.get_monthly_cashflow_by_counterparty(
                from_month=from_month,
                to_month=to_month,
                counterparty_name=counterparty_name,
            ),
            _build_where_clause(
                ("booking_month >= %s", from_month),
                ("booking_month <= %s", to_month),
                ("counterparty_name = %s", counterparty_name),
            ),
            "ORDER BY booking_month, counterparty_name",
        )

    def get_subscription_summary(
        self,
        *,
        status: str | None = None,
        currency: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_SUBSCRIPTION_SUMMARY_TABLE,
            lambda: self._transformation_service.get_subscription_summary(
                status=status,
                currency=currency,
            ),
            _build_where_clause(
                ("status = %s", status),
                ("currency = %s", currency),
            ),
            "ORDER BY contract_name",
        )

    def get_contract_price_current(
        self,
        *,
        contract_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_CONTRACT_PRICE_CURRENT_TABLE,
            lambda: self._transformation_service.get_contract_price_current(
                contract_type=contract_type,
                status=status,
            ),
            _build_where_clause(
                ("contract_type = %s", contract_type),
                ("status = %s", status),
            ),
            "ORDER BY contract_type, contract_name, price_component, valid_from",
        )

    def get_electricity_price_current(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_ELECTRICITY_PRICE_CURRENT_TABLE,
            self._transformation_service.get_electricity_price_current,
            ("", []),
            "ORDER BY contract_name, price_component, valid_from",
        )

    def get_utility_cost_summary(
        self,
        *,
        utility_type: str | None = None,
        meter_id: str | None = None,
        from_period: date | str | None = None,
        to_period: date | str | None = None,
        granularity: str = "month",
    ) -> list[dict[str, Any]]:
        if granularity not in {"day", "month"}:
            raise ValueError(f"Unsupported granularity: {granularity!r}")

        if self._access_mode == ReportingAccessMode.WAREHOUSE:
            return self._transformation_service.get_utility_cost_summary(
                utility_type=utility_type,
                meter_id=meter_id,
                from_period=from_period,
                to_period=to_period,
                granularity=granularity,
            )
        if self._publication_store is None or not self._publication_store.table_exists(
            MART_UTILITY_COST_SUMMARY_TABLE
        ):
            if self._access_mode == ReportingAccessMode.PUBLISHED:
                raise KeyError(
                    "Published reporting relation is unavailable: mart_utility_cost_summary"
                )
            return self._transformation_service.get_utility_cost_summary(
                utility_type=utility_type,
                meter_id=meter_id,
                from_period=from_period,
                to_period=to_period,
                granularity=granularity,
            )

        where_sql, params = _build_where_clause(
            ("utility_type = %s", utility_type),
            ("meter_id = %s", meter_id),
            ("period_start >= %s", from_period),
            ("period_end <= %s", to_period),
        )
        if granularity == "day":
            return self._publication_store.fetchall_dicts(
                f"""
                SELECT
                    period_day AS period,
                    period_start,
                    period_end,
                    meter_id,
                    meter_name,
                    utility_type,
                    usage_quantity,
                    usage_unit,
                    billed_amount,
                    currency,
                    unit_cost,
                    bill_count,
                    usage_record_count,
                    coverage_status
                FROM {MART_UTILITY_COST_SUMMARY_TABLE}
                {where_sql}
                ORDER BY period_day, meter_id
                """,
                params,
            )

        return self._publication_store.fetchall_dicts(
            f"""
            SELECT
                period_month AS period,
                MIN(period_start) AS period_start,
                MAX(period_end) AS period_end,
                meter_id,
                MIN(meter_name) AS meter_name,
                utility_type,
                SUM(usage_quantity) AS usage_quantity,
                MIN(usage_unit) AS usage_unit,
                SUM(billed_amount) AS billed_amount,
                MIN(currency) AS currency,
                CASE
                    WHEN SUM(usage_quantity) > 0
                    THEN ROUND(SUM(billed_amount) / SUM(usage_quantity), 4)
                    ELSE NULL
                END AS unit_cost,
                SUM(bill_count) AS bill_count,
                SUM(usage_record_count) AS usage_record_count,
                CASE
                    WHEN SUM(bill_count) > 0 AND SUM(usage_record_count) > 0 THEN 'matched'
                    WHEN SUM(bill_count) > 0 THEN 'bill_only'
                    ELSE 'usage_only'
                END AS coverage_status
            FROM {MART_UTILITY_COST_SUMMARY_TABLE}
            {where_sql}
            GROUP BY period_month, meter_id, utility_type
            ORDER BY period_month, meter_id
            """,
            params,
        )

    def get_current_dimension_rows(self, dimension_name: str) -> list[dict[str, Any]]:
        relation_name = CURRENT_DIMENSION_RELATIONS.get(dimension_name)
        if relation_name is None:
            raise KeyError(f"Unknown current dimension: {dimension_name}")
        relation = PUBLICATION_RELATIONS[relation_name]
        return self._fetch_published_or_fallback(
            relation.relation_name,
            lambda: self._transformation_service.get_current_dimension_rows(
                dimension_name
            ),
            ("", []),
            f"ORDER BY {relation.order_by}",
        )

    def get_transformation_audit(
        self,
        *,
        input_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            TRANSFORMATION_AUDIT_TABLE,
            lambda: self._transformation_service.get_transformation_audit(
                input_run_id=input_run_id
            ),
            _build_where_clause(("input_run_id = %s", input_run_id)),
            "ORDER BY started_at DESC",
        )

    def get_relation_rows(self, relation_name: str) -> list[dict[str, Any]]:
        relation = self._get_publication_relation(relation_name)
        return self._fetch_published_or_fallback(
            relation.relation_name,
            lambda: self._rows_from_relation_source(relation),
            ("", []),
            f"ORDER BY {relation.order_by}",
        )

    def record_reporting_lineage(
        self,
        *,
        run_id: str | None,
        relation_names: list[str],
    ) -> None:
        if run_id is None or self._control_plane_store is None:
            return
        if not isinstance(self._control_plane_store, SourceLineageStore):
            return
        self._control_plane_store.record_source_lineage(
            tuple(
                SourceLineageCreate(
                    lineage_id=uuid.uuid4().hex[:16],
                    input_run_id=run_id,
                    source_run_id=run_id,
                    target_layer="reporting",
                    target_name=relation_name,
                    target_kind=_relation_kind(relation_name),
                )
                for relation_name in relation_names
            )
        )

    def _fetch_published_or_fallback(
        self,
        relation_name: str,
        fallback: Callable[[], list[dict[str, Any]]],
        where_clause: tuple[str, list[Any]],
        order_by_sql: str,
    ) -> list[dict[str, Any]]:
        if self._access_mode == ReportingAccessMode.WAREHOUSE:
            return fallback()
        if self._publication_store is None or not self._publication_store.table_exists(
            relation_name
        ):
            if self._access_mode == ReportingAccessMode.PUBLISHED:
                raise KeyError(
                    f"Published reporting relation is unavailable: {relation_name}"
                )
            return fallback()
        where_sql, params = where_clause
        return self._publication_store.fetchall_dicts(
            f"SELECT * FROM {relation_name} {where_sql} {order_by_sql}",
            params,
        )

    def _publish_relation(self, relation_name: str) -> None:
        if self._publication_store is None:
            return
        relation = self._get_publication_relation(relation_name)
        rows = self._rows_from_relation_source(relation)
        self._publication_store.replace_rows(
            relation.relation_name,
            relation.columns,
            rows,
        )

    def _get_publication_relation(self, relation_name: str) -> PublicationRelation:
        relation = PUBLICATION_RELATIONS.get(relation_name)
        if relation is not None:
            return relation

        if self._extension_registry is None:
            raise ValueError(f"Unsupported publication relation: {relation_name}")

        publication = self._extension_registry.get_reporting_publication(relation_name)
        return PublicationRelation(
            relation_name=publication.relation_name,
            columns=list(publication.columns),
            order_by=publication.order_by,
            source_query=publication.source_query,
        )

    def _rows_from_relation_source(
        self,
        relation: PublicationRelation,
    ) -> list[dict[str, Any]]:
        if relation.source_query is not None:
            return self._transformation_service.store.fetchall_dicts(
                f"""
                SELECT *
                FROM ({relation.source_query}) AS published_relation
                ORDER BY {relation.order_by}
                """
            )

        return self._transformation_service.store.fetchall_dicts(
            f"SELECT * FROM {relation.relation_name} ORDER BY {relation.order_by}"
        )

    def _record_publication_audit(
        self,
        *,
        publication_key: str,
        relation_name: str,
        run_id: str | None,
        status: str,
    ) -> None:
        if self._control_plane_store is None:
            return
        if not isinstance(self._control_plane_store, PublicationAuditStore):
            return
        self._control_plane_store.record_publication_audit(
            (
                PublicationAuditCreate(
                    publication_audit_id=uuid.uuid4().hex[:16],
                    run_id=run_id,
                    publication_key=publication_key,
                    relation_name=relation_name,
                    status=status,
                ),
            )
        )


def _build_where_clause(
    *clauses: tuple[str, Any | None],
) -> tuple[str, list[Any]]:
    sql_clauses: list[str] = []
    params: list[Any] = []
    for clause, value in clauses:
        if value is None:
            continue
        sql_clauses.append(clause)
        params.append(value)
    if not sql_clauses:
        return "", []
    return f"WHERE {' AND '.join(sql_clauses)}", params


def _validate_extension_publication_conflicts(
    extension_registry: ExtensionRegistry | None,
) -> None:
    if extension_registry is None:
        return

    extension_relation_names = {
        publication.relation_name
        for publication in extension_registry.list_reporting_publications()
    }
    conflicts = set(PUBLICATION_RELATIONS) & extension_relation_names
    if conflicts:
        conflict_names = ", ".join(sorted(conflicts))
        raise ValueError(
            f"Extension publication relations conflict with built-in relations: {conflict_names}"
        )


def _relation_kind(relation_name: str) -> str:
    if relation_name == TRANSFORMATION_AUDIT_TABLE:
        return "audit"
    if relation_name.startswith("mart_"):
        return "mart"
    return "published_relation"
