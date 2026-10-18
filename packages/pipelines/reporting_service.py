from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Callable

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
from packages.domains.homelab.pipelines.ha_models import (
    DIM_HA_ENTITY_TABLE,
    FACT_HA_STATE_CHANGE_TABLE,
)
from packages.domains.homelab.pipelines.ha_service import get_ha_state_changes_since
from packages.domains.homelab.pipelines.homelab_models import (
    MART_BACKUP_FRESHNESS_TABLE,
    MART_SERVICE_HEALTH_CURRENT_TABLE,
    MART_STORAGE_RISK_TABLE,
    MART_WORKLOAD_COST_7D_TABLE,
)
from packages.domains.overview.pipelines.overview_models import (
    MART_AFFORDABILITY_RATIOS_TABLE,
    MART_COST_TREND_12M_TABLE,
    MART_CURRENT_OPERATING_BASELINE_TABLE,
    MART_HOMELAB_ROI_TABLE,
    MART_HOUSEHOLD_COST_MODEL_TABLE,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
    MART_RECURRING_COST_BASELINE_TABLE,
)
from packages.domains.overview.pipelines.scenario_service_overview import (
    build_homelab_cost_benefit_baseline_signature,
)
from packages.domains.utilities.pipelines.battery_plan_models import (
    MART_BATTERY_PLAN_OUTCOME_TABLE,
    MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE,
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
from packages.pipelines.mart_read_registry import (
    MartReadRegistry,
    get_default_mart_read_registry,
    read_warehouse_mart,
)
from packages.pipelines.promotion import PromotionResult
from packages.pipelines.reporting_snapshots import (
    DEFAULT_SNAPSHOT_RETENTION_MONTHS,
    SNAPSHOT_PUBLICATIONS,
    PublicationSnapshot,
    PublicationSnapshotStore,
    is_reference_month,
    read_warehouse_snapshot,
    record_warehouse_snapshot,
    warehouse_reference_month,
    warehouse_snapshot_months,
)
from packages.pipelines.transformation_service import TransformationService

if TYPE_CHECKING:
    from packages.domains.finance.pipelines.scenario_service import (
        ComparisonResult,
        IncomeCashflowComparison,
    )
    from packages.domains.overview.pipelines.scenario_models_overview import (
        HomelabCostBenefitComparison,
    )
from packages.shared.extensions import ExtensionRegistry
from packages.shared.metrics import metrics_registry
from packages.storage.control_plane import (
    PublicationAuditCreate,
    PublicationAuditStore,
    SourceLineageCreate,
    SourceLineageStore,
)
from packages.storage.postgres_reporting import PostgresReportingStore

_logger = logging.getLogger("homelab_analytics.reporting_service")

_AUDIT_TRIGGER_MARTS = frozenset(
    {"mart_monthly_cashflow", "mart_monthly_cashflow_by_counterparty"}
)

# Overview composition marts are refreshed via refresh_publication_keys in each
# capability pack but never listed in publication_keys, so they are never pushed
# to Postgres by publish_publications. Detect them in marts_refreshed and push
# them as auxiliary relations so the PUBLISHED access mode can serve them.
_OVERVIEW_COMPOSITION_MARTS = frozenset({
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
    MART_CURRENT_OPERATING_BASELINE_TABLE,
})


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


PUBLICATION_REFRESH_DURATION_METRIC = (
    "homelab_analytics_publication_refresh_duration_seconds"
)
_PUBLICATION_REFRESH_DURATION_HELP = (
    "Duration of publishing a promotion's publications to the reporting layer, "
    "by outcome."
)


def publish_promotion_reporting(
    reporting_service: "ReportingService | None",
    promotion: PromotionResult | None,
) -> list[str]:
    if reporting_service is None or promotion is None:
        return []
    started = time.perf_counter()
    outcome = "error"
    try:
        published = _publish_promotion_reporting(reporting_service, promotion)
        outcome = "success"
        return published
    finally:
        metrics_registry.observe(
            PUBLICATION_REFRESH_DURATION_METRIC,
            time.perf_counter() - started,
            help_text=_PUBLICATION_REFRESH_DURATION_HELP,
            labels={"outcome": outcome},
        )


def _publish_promotion_reporting(
    reporting_service: "ReportingService",
    promotion: PromotionResult,
) -> list[str]:
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
    overview_mats_to_push = sorted(
        _OVERVIEW_COMPOSITION_MARTS & set(promotion.marts_refreshed)
    )
    if overview_mats_to_push:
        try:
            published.extend(
                reporting_service.publish_auxiliary_relations(
                    overview_mats_to_push,
                    run_id=promotion.run_id,
                )
            )
        except TypeError:
            published.extend(
                reporting_service.publish_auxiliary_relations(overview_mats_to_push)
            )
    served = list(published)
    if not served and hasattr(reporting_service, "record_warehouse_publications"):
        # DuckDB path: nothing is pushed to a separate store; the refreshed
        # warehouse marts are what the API serves. Audit them so lineage and
        # confidence can see the run behind each publication.
        served = reporting_service.record_warehouse_publications(
            _dedupe([*promotion.publication_keys, *promotion.marts_refreshed]),
            run_id=promotion.run_id,
        )
    if hasattr(reporting_service, "record_reporting_lineage"):
        reporting_service.record_reporting_lineage(
            run_id=promotion.run_id,
            relation_names=served,
            source_asset_id=promotion.source_asset_id,
        )
    if hasattr(reporting_service, "capture_publication_snapshots"):
        reporting_service.capture_publication_snapshots(
            _dedupe([*promotion.marts_refreshed, *promotion.publication_keys]),
            run_id=promotion.run_id,
        )
    return published


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


class ReportingService:
    def __init__(
        self,
        transformation_service: TransformationService,
        publication_store: PostgresReportingStore | None = None,
        extension_registry: ExtensionRegistry | None = None,
        access_mode: ReportingAccessMode = ReportingAccessMode.PREFER_PUBLISHED,
        control_plane_store: SourceLineageStore | PublicationAuditStore | None = None,
        snapshot_retention_months: int = DEFAULT_SNAPSHOT_RETENTION_MONTHS,
        mart_read_registry: MartReadRegistry | None = None,
    ) -> None:
        self._transformation_service = transformation_service
        self._mart_read_registry = mart_read_registry or get_default_mart_read_registry()
        self._publication_store = publication_store
        self._extension_registry = extension_registry
        self._access_mode = access_mode
        self._control_plane_store = control_plane_store
        self._snapshot_retention_months = snapshot_retention_months
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
            lambda: self._read_mart(
                MART_MONTHLY_CASHFLOW_TABLE,
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
            lambda: self._read_mart(
                MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
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
            lambda: self._read_mart(
                MART_SUBSCRIPTION_SUMMARY_TABLE,
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
            lambda: self._read_mart(
                MART_CONTRACT_PRICE_CURRENT_TABLE,
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
            lambda: self._read_mart(MART_ELECTRICITY_PRICE_CURRENT_TABLE),
            ("", []),
            "ORDER BY contract_name, price_component, valid_from",
        )

    def get_loan_schedule_projected(
        self,
        loan_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_LOAN_SCHEDULE_PROJECTED_TABLE,
            lambda: self._read_mart(MART_LOAN_SCHEDULE_PROJECTED_TABLE, loan_id=loan_id),
            _build_where_clause(("loan_id = %s", loan_id)),
            "ORDER BY loan_id, period",
        )

    def get_loan_overview(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_LOAN_OVERVIEW_TABLE,
            lambda: self._read_mart(MART_LOAN_OVERVIEW_TABLE),
            ("", []),
            "ORDER BY loan_name",
        )

    def get_loan_repayment_variance(
        self,
        loan_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_LOAN_REPAYMENT_VARIANCE_TABLE,
            lambda: self._read_mart(MART_LOAN_REPAYMENT_VARIANCE_TABLE, loan_id=loan_id),
            _build_where_clause(("loan_id = %s", loan_id)),
            "ORDER BY loan_id, repayment_month",
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
            return self._read_mart(
                MART_UTILITY_COST_SUMMARY_TABLE,
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
            return self._read_mart(
                MART_UTILITY_COST_SUMMARY_TABLE,
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

    def get_current_categories(self) -> list[dict[str, Any]]:
        """Current category dimension rows for the category management API.

        Categories are operator-managed (``POST /api/categories`` writes the
        warehouse dimension directly), so this read stays on the warehouse view
        to make operator writes visible immediately instead of waiting for the
        next publication of ``rpt_current_dim_category``.
        """
        return self._transformation_service.get_current_dimension_rows("dim_category")

    # ------------------------------------------------------------------
    # Scenario read models
    # Scenario state and projections are written by the scenario service in
    # the warehouse; app-facing reads go through these methods.
    # ------------------------------------------------------------------

    def list_scenarios(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        return self._transformation_service.list_scenarios(include_archived=include_archived)

    def list_scenario_compare_sets(
        self,
        *,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        return self._transformation_service.list_scenario_compare_sets(
            include_archived=include_archived
        )

    def get_scenario(self, scenario_id: str) -> dict[str, Any] | None:
        return self._transformation_service.get_scenario(scenario_id)

    def get_scenario_assumptions(self, scenario_id: str) -> list[dict[str, Any]]:
        return self._transformation_service.get_scenario_assumptions(scenario_id)

    def get_scenario_view(
        self,
        scenario_id: str,
        *,
        view: str,
        current_baseline_run_id: str | None = None,
    ) -> ComparisonResult | IncomeCashflowComparison | HomelabCostBenefitComparison | None:
        """Render a scenario's ``comparison`` or ``cashflow`` view.

        The scenario registry picks the domain-pack view for the stored
        scenario type; ``current_baseline_run_id`` is used only by types that
        compare against a live baseline (homelab cost/benefit).
        """
        result: (
            ComparisonResult | IncomeCashflowComparison | HomelabCostBenefitComparison | None
        ) = self._transformation_service.get_scenario_view(
            scenario_id,
            view=view,
            current_baseline_run_id=current_baseline_run_id,
        )
        return result

    def get_transformation_audit(
        self,
        *,
        input_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            TRANSFORMATION_AUDIT_TABLE,
            lambda: self._read_mart(TRANSFORMATION_AUDIT_TABLE, input_run_id=input_run_id),
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
            lambda: self._read_mart(
                MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
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
            lambda: self._read_mart(MART_RECENT_LARGE_TRANSACTIONS_TABLE),
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
            lambda: self._read_mart(
                MART_ACCOUNT_BALANCE_TREND_TABLE,
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

    def get_spend_by_weekday_hour(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_SPEND_BY_WEEKDAY_HOUR_TABLE,
            lambda: self._read_mart(
                MART_SPEND_BY_WEEKDAY_HOUR_TABLE,
                from_date=from_date,
                to_date=to_date,
            ),
            _build_where_clause(
                ("booked_at >= %s", from_date),
                ("booked_at <= %s", to_date),
            ),
            "ORDER BY booked_at, hour_of_day NULLS FIRST",
        )

    def get_transaction_anomalies_current(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
            lambda: self._read_mart(MART_TRANSACTION_ANOMALIES_CURRENT_TABLE),
            ("", []),
            "ORDER BY booking_date DESC",
        )

    # ------------------------------------------------------------------
    # Subscriptions / fixed costs
    # ------------------------------------------------------------------

    def get_upcoming_fixed_costs_30d(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_UPCOMING_FIXED_COSTS_30D_TABLE,
            lambda: self._read_mart(MART_UPCOMING_FIXED_COSTS_30D_TABLE),
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
            lambda: self._read_mart(
                MART_UTILITY_COST_TREND_MONTHLY_TABLE,
                utility_type=utility_type,
            ),
            _build_where_clause(("utility_type = %s", utility_type)),
            "ORDER BY billing_month, utility_type",
        )

    def get_battery_plan_outcome(
        self,
        *,
        decision_month: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_BATTERY_PLAN_OUTCOME_TABLE,
            lambda: self._read_mart(
                MART_BATTERY_PLAN_OUTCOME_TABLE,
                decision_month=decision_month,
            ),
            _build_where_clause(("decision_month = %s", decision_month)),
            "ORDER BY decision_month DESC",
        )

    def get_battery_plan_outcome_values(
        self,
        *,
        decision_month: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE,
            lambda: self._read_mart(
                MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE,
                decision_month=decision_month,
            ),
            _build_where_clause(("decision_month = %s", decision_month)),
            "ORDER BY decision_month DESC, display_order",
        )

    def get_usage_vs_price_summary(
        self,
        *,
        utility_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_USAGE_VS_PRICE_SUMMARY_TABLE,
            lambda: self._read_mart(
                MART_USAGE_VS_PRICE_SUMMARY_TABLE,
                utility_type=utility_type,
            ),
            _build_where_clause(("utility_type = %s", utility_type)),
            "ORDER BY period, utility_type",
        )

    def get_contract_review_candidates(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
            lambda: self._read_mart(MART_CONTRACT_REVIEW_CANDIDATES_TABLE),
            ("", []),
            "ORDER BY score DESC, contract_id",
        )

    def get_contract_renewal_watchlist(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
            lambda: self._read_mart(MART_CONTRACT_RENEWAL_WATCHLIST_TABLE),
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

    def get_household_cost_model(
        self,
        *,
        period_label: str | None = None,
        cost_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_HOUSEHOLD_COST_MODEL_TABLE,
            lambda: self._transformation_service.get_household_cost_model(
                period_label=period_label,
                cost_type=cost_type,
            ),
            _build_where_clause(
                ("period_label = %s", period_label),
                ("cost_type = %s", cost_type),
            ),
            "ORDER BY period_label, cost_type",
        )

    def get_cost_trend_12m(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_COST_TREND_12M_TABLE,
            self._transformation_service.get_cost_trend_12m,
            ("", []),
            "ORDER BY period_label, cost_type",
        )

    def get_affordability_ratios(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_AFFORDABILITY_RATIOS_TABLE,
            self._transformation_service.get_affordability_ratios,
            ("", []),
            "ORDER BY ratio_name",
        )

    def get_recurring_cost_baseline(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_RECURRING_COST_BASELINE_TABLE,
            self._transformation_service.get_recurring_cost_baseline,
            ("", []),
            "ORDER BY cost_source, counterparty_or_contract",
        )

    # ------------------------------------------------------------------
    # Budget
    # ------------------------------------------------------------------

    def get_budget_variance(
        self,
        *,
        budget_name: str | None = None,
        category_id: str | None = None,
        period_label: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_BUDGET_VARIANCE_TABLE,
            lambda: self._read_mart(
                MART_BUDGET_VARIANCE_TABLE,
                budget_name=budget_name,
                category_id=category_id,
                period_label=period_label,
            ),
            _build_where_clause(
                ("budget_name = %s", budget_name),
                ("category_id = %s", category_id),
                ("period_label = %s", period_label),
            ),
            "ORDER BY budget_name, category_id, period_label",
        )

    def get_budget_envelope_drift(
        self,
        *,
        budget_name: str | None = None,
        category_id: str | None = None,
        period_label: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_BUDGET_ENVELOPE_DRIFT_TABLE,
            lambda: self._read_mart(
                MART_BUDGET_ENVELOPE_DRIFT_TABLE,
                budget_name=budget_name,
                category_id=category_id,
                period_label=period_label,
            ),
            _build_where_clause(
                ("budget_name = %s", budget_name),
                ("category_id = %s", category_id),
                ("period_label = %s", period_label),
            ),
            "ORDER BY budget_name, category_id, period_label",
        )

    def get_budget_progress_current(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_BUDGET_PROGRESS_CURRENT_TABLE,
            lambda: self._read_mart(MART_BUDGET_PROGRESS_CURRENT_TABLE),
            ("", []),
            "ORDER BY budget_name, category_id",
        )

    # ------------------------------------------------------------------
    # Homelab: service health, backups, storage, workloads
    # ------------------------------------------------------------------

    def get_service_health_current(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_SERVICE_HEALTH_CURRENT_TABLE,
            lambda: self._read_mart(MART_SERVICE_HEALTH_CURRENT_TABLE),
            ("", []),
            "ORDER BY service_id",
        )

    def get_backup_freshness(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_BACKUP_FRESHNESS_TABLE,
            lambda: self._read_mart(MART_BACKUP_FRESHNESS_TABLE),
            ("", []),
            "ORDER BY target",
        )

    def get_storage_risk(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_STORAGE_RISK_TABLE,
            lambda: self._read_mart(MART_STORAGE_RISK_TABLE),
            ("", []),
            "ORDER BY pct_used DESC",
        )

    def get_workload_cost_7d(self) -> list[dict[str, Any]]:
        return self._fetch_published_or_fallback(
            MART_WORKLOAD_COST_7D_TABLE,
            lambda: self._read_mart(MART_WORKLOAD_COST_7D_TABLE),
            ("", []),
            "ORDER BY est_monthly_cost DESC NULLS LAST",
        )

    # ------------------------------------------------------------------
    # HA entity reads — DuckDB-only, no published mart
    # ------------------------------------------------------------------

    def ingest_ha_states(
        self,
        states: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str = "home_assistant",
    ) -> int:
        return self._transformation_service.ingest_ha_states(
            states, run_id=run_id, source_system=source_system
        )

    def get_ha_entities(self) -> list[dict[str, Any]]:
        return self._read_mart(DIM_HA_ENTITY_TABLE)

    def get_ha_entity_history(
        self,
        entity_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self._read_mart(FACT_HA_STATE_CHANGE_TABLE, entity_id=entity_id, limit=limit)

    def get_ha_state_changes_since(
        self,
        entity_ids: list[str],
        *,
        since: datetime,
    ) -> list[dict[str, Any]]:
        # Domain read over the warehouse store, not a facade method: the
        # TransformationService surface is shrink-only (#50).
        return get_ha_state_changes_since(
            self._transformation_service.store, entity_ids, since=since
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
        source_asset_id: str | None = None,
    ) -> None:
        """Record run → reporting lineage, plus the landing hop when known.

        ``source_asset_id`` adds one landing-layer row (the source asset the
        run was landed for), so the lineage graph reads source asset → run →
        transformation → publication. Reporting rows keep ``source_system``
        unset; confidence attributes them to the run's source asset.

        The refresh recorded its confidence snapshots before this lineage
        existed, so the snapshots for ``relation_names`` are recorded again
        once it is stored.
        """
        if run_id is None or self._control_plane_store is None:
            return
        if not isinstance(self._control_plane_store, SourceLineageStore):
            return
        records = [
            SourceLineageCreate(
                lineage_id=uuid.uuid4().hex[:16],
                input_run_id=run_id,
                source_run_id=run_id,
                target_layer="reporting",
                target_name=relation_name,
                target_kind=_relation_kind(relation_name),
            )
            for relation_name in relation_names
        ]
        if source_asset_id and relation_names:
            records.append(
                SourceLineageCreate(
                    lineage_id=uuid.uuid4().hex[:16],
                    input_run_id=run_id,
                    source_run_id=run_id,
                    target_layer="landing",
                    target_name=source_asset_id,
                    target_kind="source_asset",
                )
            )
        if records:
            self._control_plane_store.record_source_lineage(tuple(records))
            record_confidence = getattr(
                self._transformation_service, "record_publication_confidence", None
            )
            if record_confidence is not None:
                record_confidence(relation_names)

    def record_warehouse_publications(
        self,
        relation_names: list[str],
        *,
        run_id: str | None = None,
    ) -> list[str]:
        """Audit warehouse-served publications on the DuckDB path.

        With a Postgres reporting store, ``publish_publications`` audits each
        relation it pushes. Without one, the warehouse marts are served
        directly and nothing was audited, so the lineage graph had no run
        behind any publication. Returns the relations audited.
        """
        if self._publication_store is not None or run_id is None:
            return []
        audited: list[str] = []
        for relation_name in relation_names:
            if not self._is_known_relation(relation_name):
                continue
            self._record_publication_audit(
                publication_key=relation_name,
                relation_name=relation_name,
                run_id=run_id,
                status="warehouse",
            )
            audited.append(relation_name)
        return audited

    # ------------------------------------------------------------------
    # As-of snapshots of current-only publications
    # ------------------------------------------------------------------

    def capture_publication_snapshots(
        self,
        relation_names: list[str],
        *,
        run_id: str | None = None,
        captured_at: datetime | None = None,
    ) -> list[str]:
        """Snapshot the refreshed current-only publications.

        Only relations in ``SNAPSHOT_PUBLICATIONS`` are captured, and only
        once the household has a published month to key them by. A failed
        snapshot is logged and never fails the publication refresh.
        """
        targets = sorted({name for name in relation_names if name in SNAPSHOT_PUBLICATIONS})
        if not targets:
            return []
        reference_month = self._warehouse_reference_month()
        if reference_month is None:
            return []
        stamp = (captured_at or datetime.now(UTC)).astimezone(UTC).isoformat()
        published_store = (
            PublicationSnapshotStore.for_postgres(self._publication_store)
            if self._publication_store is not None
            else None
        )
        captured: list[str] = []
        for relation_name in targets:
            try:
                rows = self._rows_from_relation_source(
                    self._get_publication_relation(relation_name)
                )
                snapshot = PublicationSnapshot(
                    publication_key=relation_name,
                    reference_month=reference_month,
                    captured_at=stamp,
                    run_id=run_id,
                    rows=rows,
                )
                record_warehouse_snapshot(
                    self._transformation_service,
                    snapshot,
                    retention_months=self._snapshot_retention_months,
                )
                if published_store is not None:
                    published_store.write(
                        snapshot,
                        retention_months=self._snapshot_retention_months,
                    )
            except Exception:
                _logger.warning("snapshot capture failed for %s", relation_name, exc_info=True)
                continue
            captured.append(relation_name)
        return captured

    def get_publication_snapshot(
        self,
        relation_name: str,
        reference_month: str,
    ) -> PublicationSnapshot | None:
        """Rows of ``relation_name`` as published for ``reference_month``.

        ``None`` means no snapshot exists for that month (before the first
        capture, or pruned by retention). Callers report "no history" rather
        than substituting current rows.

        WAREHOUSE reads the DuckDB copy. PUBLISHED reads only the Postgres
        copy and has no history until that table exists. PREFER_PUBLISHED
        reads the Postgres copy when present, else the warehouse.
        """
        if not is_reference_month(reference_month):
            raise ValueError("reference_month must be YYYY-MM")
        published_store = self._published_snapshot_store()
        if published_store is not None:
            return published_store.read(relation_name, reference_month)
        if self._access_mode == ReportingAccessMode.PUBLISHED:
            return None
        return read_warehouse_snapshot(
            self._transformation_service, relation_name, reference_month
        )

    def list_publication_snapshot_months(self, relation_name: str) -> list[str]:
        published_store = self._published_snapshot_store()
        if published_store is not None:
            return published_store.months(relation_name)
        if self._access_mode == ReportingAccessMode.PUBLISHED:
            return []
        return warehouse_snapshot_months(self._transformation_service, relation_name)

    def _published_snapshot_store(self) -> PublicationSnapshotStore | None:
        if self._access_mode == ReportingAccessMode.WAREHOUSE or self._publication_store is None:
            return None
        store = PublicationSnapshotStore.for_postgres(self._publication_store)
        return store if store.exists() else None

    def _warehouse_reference_month(self) -> str | None:
        try:
            return warehouse_reference_month(self._transformation_service)
        except Exception:
            _logger.warning("snapshot capture skipped: warehouse unreadable", exc_info=True)
            return None

    def _is_known_relation(self, relation_name: str) -> bool:
        try:
            self._get_publication_relation(relation_name)
        except (KeyError, ValueError):
            return False
        return True

    def sample_publication_rows(
        self,
        relation_name: str,
        *,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int | None] | None:
        """Bounded sample of a publication relation for agent surfaces.

        Prefers the published store; falls back to the warehouse relation
        source. Returns ``None`` when the relation is not materialized
        anywhere yet (e.g. the mart's domain has no ingested data), so
        callers can serve the contract without sample values.
        """
        if limit <= 0:
            return None
        if (
            self._access_mode != ReportingAccessMode.WAREHOUSE
            and self._publication_store is not None
            and self._publication_store.table_exists(relation_name)
        ):
            rows = self._publication_store.fetchall_dicts(
                f"SELECT * FROM {relation_name} LIMIT %s", [limit]
            )
            counted = self._publication_store.fetchall_dicts(
                f"SELECT COUNT(*) AS row_count FROM {relation_name}"
            )
            total = int(counted[0]["row_count"]) if counted else None
            return rows, total
        try:
            relation = self._get_publication_relation(relation_name)
            rows = self._rows_from_relation_source(relation)
        except Exception:
            # Sampling is best-effort: an unknown relation or a warehouse
            # table that has not been created yet is not an error for the
            # agent index, it is simply a publication without samples.
            return None
        return rows[:limit], len(rows)

    def _read_mart(self, relation_name: str, **filters: Any) -> list[dict[str, Any]]:
        """Warehouse read through the pack-owned mart reader, on one leased handle."""
        return read_warehouse_mart(
            self._transformation_service,
            relation_name,
            registry=self._mart_read_registry,
            **filters,
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
