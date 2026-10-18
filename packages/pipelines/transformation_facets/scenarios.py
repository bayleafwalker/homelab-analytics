"""What-if scenario creation and comparison."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

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
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class ScenarioTransformationMixin(TransformationFacetBase):
    """What-if scenario creation and comparison."""

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
