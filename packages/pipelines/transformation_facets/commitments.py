"""Subscriptions, contract prices, budgets, loans, and balances."""

from __future__ import annotations

from datetime import date
from typing import Any

from packages.domains.finance.pipelines.budget_models import (
    DIM_BUDGET,
)
from packages.domains.finance.pipelines.loan_models import (
    DIM_LOAN,
)
from packages.domains.finance.pipelines.subscription_models import (
    DIM_CONTRACT,
)
from packages.domains.finance.pipelines.transformation_budgets import (
    count_budget_targets,
    get_budget_envelope_drift,
    get_budget_progress_current,
    get_budget_variance,
    load_budget_targets,
)
from packages.domains.finance.pipelines.transformation_contract_prices import (
    count_contract_prices,
    get_contract_price_current,
    get_electricity_price_current,
    load_contract_prices,
)
from packages.domains.finance.pipelines.transformation_loans import (
    count_loan_repayments,
    get_loan_overview,
    get_loan_repayment_variance,
    get_loan_schedule_projected,
    load_loan_repayments,
)
from packages.domains.finance.pipelines.transformation_subscriptions import (
    count_subscriptions,
    get_subscription_summary,
    get_upcoming_fixed_costs_30d,
    load_subscriptions,
)
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class CommitmentTransformationMixin(TransformationFacetBase):
    """Subscriptions, contract prices, budgets, loans, and balances."""

    def count_subscriptions(self, run_id: str | None = None) -> int:
        return count_subscriptions(self._store, run_id=run_id)

    def count_contract_prices(self, run_id: str | None = None) -> int:
        return count_contract_prices(self._store, run_id=run_id)

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
