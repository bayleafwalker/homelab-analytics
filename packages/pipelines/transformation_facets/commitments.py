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
    load_budget_targets,
)
from packages.domains.finance.pipelines.transformation_contract_prices import (
    count_contract_prices,
    load_contract_prices,
)
from packages.domains.finance.pipelines.transformation_loans import (
    count_loan_repayments,
    load_loan_repayments,
)
from packages.domains.finance.pipelines.transformation_subscriptions import (
    count_subscriptions,
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
