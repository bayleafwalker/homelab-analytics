"""Transformation service facade over domain-specific warehouse processors."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from packages.pipelines.normalization import (
    normalize_currency_code,
    normalize_timestamp_utc,
)
from packages.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
    CURRENT_DIM_CONTRACT_VIEW,
    DIM_CATEGORY,
    DIM_CONTRACT,
)
from packages.pipelines.transaction_models import (
    CURRENT_DIM_ACCOUNT_VIEW,
    CURRENT_DIM_COUNTERPARTY_VIEW,
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    TRANSFORMATION_AUDIT_TABLE,
)
from packages.pipelines.transformation_contract_prices import (
    count_contract_prices,
    ensure_contract_price_storage,
    get_contract_price_current,
    get_electricity_price_current,
    load_contract_prices,
    refresh_contract_price_current,
)
from packages.pipelines.transformation_domain_registry import (
    TransformationDomainRegistry,
    get_default_transformation_domain_registry,
)
from packages.pipelines.transformation_overview import (
    ensure_overview_storage,
    get_current_operating_baseline,
    get_household_overview,
    get_open_attention_items,
    get_recent_significant_changes,
    refresh_current_operating_baseline,
    refresh_household_overview,
    refresh_open_attention_items,
    refresh_recent_significant_changes,
)
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshRegistry,
    get_default_publication_refresh_registry,
)
from packages.pipelines.transformation_subscriptions import (
    count_subscriptions,
    ensure_subscription_storage,
    get_subscription_summary,
    get_upcoming_fixed_costs_30d,
    load_subscriptions,
    refresh_subscription_summary,
    refresh_upcoming_fixed_costs_30d,
)
from packages.pipelines.transformation_transactions import (
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
    refresh_account_balance_trend,
    refresh_monthly_cashflow,
    refresh_monthly_cashflow_by_counterparty,
    refresh_recent_large_transactions,
    refresh_spend_by_category_monthly,
    refresh_transaction_anomalies_current,
)
from packages.pipelines.transformation_utilities import (
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
from packages.pipelines.utility_models import (
    CURRENT_DIM_METER_VIEW,
    DIM_METER,
)
from packages.storage.control_plane import SourceLineageCreate, SourceLineageStore
from packages.storage.duckdb_store import DuckDBStore


class TransformationService:
    """Loads validated landing data into the transformation and reporting layers."""

    def __init__(
        self,
        store: DuckDBStore,
        *,
        control_plane_store: SourceLineageStore | None = None,
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
        ensure_subscription_storage(self._store)
        ensure_contract_price_storage(self._store)

        self._store.ensure_dimension(DIM_METER)
        self._store.ensure_current_dimension_view(DIM_METER, CURRENT_DIM_METER_VIEW)
        ensure_utility_storage(self._store)

        ensure_overview_storage(self._store)

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
    ) -> int:
        return load_transactions(
            self._store,
            rows=rows,
            normalize_row=self._normalize_row,
            record_lineage=self._record_lineage,
            dim_account=DIM_ACCOUNT,
            dim_counterparty=DIM_COUNTERPARTY,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

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
        return self._publication_refresh_registry.refresh(self, publication_keys)

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

    def get_current_meters(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_METER_VIEW} ORDER BY meter_id"
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
