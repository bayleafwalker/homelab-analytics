from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Callable

from packages.domains.finance.pipelines.contract_price_models import (
    MART_CONTRACT_PRICE_CURRENT_TABLE,
    MART_ELECTRICITY_PRICE_CURRENT_TABLE,
)
from packages.domains.finance.pipelines.loan_models import (
    MART_LOAN_OVERVIEW_TABLE,
    MART_LOAN_SCHEDULE_PROJECTED_TABLE,
)
from packages.domains.finance.pipelines.scenario_service import (
    build_homelab_cost_benefit_baseline_signature,
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
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
    TRANSFORMATION_AUDIT_TABLE,
)
from packages.domains.homelab.pipelines.homelab_models import (
    MART_BACKUP_FRESHNESS_TABLE,
    MART_SERVICE_HEALTH_CURRENT_TABLE,
    MART_STORAGE_RISK_TABLE,
    MART_WORKLOAD_COST_7D_TABLE,
)
from packages.domains.overview.pipelines.overview_models import (
    MART_CURRENT_OPERATING_BASELINE_TABLE,
    MART_HOMELAB_ROI_TABLE,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
)
from packages.domains.utilities.pipelines.utility_models import (
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
    MART_USAGE_VS_PRICE_SUMMARY_TABLE,
    MART_UTILITY_COST_SUMMARY_TABLE,
    MART_UTILITY_COST_TREND_MONTHLY_TABLE,
)
from packages.pipelines.household_reporting import (
    CURRENT_DIMENSION_RELATIONS,
    PUBLICATION_RELATIONS,
    PublicationRelation,
)
from packages.pipelines.promotion import PromotionResult
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionRegistry
from packages.storage.control_plane import (
    PublicationAuditCreate,
    PublicationAuditStore,
    SourceLineageCreate,
    SourceLineageStore,
)
from packages.storage.postgres_reporting import PostgresReportingStore

_AUDIT_TRIGGER_MARTS = frozenset(
    {"mart_monthly_cashflow", "mart_monthly_cashflow_by_counterparty"}
)


class ReportingAccessMode(StrEnum):
    PREFER_PUBLISHED = "prefer_published"
    PUBLISHED = "published"
    WAREHOUSE = "warehouse"


@dataclass(frozen=True)
class HomelabCostBenefitBaseline:
    service_rows: list[dict[str, Any]]
    workload_rows: list[dict[str, Any]]
    signature: str | None


