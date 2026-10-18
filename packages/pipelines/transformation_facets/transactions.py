"""Account transactions, cashflow marts, and category rules/overrides."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from packages.domains.finance.pipelines.category_rules import (
    add_category_rule,
    backfill_counterparty_categories,
    list_category_overrides,
    list_category_rules,
    remove_category_override,
    remove_category_rule,
    resolve_categories_bulk,
    set_category_override,
)
from packages.domains.finance.pipelines.reconciliation import reconcile_batch
from packages.domains.finance.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
)
from packages.domains.finance.pipelines.transaction_models import (
    CURRENT_DIM_ACCOUNT_VIEW,
    CURRENT_DIM_COUNTERPARTY_VIEW,
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    count_transactions,
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
from packages.pipelines.normalization import (
    normalize_currency_code,
    normalize_timestamp_utc,
)
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class TransactionTransformationMixin(TransformationFacetBase):
    """Account transactions, cashflow marts, and category rules/overrides."""

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

    def refresh_monthly_cashflow(self) -> int:
        return refresh_monthly_cashflow(self._store)

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

    def get_current_accounts(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_ACCOUNT_VIEW} ORDER BY account_id"
        )

    def get_current_counterparties(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_COUNTERPARTY_VIEW} ORDER BY counterparty_name"
        )

    def get_current_categories(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_CATEGORY_VIEW} ORDER BY category_id"
        )

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

    def populate_counterparty_category_ids(self) -> int:
        return populate_counterparty_category_ids(self._store)
