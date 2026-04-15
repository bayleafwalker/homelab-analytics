"""Transformation service facade over domain-specific warehouse processors."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from packages.domains.finance.pipelines.budget_models import (
    CURRENT_DIM_BUDGET_VIEW,
    DIM_BUDGET,
)
from packages.domains.finance.pipelines.category_rules import (
    add_category_rule,
    backfill_counterparty_categories,
    ensure_category_storage,
    list_category_overrides,
    list_category_rules,
    remove_category_override,
    remove_category_rule,
    resolve_categories_bulk,
    set_category_override,
)
from packages.domains.finance.pipelines.category_seed import seed_system_categories
from packages.domains.finance.pipelines.loan_models import (
    CURRENT_DIM_LOAN_VIEW,
    DIM_LOAN,
)
from packages.domains.finance.pipelines.scenario_service import (
    ComparisonResult,
    ExpenseShockResult,
    IncomeCashflowComparison,
    IncomeScenarioResult,
    ScenarioCompareSetResult,
    ScenarioResult,
    archive_scenario,
    archive_scenario_compare_set,
    create_expense_shock_scenario,
    create_income_change_scenario,
    create_loan_what_if_scenario,
    create_scenario_compare_set,
    ensure_scenario_storage,
    get_expense_shock_comparison,
    get_income_scenario_comparison,
    get_scenario,
    get_scenario_assumptions,
    get_scenario_comparison,
    list_scenario_compare_sets,
    list_scenarios,
    restore_scenario_compare_set,
    update_scenario_compare_set_label,
)
from packages.domains.overview.pipelines.scenario_models_overview import (
    HomelabCostBenefitComparison,
    HomelabCostBenefitResult,
    TariffShockResult,
)
from packages.domains.overview.pipelines.scenario_service_overview import (
    create_homelab_cost_benefit_scenario,
    create_tariff_shock_scenario,
    get_homelab_cost_benefit_comparison,
    get_tariff_shock_comparison,
)
from packages.domains.finance.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
    CURRENT_DIM_CONTRACT_VIEW,
    DIM_CATEGORY,
    DIM_CONTRACT,
)
from packages.domains.finance.pipelines.transaction_models import (
    CURRENT_DIM_ACCOUNT_VIEW,
    CURRENT_DIM_COUNTERPARTY_VIEW,
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    TRANSFORMATION_AUDIT_TABLE,
)
from packages.domains.finance.pipelines.transformation_balances import (
    ensure_balance_storage,
    get_balance_snapshot,
    refresh_balance_snapshot,
)
from packages.domains.finance.pipelines.transformation_budgets import (
    count_budget_targets,
    ensure_budget_storage,
    get_budget_envelope_drift,
    get_budget_progress_current,
    get_budget_variance,
    load_budget_targets,
    refresh_budget_envelope_drift,
    refresh_budget_progress_current,
    refresh_budget_variance,
)
from packages.domains.finance.pipelines.transformation_contract_prices import (
    count_contract_prices,
    ensure_contract_price_storage,
    get_contract_price_current,
    get_electricity_price_current,
    load_contract_prices,
    refresh_contract_price_current,
)
from packages.domains.finance.pipelines.transformation_loans import (
    count_loan_repayments,
    ensure_loan_storage,
    get_loan_overview,
    get_loan_repayment_variance,
    get_loan_schedule_projected,
    load_loan_repayments,
    refresh_loan_overview,
    refresh_loan_repayment_variance,
    refresh_loan_schedule_projected,
)
from packages.domains.finance.pipelines.transformation_subscriptions import (
    count_subscriptions,
    ensure_subscription_storage,
    get_subscription_summary,
    get_upcoming_fixed_costs_30d,
    load_subscriptions,
    refresh_subscription_summary,
    refresh_upcoming_fixed_costs_30d,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    count_transactions,
    ensure_transaction_storage,
    get_account_balance_trend,
    get_monthly_cashflow,
    get_monthly_cashflow_by_counterparty,
    get_recent_large_transactions,
    get_spend_by_category_monthly,
    get_transaction_anomalies_current,
    get_transactions,
    load_transactions,
    populate_counterparty_category_ids,
    refresh_account_balance_trend,
    refresh_monthly_cashflow,
    refresh_monthly_cashflow_by_counterparty,
    refresh_recent_large_transactions,
    refresh_spend_by_category_monthly,
    refresh_transaction_anomalies_current,
)
from packages.domains.homelab.pipelines.ha_service import (
    ensure_ha_storage,
    get_ha_entities,
    get_ha_entity_history,
    ingest_ha_states,
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
)
from packages.domains.homelab.pipelines.transformation_home_automation import (
    count_automation_event_rows,
    count_home_automation_state_rows,
    count_sensor_reading_rows,
    ensure_home_automation_storage,
    get_current_entities,
    load_automation_events,
    load_home_automation_state_rows,
    load_sensor_readings,
)
from packages.domains.homelab.pipelines.transformation_homelab import (
    count_backup_run_rows,
    count_service_health_rows,
    count_storage_sensor_rows,
    count_workload_sensor_rows,
    ensure_homelab_storage,
    get_backup_freshness,
    get_current_services,
    get_current_workloads,
    get_service_health_current,
    get_storage_risk,
    get_workload_cost_7d,
    load_backup_run_rows,
    load_service_health_rows,
    load_storage_sensor_rows,
    load_workload_sensor_rows,
    refresh_backup_freshness,
    refresh_service_health_current,
    refresh_storage_risk,
    refresh_workload_cost_7d,
)
from packages.domains.homelab.pipelines.transformation_infrastructure import (
    count_cluster_metric_rows,
    count_power_consumption_rows,
    ensure_infrastructure_storage,
    get_current_devices,
    get_current_nodes,
    load_cluster_metric_rows,
    load_power_consumption_rows,
)
from packages.domains.overview.pipelines.transformation_overview import (
    ensure_overview_storage,
    get_affordability_ratios,
    get_cost_trend_12m,
    get_current_operating_baseline,
    get_homelab_roi,
    get_household_cost_model,
    get_household_overview,
    get_open_attention_items,
    get_recent_significant_changes,
    get_recurring_cost_baseline,
    refresh_affordability_ratios,
    refresh_cost_trend_12m,
    refresh_current_operating_baseline,
    refresh_homelab_roi,
    refresh_household_cost_model,
    refresh_household_overview,
    refresh_open_attention_items,
    refresh_recent_significant_changes,
    refresh_recurring_cost_baseline,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    count_bills,
    count_utility_usage,
    ensure_utility_storage,
    get_contract_renewal_watchlist,
    get_contract_review_candidates,
    get_usage_vs_price_summary,
    get_utility_cost_summary,
    get_utility_cost_trend_monthly,
    load_bills,
    load_utility_usage,
    refresh_contract_renewal_watchlist,
    refresh_contract_review_candidates,
    refresh_usage_vs_price_summary,
    refresh_utility_cost_summary,
    refresh_utility_cost_trend_monthly,
)
from packages.domains.utilities.pipelines.utility_models import (
    CURRENT_DIM_METER_VIEW,
    DIM_METER,
)
from packages.pipelines.asset_models import (
    CURRENT_DIM_ASSET_VIEW,
    DIM_ASSET,
)
from packages.pipelines.normalization import (
    normalize_currency_code,
    normalize_timestamp_utc,
)
from packages.pipelines.publication_confidence_service import (
    compute_and_record_publication_confidence,
)
from packages.pipelines.reconciliation import reconcile_batch
from packages.pipelines.transformation_assets import (
    count_asset_event_rows,
    ensure_asset_storage,
    get_current_assets,
    load_asset_event_rows,
    load_asset_register_rows,
)
from packages.pipelines.transformation_domain_registry import (
    TransformationDomainRegistry,
    get_default_transformation_domain_registry,
)
from packages.pipelines.transformation_household import (
    ensure_household_member_storage,
    get_household_members,
    seed_default_household_member,
    upsert_household_member,
)
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshRegistry,
    get_default_publication_refresh_registry,
)
from packages.storage.control_plane import ControlPlaneStore, SourceLineageCreate
from packages.storage.duckdb_store import DuckDBStore


class TransformationService:
    """Loads validated landing data into the transformation and reporting layers."""

    def __init__(
        self,
        store: DuckDBStore,
        *,
        control_plane_store: ControlPlaneStore | None = None,
        publication_refresh_registry: PublicationRefreshRegistry | None = None,
        domain_registry: TransformationDomainRegistry | None = None,
    ) -> None:
        self._store = store
        self._control_plane_store = control_plane_store
        self._publication_refresh_registry = (
            publication_refresh_registry or get_default_publication_refresh_registry()
        )
        self._domain_registry = domain_registry or get_default_transformation_domain_registry()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._store.ensure_dimension(DIM_ACCOUNT)
        self._store.ensure_dimension(DIM_COUNTERPARTY)
        self._store.ensure_current_dimension_view(DIM_ACCOUNT, CURRENT_DIM_ACCOUNT_VIEW)
        self._store.ensure_current_dimension_view(
            DIM_COUNTERPARTY,
            CURRENT_DIM_COUNTERPARTY_VIEW,
        )
        ensure_transaction_storage(self._store)

        self._store.ensure_dimension(DIM_CATEGORY)
        self._store.ensure_dimension(DIM_CONTRACT)
        self._store.ensure_current_dimension_view(DIM_CATEGORY, CURRENT_DIM_CATEGORY_VIEW)
        self._store.ensure_current_dimension_view(DIM_CONTRACT, CURRENT_DIM_CONTRACT_VIEW)
        seed_system_categories(self._store)
        ensure_subscription_storage(self._store)
        ensure_contract_price_storage(self._store)

        self._store.ensure_dimension(DIM_METER)
        self._store.ensure_current_dimension_view(DIM_METER, CURRENT_DIM_METER_VIEW)
        ensure_utility_storage(self._store)

        self._store.ensure_dimension(DIM_ASSET)
        self._store.ensure_current_dimension_view(DIM_ASSET, CURRENT_DIM_ASSET_VIEW)
        ensure_asset_storage(self._store)

        self._store.ensure_dimension(DIM_ENTITY)
        self._store.ensure_current_dimension_view(DIM_ENTITY, CURRENT_DIM_ENTITY_VIEW)
        ensure_home_automation_storage(self._store)

        self._store.ensure_dimension(DIM_BUDGET)
        self._store.ensure_current_dimension_view(DIM_BUDGET, CURRENT_DIM_BUDGET_VIEW)
        ensure_budget_storage(self._store)

        self._store.ensure_dimension(DIM_LOAN)
        self._store.ensure_current_dimension_view(DIM_LOAN, CURRENT_DIM_LOAN_VIEW)
        ensure_loan_storage(self._store)
        ensure_balance_storage(self._store)

        ensure_overview_storage(self._store)
        ensure_category_storage(self._store)

        self._store.ensure_dimension(DIM_SERVICE)
        self._store.ensure_current_dimension_view(DIM_SERVICE, CURRENT_DIM_SERVICE_VIEW)
        self._store.ensure_dimension(DIM_WORKLOAD)
        self._store.ensure_current_dimension_view(DIM_WORKLOAD, CURRENT_DIM_WORKLOAD_VIEW)
        ensure_homelab_storage(self._store)
        ensure_infrastructure_storage(self._store)
        ensure_ha_storage(self._store)

        ensure_household_member_storage(self._store)
        seed_default_household_member(self._store)
        populate_counterparty_category_ids(self._store)

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        amount = row.get("amount", 0)
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif isinstance(amount, float):
            amount = Decimal(str(amount))

        currency = str(row.get("currency", "")).strip()
        normalized_currency = normalize_currency_code(currency)
        direction = "income" if amount >= 0 else "expense"

        return {
            **row,
            "amount": amount,
            "booked_at_utc": normalize_timestamp_utc(row["booked_at"]),
            "currency": currency,
            "normalized_currency": normalized_currency,
            "direction": direction,
        }

    def _record_lineage(
        self,
        *,
        run_id: str | None,
        source_system: str | None,
        records: list[tuple[str, str, int | None]],
    ) -> None:
        if run_id is None or self._control_plane_store is None:
            return
        self._control_plane_store.record_source_lineage(
            tuple(
                SourceLineageCreate(
                    lineage_id=uuid.uuid4().hex[:16],
                    input_run_id=run_id,
                    source_run_id=run_id,
                    source_system=source_system,
                    target_layer="transformation",
                    target_name=target_name,
                    target_kind=target_kind,
                    row_count=row_count,
                )
                for target_name, target_kind, row_count in records
            )
        )

    def load_transactions(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
        batch_sha256: str | None = None,
        source_asset_id: str | None = None,
    ) -> int:
        # Resolve categories for counterparties in this batch
        counterparty_names = list({row["counterparty_name"] for row in rows})
        category_resolver = resolve_categories_bulk(self._store, counterparty_names)

        inserted, batch_id = load_transactions(
            self._store,
            rows=rows,
            normalize_row=self._normalize_row,
            record_lineage=self._record_lineage,
            dim_account=DIM_ACCOUNT,
            dim_counterparty=DIM_COUNTERPARTY,
            category_resolver=category_resolver,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
            batch_sha256=batch_sha256,
            source_asset_id=source_asset_id,
        )
        reconcile_batch(self._store, batch_id, run_id=run_id)
        return inserted

    def load_domain_rows(
        self,
        domain_key: str,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return self._domain_registry.load(
            self,
            domain_key,
            rows,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def refresh_monthly_cashflow(self) -> int:
        return refresh_monthly_cashflow(self._store)

    def refresh_publications(
        self,
        publication_keys: list[str] | tuple[str, ...],
    ) -> list[str]:
        """Refresh publications and compute confidence snapshots.

        Refreshes the specified publications and records their confidence
        snapshots in the control plane for upstream consumption by dashboards,
        APIs, and other confidence-aware features.
        """
        refreshed = self._publication_refresh_registry.refresh(self, publication_keys)

        # Record confidence snapshots for each refreshed publication
        if self._control_plane_store is not None:
            as_of = datetime.now(timezone.utc)
            for publication_key in refreshed:
                try:
                    compute_and_record_publication_confidence(
                        publication_key,
                        self._control_plane_store,
                        self._store,
                        as_of=as_of,
                    )
                except Exception:
                    # Silently skip on error; confidence snapshot is optional
                    # and should not block publication refresh
                    pass

        return refreshed

    def get_monthly_cashflow(
        self,
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_monthly_cashflow(
            self._store,
            from_month=from_month,
            to_month=to_month,
        )

    def get_transactions(self) -> list[dict[str, Any]]:
        return get_transactions(self._store)

    def count_transactions(self, run_id: str | None = None) -> int:
        return count_transactions(self._store, run_id=run_id)

    def count_domain_rows(self, domain_key: str, *, run_id: str | None = None) -> int:
        return self._domain_registry.count(self, domain_key, run_id=run_id)

    def count_subscriptions(self, run_id: str | None = None) -> int:
        return count_subscriptions(self._store, run_id=run_id)

    def count_contract_prices(self, run_id: str | None = None) -> int:
        return count_contract_prices(self._store, run_id=run_id)

    def count_utility_usage(self, run_id: str | None = None) -> int:
        return count_utility_usage(self._store, run_id=run_id)

    def count_bills(self, run_id: str | None = None) -> int:
        return count_bills(self._store, run_id=run_id)

    def refresh_monthly_cashflow_by_counterparty(self) -> int:
        return refresh_monthly_cashflow_by_counterparty(self._store)

    def get_monthly_cashflow_by_counterparty(
        self,
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty_name: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_monthly_cashflow_by_counterparty(
            self._store,
            from_month=from_month,
            to_month=to_month,
            counterparty_name=counterparty_name,
        )

    def refresh_spend_by_category_monthly(self) -> int:
        return refresh_spend_by_category_monthly(self._store)

    def get_spend_by_category_monthly(
        self,
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty_name: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_spend_by_category_monthly(
            self._store,
            from_month=from_month,
            to_month=to_month,
            counterparty_name=counterparty_name,
            category=category,
        )

    def refresh_recent_large_transactions(self) -> int:
        return refresh_recent_large_transactions(self._store)

    def get_recent_large_transactions(self) -> list[dict[str, Any]]:
        return get_recent_large_transactions(self._store)

    def refresh_account_balance_trend(self) -> int:
        return refresh_account_balance_trend(self._store)

    def get_account_balance_trend(
        self,
        account_id: str | None = None,
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_account_balance_trend(
            self._store,
            account_id=account_id,
            from_month=from_month,
            to_month=to_month,
        )

    def refresh_transaction_anomalies_current(self) -> int:
        return refresh_transaction_anomalies_current(self._store)

    def get_transaction_anomalies_current(self) -> list[dict[str, Any]]:
        return get_transaction_anomalies_current(self._store)

    def get_transformation_audit(
        self,
        input_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if input_run_id is not None:
            return self._store.fetchall_dicts(
                f"SELECT * FROM {TRANSFORMATION_AUDIT_TABLE}"
                " WHERE input_run_id = ?"
                " ORDER BY started_at DESC",
                [input_run_id],
            )
        return self._store.fetchall_dicts(
            f"SELECT * FROM {TRANSFORMATION_AUDIT_TABLE} ORDER BY started_at DESC"
        )

    def get_current_accounts(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_ACCOUNT_VIEW} ORDER BY account_id"
        )

    def get_current_counterparties(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_COUNTERPARTY_VIEW} ORDER BY counterparty_name"
        )

    def get_current_contracts(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_CONTRACT_VIEW} ORDER BY contract_name"
        )

    def get_current_categories(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_CATEGORY_VIEW} ORDER BY category_id"
        )

    # ------------------------------------------------------------------
    # Category rules and overrides
    # ------------------------------------------------------------------

    def add_category_rule(
        self,
        *,
        rule_id: str,
        pattern: str,
        category: str,
        priority: int = 0,
    ) -> None:
        add_category_rule(
            self._store, rule_id=rule_id, pattern=pattern,
            category=category, priority=priority,
        )
        backfill_counterparty_categories(self._store)

    def remove_category_rule(self, *, rule_id: str) -> None:
        remove_category_rule(self._store, rule_id=rule_id)
        backfill_counterparty_categories(self._store)

    def list_category_rules(self) -> list[dict[str, Any]]:
        return list_category_rules(self._store)

    def set_category_override(
        self, *, counterparty_name: str, category: str,
    ) -> None:
        set_category_override(
            self._store, counterparty_name=counterparty_name, category=category,
        )
        backfill_counterparty_categories(self._store)

    def remove_category_override(self, *, counterparty_name: str) -> None:
        remove_category_override(self._store, counterparty_name=counterparty_name)
        backfill_counterparty_categories(self._store)

    def list_category_overrides(self) -> list[dict[str, Any]]:
        return list_category_overrides(self._store)

    def get_current_meters(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_METER_VIEW} ORDER BY meter_id"
        )

    def get_current_budgets(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_BUDGET_VIEW} ORDER BY budget_id"
        )

    def get_current_loans(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_LOAN_VIEW} ORDER BY loan_id"
        )

    def get_current_dimension_rows(self, dimension_name: str) -> list[dict[str, Any]]:
        if dimension_name == "dim_account":
            return self.get_current_accounts()
        if dimension_name == "dim_counterparty":
            return self.get_current_counterparties()
        if dimension_name == "dim_contract":
            return self.get_current_contracts()
        if dimension_name == "dim_category":
            return self.get_current_categories()
        if dimension_name == "dim_meter":
            return self.get_current_meters()
        if dimension_name == "dim_budget":
            return self.get_current_budgets()
        if dimension_name == "dim_loan":
            return self.get_current_loans()
        if dimension_name == "dim_asset":
            return self.get_current_assets()
        if dimension_name == "dim_entity":
            return self.get_current_entities()
        if dimension_name == "dim_node":
            return self.get_current_nodes()
        if dimension_name == "dim_device":
            return self.get_current_devices()
        if dimension_name == "dim_service":
            return self.get_current_services()
        if dimension_name == "dim_workload":
            return self.get_current_workloads()
        raise KeyError(f"Unknown current dimension: {dimension_name}")

    @property
    def store(self) -> DuckDBStore:
        return self._store

    def load_subscriptions(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_subscriptions(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            dim_contract=DIM_CONTRACT,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def refresh_subscription_summary(self) -> int:
        return refresh_subscription_summary(self._store)

    def refresh_upcoming_fixed_costs_30d(self) -> int:
        return refresh_upcoming_fixed_costs_30d(self._store)

    def get_upcoming_fixed_costs_30d(self) -> list[dict[str, Any]]:
        return get_upcoming_fixed_costs_30d(self._store)

    def get_subscription_summary(
        self,
        status: str | None = None,
        currency: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_subscription_summary(
            self._store,
            status=status,
            currency=currency,
        )

    # ------------------------------------------------------------------
    # Budget targets
    # ------------------------------------------------------------------

    def load_budget_targets(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_budget_targets(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            dim_budget=DIM_BUDGET,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def count_budget_targets(self, run_id: str | None = None) -> int:
        return count_budget_targets(self._store, run_id=run_id)

    def refresh_budget_variance(self) -> int:
        return refresh_budget_variance(self._store)

    def get_budget_variance(
        self,
        *,
        budget_name: str | None = None,
        category_id: str | None = None,
        period_label: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_budget_variance(
            self._store,
            budget_name=budget_name,
            category_id=category_id,
            period_label=period_label,
        )

    def refresh_budget_progress_current(self) -> int:
        return refresh_budget_progress_current(self._store)

    def refresh_budget_envelope_drift(self) -> int:
        return refresh_budget_envelope_drift(self._store)

    def get_budget_progress_current(self) -> list[dict[str, Any]]:
        return get_budget_progress_current(self._store)

    def get_budget_envelope_drift(
        self,
        *,
        budget_name: str | None = None,
        category_id: str | None = None,
        period_label: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_budget_envelope_drift(
            self._store,
            budget_name=budget_name,
            category_id=category_id,
            period_label=period_label,
        )

    # ------------------------------------------------------------------
    # Loan repayments
    # ------------------------------------------------------------------

    def load_loan_repayments(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_loan_repayments(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            dim_loan=DIM_LOAN,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def count_loan_repayments(self, run_id: str | None = None) -> int:
        return count_loan_repayments(self._store, run_id=run_id)

    def refresh_loan_schedule_projected(self) -> int:
        return refresh_loan_schedule_projected(self._store)

    def refresh_loan_repayment_variance(self) -> int:
        return refresh_loan_repayment_variance(self._store)

    def refresh_loan_overview(self) -> int:
        return refresh_loan_overview(self._store)

    def refresh_balance_snapshot(self) -> int:
        return refresh_balance_snapshot(self._store)

    def get_loan_schedule_projected(
        self, loan_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_loan_schedule_projected(self._store, loan_id=loan_id)

    def get_loan_repayment_variance(
        self, loan_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_loan_repayment_variance(self._store, loan_id=loan_id)

    def get_loan_overview(self) -> list[dict[str, Any]]:
        return get_loan_overview(self._store)

    def get_balance_snapshot(self, balance_kind: str | None = None) -> list[dict[str, Any]]:
        return get_balance_snapshot(self._store, balance_kind=balance_kind)

    def load_contract_prices(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_contract_prices(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            dim_contract=DIM_CONTRACT,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def refresh_contract_price_current(self) -> int:
        return refresh_contract_price_current(self._store)

    def get_contract_price_current(
        self,
        *,
        contract_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_contract_price_current(
            self._store,
            contract_type=contract_type,
            status=status,
        )

    def get_electricity_price_current(self) -> list[dict[str, Any]]:
        return get_electricity_price_current(self._store)

    def load_utility_usage(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_utility_usage(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            dim_meter=DIM_METER,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def load_bills(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_bills(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            dim_meter=DIM_METER,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def refresh_utility_cost_summary(self) -> int:
        return refresh_utility_cost_summary(self._store)

    def refresh_utility_cost_trend_monthly(self) -> int:
        return refresh_utility_cost_trend_monthly(self._store)

    def get_utility_cost_trend_monthly(
        self,
        utility_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_utility_cost_trend_monthly(self._store, utility_type=utility_type)

    def refresh_usage_vs_price_summary(self) -> int:
        return refresh_usage_vs_price_summary(self._store)

    def get_usage_vs_price_summary(
        self,
        utility_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_usage_vs_price_summary(self._store, utility_type=utility_type)

    def refresh_contract_review_candidates(self) -> int:
        return refresh_contract_review_candidates(self._store)

    def get_contract_review_candidates(self) -> list[dict[str, Any]]:
        return get_contract_review_candidates(self._store)

    def refresh_contract_renewal_watchlist(self) -> int:
        return refresh_contract_renewal_watchlist(self._store)

    def get_contract_renewal_watchlist(self) -> list[dict[str, Any]]:
        return get_contract_renewal_watchlist(self._store)

    def get_utility_cost_summary(
        self,
        *,
        utility_type: str | None = None,
        meter_id: str | None = None,
        from_period: date | str | None = None,
        to_period: date | str | None = None,
        granularity: str = "month",
    ) -> list[dict[str, Any]]:
        return get_utility_cost_summary(
            self._store,
            utility_type=utility_type,
            meter_id=meter_id,
            from_period=from_period,
            to_period=to_period,
            granularity=granularity,
        )

    def refresh_household_overview(self) -> int:
        return refresh_household_overview(self._store)

    def get_household_overview(self) -> list[dict[str, Any]]:
        return get_household_overview(self._store)

    def refresh_homelab_roi(self) -> int:
        return refresh_homelab_roi(self._store)

    def get_homelab_roi(self) -> list[dict[str, Any]]:
        return get_homelab_roi(self._store)

    def refresh_open_attention_items(self) -> int:
        return refresh_open_attention_items(self._store)

    def get_open_attention_items(self) -> list[dict[str, Any]]:
        return get_open_attention_items(self._store)

    def refresh_recent_significant_changes(self) -> int:
        return refresh_recent_significant_changes(self._store)

    def get_recent_significant_changes(self) -> list[dict[str, Any]]:
        return get_recent_significant_changes(self._store)

    def refresh_current_operating_baseline(self) -> int:
        return refresh_current_operating_baseline(self._store)

    def get_current_operating_baseline(self) -> list[dict[str, Any]]:
        return get_current_operating_baseline(self._store)

    def refresh_household_cost_model(self) -> int:
        return refresh_household_cost_model(self._store)

    def get_household_cost_model(
        self,
        *,
        period_label: str | None = None,
        cost_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_household_cost_model(
            self._store, period_label=period_label, cost_type=cost_type
        )

    def refresh_cost_trend_12m(self) -> int:
        return refresh_cost_trend_12m(self._store)

    def get_cost_trend_12m(self) -> list[dict[str, Any]]:
        return get_cost_trend_12m(self._store)

    def refresh_affordability_ratios(self) -> int:
        return refresh_affordability_ratios(self._store)

    def get_affordability_ratios(self) -> list[dict[str, Any]]:
        return get_affordability_ratios(self._store)

    def refresh_recurring_cost_baseline(self) -> int:
        return refresh_recurring_cost_baseline(self._store)

    def get_recurring_cost_baseline(self) -> list[dict[str, Any]]:
        return get_recurring_cost_baseline(self._store)

    # ------------------------------------------------------------------
    # Homelab
    # ------------------------------------------------------------------

    def load_service_health(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_service_health_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_backup_runs(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_backup_run_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_storage_sensors(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_storage_sensor_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_workload_sensors(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_workload_sensor_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def refresh_service_health_current(self) -> int:
        return refresh_service_health_current(self._store)

    def refresh_backup_freshness(self) -> int:
        return refresh_backup_freshness(self._store)

    def refresh_storage_risk(self) -> int:
        return refresh_storage_risk(self._store)

    def refresh_workload_cost_7d(self) -> int:
        return refresh_workload_cost_7d(self._store)

    def get_service_health_current(self) -> list[dict[str, Any]]:
        return get_service_health_current(self._store)

    def get_backup_freshness(self) -> list[dict[str, Any]]:
        return get_backup_freshness(self._store)

    def get_storage_risk(self) -> list[dict[str, Any]]:
        return get_storage_risk(self._store)

    def get_workload_cost_7d(self) -> list[dict[str, Any]]:
        return get_workload_cost_7d(self._store)

    def load_cluster_metrics(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_cluster_metric_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_power_consumption(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_power_consumption_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_asset_register(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_asset_register_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def load_asset_events(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_asset_event_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_home_automation_state(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_home_automation_state_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def load_sensor_readings(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_sensor_readings(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def load_automation_events(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_automation_events(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def get_current_nodes(self) -> list[dict[str, Any]]:
        return get_current_nodes(self._store)

    def get_current_devices(self) -> list[dict[str, Any]]:
        return get_current_devices(self._store)

    def get_current_services(self) -> list[dict[str, Any]]:
        return get_current_services(self._store)

    def get_current_workloads(self) -> list[dict[str, Any]]:
        return get_current_workloads(self._store)

    def get_current_assets(self) -> list[dict[str, Any]]:
        return get_current_assets(self._store)

    def count_cluster_metric_rows(self, run_id: str | None = None) -> int:
        return count_cluster_metric_rows(self._store, run_id=run_id)

    def count_power_consumption_rows(self, run_id: str | None = None) -> int:
        return count_power_consumption_rows(self._store, run_id=run_id)

    def count_asset_event_rows(self, run_id: str | None = None) -> int:
        return count_asset_event_rows(self._store, run_id=run_id)

    def get_current_entities(self) -> list[dict[str, Any]]:
        return get_current_entities(self._store)

    def count_sensor_reading_rows(self, run_id: str | None = None) -> int:
        return count_sensor_reading_rows(self._store, run_id=run_id)

    def count_automation_event_rows(self, run_id: str | None = None) -> int:
        return count_automation_event_rows(self._store, run_id=run_id)

    def count_home_automation_state_rows(self, run_id: str | None = None) -> int:
        return count_home_automation_state_rows(self._store, run_id=run_id)

    def count_service_health_rows(self, run_id: str | None = None) -> int:
        return count_service_health_rows(self._store, run_id=run_id)

    def count_backup_run_rows(self, run_id: str | None = None) -> int:
        return count_backup_run_rows(self._store, run_id=run_id)

    def count_storage_sensor_rows(self, run_id: str | None = None) -> int:
        return count_storage_sensor_rows(self._store, run_id=run_id)

    def count_workload_sensor_rows(self, run_id: str | None = None) -> int:
        return count_workload_sensor_rows(self._store, run_id=run_id)

    # ------------------------------------------------------------------
    # Scenario service
    # ------------------------------------------------------------------

    def create_loan_what_if_scenario(
        self,
        loan_id: str,
        *,
        label: str | None = None,
        extra_repayment: Decimal | None = None,
        annual_rate: Decimal | None = None,
        term_months: int | None = None,
    ) -> ScenarioResult:
        return create_loan_what_if_scenario(
            self._store,
            loan_id=loan_id,
            label=label,
            extra_repayment=extra_repayment,
            annual_rate=annual_rate,
            term_months=term_months,
        )

    def list_scenarios(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        return list_scenarios(self._store, include_archived=include_archived)

    def list_scenario_compare_sets(
        self,
        *,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        return list_scenario_compare_sets(
            self._store,
            include_archived=include_archived,
        )

    def get_scenario(self, scenario_id: str) -> dict[str, Any] | None:
        return get_scenario(self._store, scenario_id)

    def get_scenario_comparison(self, scenario_id: str) -> ComparisonResult | None:
        return get_scenario_comparison(self._store, scenario_id)

    def get_scenario_assumptions(self, scenario_id: str) -> list[dict[str, Any]]:
        return get_scenario_assumptions(self._store, scenario_id)

    def archive_scenario(self, scenario_id: str) -> bool:
        return archive_scenario(self._store, scenario_id)

    def create_scenario_compare_set(
        self,
        *,
        left_scenario_id: str,
        right_scenario_id: str,
        label: str | None = None,
    ) -> ScenarioCompareSetResult:
        return create_scenario_compare_set(
            self._store,
            left_scenario_id=left_scenario_id,
            right_scenario_id=right_scenario_id,
            label=label,
        )

    def update_scenario_compare_set_label(
        self,
        compare_set_id: str,
        *,
        label: str,
    ) -> ScenarioCompareSetResult | None:
        return update_scenario_compare_set_label(
            self._store,
            compare_set_id,
            label=label,
        )

    def archive_scenario_compare_set(self, compare_set_id: str) -> bool:
        return archive_scenario_compare_set(self._store, compare_set_id)

    def restore_scenario_compare_set(self, compare_set_id: str) -> ScenarioCompareSetResult | None:
        return restore_scenario_compare_set(self._store, compare_set_id)

    def ensure_scenario_storage(self) -> None:
        ensure_scenario_storage(self._store)

    def create_income_change_scenario(
        self,
        *,
        monthly_income_delta: Decimal,
        currency: str = "GBP",
        label: str | None = None,
        projection_months: int = 12,
    ) -> IncomeScenarioResult:
        return create_income_change_scenario(
            self._store,
            monthly_income_delta=monthly_income_delta,
            currency=currency,
            label=label,
            projection_months=projection_months,
        )

    def get_income_scenario_comparison(
        self, scenario_id: str
    ) -> IncomeCashflowComparison | None:
        return get_income_scenario_comparison(self._store, scenario_id)

    def create_expense_shock_scenario(
        self,
        *,
        expense_pct_delta: Decimal,
        label: str | None = None,
        projection_months: int = 12,
    ) -> ExpenseShockResult:
        return create_expense_shock_scenario(
            self._store,
            expense_pct_delta=expense_pct_delta,
            label=label,
            projection_months=projection_months,
        )

    def get_expense_shock_comparison(
        self, scenario_id: str
    ) -> IncomeCashflowComparison | None:
        return get_expense_shock_comparison(self._store, scenario_id)

    def create_homelab_cost_benefit_scenario(
        self,
        *,
        monthly_cost_delta: Decimal,
        label: str | None = None,
        service_rows: list[dict[str, Any]] | None = None,
        workload_rows: list[dict[str, Any]] | None = None,
        baseline_run_id: str | None = None,
    ) -> HomelabCostBenefitResult:
        return create_homelab_cost_benefit_scenario(
            self._store,
            monthly_cost_delta=monthly_cost_delta,
            label=label,
            service_rows=service_rows,
            workload_rows=workload_rows,
            baseline_run_id=baseline_run_id,
        )

    def get_homelab_cost_benefit_comparison(
        self,
        scenario_id: str,
        *,
        current_baseline_run_id: str | None = None,
    ) -> HomelabCostBenefitComparison | None:
        return get_homelab_cost_benefit_comparison(
            self._store,
            scenario_id,
            current_baseline_run_id=current_baseline_run_id,
        )

    def create_tariff_shock_scenario(
        self,
        *,
        tariff_pct_delta: Decimal,
        utility_type: str = "electricity",
        label: str | None = None,
        projection_months: int = 12,
    ) -> TariffShockResult:
        return create_tariff_shock_scenario(
            self._store,
            tariff_pct_delta=tariff_pct_delta,
            utility_type=utility_type,
            label=label,
            projection_months=projection_months,
        )

    def get_tariff_shock_comparison(
        self, scenario_id: str
    ) -> IncomeCashflowComparison | None:
        return get_tariff_shock_comparison(self._store, scenario_id)

    # ------------------------------------------------------------------
    # HA integration service
    # ------------------------------------------------------------------

    def ingest_ha_states(
        self,
        states: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str = "home_assistant",
    ) -> int:
        return ingest_ha_states(
            self._store,
            states,
            run_id=run_id,
            source_system=source_system,
        )

    def get_ha_entities(self) -> list[dict[str, Any]]:
        return get_ha_entities(self._store)

    def get_ha_entity_history(
        self, entity_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        return get_ha_entity_history(self._store, entity_id, limit=limit)

    # ------------------------------------------------------------------
    # Household member dimension
    # ------------------------------------------------------------------

    def populate_counterparty_category_ids(self) -> int:
        return populate_counterparty_category_ids(self._store)

    def get_household_members(self) -> list[dict[str, Any]]:
        return get_household_members(self._store)

    def upsert_household_member(
        self,
        *,
        member_id: str,
        display_name: str,
        role: str,
        active: bool = True,
    ) -> None:
        upsert_household_member(
            self._store,
            member_id=member_id,
            display_name=display_name,
            role=role,
            active=active,
        )