@dataclass(frozen=True)
class ScalarMetricSnapshot:
    value: Decimal | None
    unit: str


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

    def get_current_month_net_cashflow(self) -> ScalarMetricSnapshot:
        rows = self.get_household_overview()
        latest_row = _latest_row(rows, "current_month")
        if latest_row is None:
            return ScalarMetricSnapshot(value=None, unit="")
        return ScalarMetricSnapshot(
            value=_decimal_or_none(latest_row.get("cashflow_net")),
            unit=str(latest_row.get("currency") or ""),
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

    def get_loan_schedule_projected(
        self,
        loan_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_LOAN_SCHEDULE_PROJECTED_TABLE,
            lambda: self._transformation_service.get_loan_schedule_projected(
                loan_id=loan_id
            ),
            _build_where_clause(("loan_id = %s", loan_id)),
            "ORDER BY loan_id, period",
        )

    def get_loan_overview(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_LOAN_OVERVIEW_TABLE,
            self._transformation_service.get_loan_overview,
            ("", []),
            "ORDER BY loan_name",
        )

    def get_next_loan_payment_amount(self) -> ScalarMetricSnapshot:
        rows = self.get_loan_schedule_projected()
        today = date.today()
        next_payment_date: date | None = None
        candidate_rows: list[dict[str, Any]] = []
        for row in rows:
            payment_date = _coerce_date(row.get("payment_date"))
            if payment_date is None or payment_date < today:
                continue
            if next_payment_date is None or payment_date < next_payment_date:
                next_payment_date = payment_date
                candidate_rows = [row]
            elif payment_date == next_payment_date:
                candidate_rows.append(row)
        if not candidate_rows:
            return ScalarMetricSnapshot(value=None, unit="")
        unit = _shared_unit(candidate_rows, "currency")
        if unit is None:
            return ScalarMetricSnapshot(value=None, unit="")
        total = sum(
            (_decimal_or_zero(row.get("payment")) for row in candidate_rows),
            Decimal("0"),
        )
        return ScalarMetricSnapshot(value=total, unit=unit)

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
                CAST(unit_cost AS DECIMAL(18,4)) AS unit_cost,
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
                    THEN CAST(ROUND(SUM(billed_amount) / SUM(usage_quantity), 4) AS DECIMAL(18,4))
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

    def get_current_month_electricity_cost(self) -> ScalarMetricSnapshot:
        rows = self.get_utility_cost_summary(
            utility_type="electricity",
            granularity="month",
        )
        latest_period = _latest_period(rows, _utility_period_label)
        if latest_period is None:
            return ScalarMetricSnapshot(value=None, unit="")
        selected_rows = [
            row
            for row in rows
            if _utility_period_label(row) == latest_period
        ]
        if not selected_rows:
            return ScalarMetricSnapshot(value=None, unit="")
        unit = _shared_unit(selected_rows, "currency")
        if unit is None:
            return ScalarMetricSnapshot(value=None, unit="")
        total = sum(
            (_decimal_or_zero(row.get("billed_amount")) for row in selected_rows),
            Decimal("0"),
        )
        return ScalarMetricSnapshot(value=total, unit=unit)

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

    # ------------------------------------------------------------------
    # Finance: new dedicated report methods
    # ------------------------------------------------------------------

    def get_spend_by_category_monthly(
        self,
        *,
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty_name: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
            lambda: self._transformation_service.get_spend_by_category_monthly(
                from_month=from_month,
                to_month=to_month,
                counterparty_name=counterparty_name,
                category=category,
            ),
            _build_where_clause(
                ("booking_month >= %s", from_month),
                ("booking_month <= %s", to_month),
                ("counterparty_name = %s", counterparty_name),
                ("category = %s", category),
            ),
            "ORDER BY booking_month, category, counterparty_name",
        )

    def get_recent_large_transactions(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_RECENT_LARGE_TRANSACTIONS_TABLE,
            self._transformation_service.get_recent_large_transactions,
            ("", []),
            "ORDER BY booked_at DESC",
        )

    def get_account_balance_trend(
        self,
        *,
        account_id: str | None = None,
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_ACCOUNT_BALANCE_TREND_TABLE,
            lambda: self._transformation_service.get_account_balance_trend(
                account_id=account_id,
                from_month=from_month,
                to_month=to_month,
            ),
            _build_where_clause(
                ("account_id = %s", account_id),
                ("booking_month >= %s", from_month),
                ("booking_month <= %s", to_month),
            ),
            "ORDER BY booking_month, account_id",
        )

    def get_transaction_anomalies_current(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
            self._transformation_service.get_transaction_anomalies_current,
            ("", []),
            "ORDER BY booked_at DESC",
        )

    # ------------------------------------------------------------------
    # Subscriptions / fixed costs
    # ------------------------------------------------------------------

    def get_upcoming_fixed_costs_30d(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_UPCOMING_FIXED_COSTS_30D_TABLE,
            self._transformation_service.get_upcoming_fixed_costs_30d,
            ("", []),
            "ORDER BY expected_date, contract_name",
        )

    # ------------------------------------------------------------------
    # Utilities: new dedicated report methods
    # ------------------------------------------------------------------

    def get_utility_cost_trend_monthly(
        self,
        *,
        utility_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_UTILITY_COST_TREND_MONTHLY_TABLE,
            lambda: self._transformation_service.get_utility_cost_trend_monthly(
                utility_type=utility_type,
            ),
            _build_where_clause(("utility_type = %s", utility_type)),
            "ORDER BY billing_month, utility_type",
        )

    def get_usage_vs_price_summary(
        self,
        *,
        utility_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_USAGE_VS_PRICE_SUMMARY_TABLE,
            lambda: self._transformation_service.get_usage_vs_price_summary(
                utility_type=utility_type,
            ),
            _build_where_clause(("utility_type = %s", utility_type)),
            "ORDER BY period, utility_type",
        )

    def get_contract_review_candidates(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
            self._transformation_service.get_contract_review_candidates,
            ("", []),
            "ORDER BY score DESC, contract_id",
        )

    def get_contract_renewal_watchlist(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
            self._transformation_service.get_contract_renewal_watchlist,
            ("", []),
            "ORDER BY renewal_date, contract_name",
        )

    # ------------------------------------------------------------------
    # Overview / household KPIs
    # ------------------------------------------------------------------

    def get_household_overview(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_HOUSEHOLD_OVERVIEW_TABLE,
            self._transformation_service.get_household_overview,
            ("", []),
            "ORDER BY current_month DESC",
        )

    def get_homelab_roi(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_HOMELAB_ROI_TABLE,
            self._transformation_service.get_homelab_roi,
            ("", []),
            "ORDER BY roi_state, service_count DESC",
        )

    def get_open_attention_items(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_OPEN_ATTENTION_ITEMS_TABLE,
            self._transformation_service.get_open_attention_items,
            ("", []),
            "ORDER BY severity, item_type",
        )

    def get_recent_significant_changes(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
            self._transformation_service.get_recent_significant_changes,
            ("", []),
            "ORDER BY period DESC, change_type",
        )

    def get_current_operating_baseline(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_CURRENT_OPERATING_BASELINE_TABLE,
            self._transformation_service.get_current_operating_baseline,
            ("", []),
            "ORDER BY baseline_type",
        )

    # ------------------------------------------------------------------
    # Homelab: service health, backups, storage, workloads
    # ------------------------------------------------------------------

    def get_service_health_current(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_SERVICE_HEALTH_CURRENT_TABLE,
            self._transformation_service.get_service_health_current,
            ("", []),
            "ORDER BY service_id",
        )

    def get_backup_freshness(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_BACKUP_FRESHNESS_TABLE,
            self._transformation_service.get_backup_freshness,
            ("", []),
            "ORDER BY target",
        )

    def get_storage_risk(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_STORAGE_RISK_TABLE,
            self._transformation_service.get_storage_risk,
            ("", []),
            "ORDER BY pct_used DESC",
        )

    def get_workload_cost_7d(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_WORKLOAD_COST_7D_TABLE,
            self._transformation_service.get_workload_cost_7d,
            ("", []),
            "ORDER BY est_monthly_cost DESC NULLS LAST",
        )

    def get_homelab_cost_benefit_baseline(self) -> HomelabCostBenefitBaseline:
        service_rows = self.get_service_health_current()
        workload_rows = self.get_workload_cost_7d()
        return HomelabCostBenefitBaseline(
            service_rows=service_rows,
            workload_rows=workload_rows,
            signature=build_homelab_cost_benefit_baseline_signature(
                service_rows=service_rows,
                workload_rows=workload_rows,
            ),
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


def _latest_row(
    rows: list[dict[str, Any]],
    field_name: str,
) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.get(field_name) is not None]
    if not candidates:
        return rows[0] if rows else None
    return max(candidates, key=lambda row: str(row.get(field_name) or ""))


def _latest_period(
    rows: list[dict[str, Any]],
    field_name: str | Callable[[dict[str, Any]], str],
) -> str | None:
    if callable(field_name):
        periods = [field_name(row) for row in rows if field_name(row)]
    else:
        periods = [str(row.get(field_name) or "") for row in rows if row.get(field_name)]
    return max(periods) if periods else None


def _utility_period_label(row: dict[str, Any]) -> str:
    return str(
        row.get("period_month")
        or row.get("period")
        or row.get("billing_month")
        or ""
    )


def _shared_unit(
    rows: list[dict[str, Any]],
    field_name: str,
) -> str | None:
    units = {str(row.get(field_name) or "").strip() for row in rows}
    units.discard("")
    if not units:
        return ""
    if len(units) > 1:
        return None
    return next(iter(units))


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _decimal_or_zero(value: Any) -> Decimal:
    parsed = _decimal_or_none(value)
    return parsed if parsed is not None else Decimal("0")


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None
