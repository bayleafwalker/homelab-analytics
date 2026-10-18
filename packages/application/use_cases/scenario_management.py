"""Application use-cases for scenario creation and retrieval.

Surfaces call these functions; they do not call TransformationService directly.
Scenario-type logic is owned by the domain packs and dispatched through
``packages.pipelines.scenario_registry``; these functions keep the typed,
per-type entrypoints that routes call.
Scenario writes take the TransformationService; scenario reads take the
ReportingService so app-facing reads stay on the reporting layer.
Decimal parsing and HTTP error mapping remain in the calling route.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from packages.pipelines.scenario_registry import (
    SCENARIO_VIEW_CASHFLOW,
    SCENARIO_VIEW_COMPARISON,
)

if TYPE_CHECKING:
    from packages.domains.finance.pipelines.scenario_service import (
        ComparisonResult,
        ExpenseShockResult,
        IncomeCashflowComparison,
        IncomeScenarioResult,
        ScenarioCompareSetResult,
        ScenarioResult,
    )
    from packages.domains.overview.pipelines.scenario_models_overview import (
        HomelabCostBenefitComparison,
        HomelabCostBenefitResult,
        TariffShockResult,
    )
    from packages.pipelines.reporting_service import (
        HomelabCostBenefitBaseline,
        ReportingService,
    )
    from packages.pipelines.transformation_service import TransformationService


# ---------------------------------------------------------------------------
# Scenario creation
# ---------------------------------------------------------------------------


def create_loan_what_if(
    svc: "TransformationService",
    loan_id: str,
    *,
    label: str | None = None,
    extra_repayment: Decimal | None = None,
    annual_rate: Decimal | None = None,
    term_months: int | None = None,
) -> "ScenarioResult":
    return svc.create_scenario(
        "loan_what_if",
        loan_id=loan_id,
        label=label,
        extra_repayment=extra_repayment,
        annual_rate=annual_rate,
        term_months=term_months,
    )


def create_income_change(
    svc: "TransformationService",
    *,
    monthly_income_delta: Decimal,
    currency: str = "GBP",
    label: str | None = None,
    projection_months: int = 12,
) -> "IncomeScenarioResult":
    return svc.create_scenario(
        "income_change",
        monthly_income_delta=monthly_income_delta,
        currency=currency,
        label=label,
        projection_months=projection_months,
    )


def create_expense_shock(
    svc: "TransformationService",
    *,
    expense_pct_delta: Decimal,
    label: str | None = None,
    projection_months: int = 12,
) -> "ExpenseShockResult":
    return svc.create_scenario(
        "expense_shock",
        expense_pct_delta=expense_pct_delta,
        label=label,
        projection_months=projection_months,
    )


def create_tariff_shock(
    svc: "TransformationService",
    *,
    tariff_pct_delta: Decimal,
    utility_type: str = "electricity",
    label: str | None = None,
    projection_months: int = 12,
) -> "TariffShockResult":
    return svc.create_scenario(
        "tariff_shock",
        tariff_pct_delta=tariff_pct_delta,
        utility_type=utility_type,
        label=label,
        projection_months=projection_months,
    )


def create_homelab_cost_benefit(
    svc: "TransformationService",
    *,
    monthly_cost_delta: Decimal,
    label: str | None = None,
    homelab_baseline: "HomelabCostBenefitBaseline | None" = None,
) -> "HomelabCostBenefitResult":
    return svc.create_scenario(
        "homelab_cost_benefit",
        monthly_cost_delta=monthly_cost_delta,
        label=label,
        service_rows=None if homelab_baseline is None else homelab_baseline.service_rows,
        workload_rows=None if homelab_baseline is None else homelab_baseline.workload_rows,
        baseline_run_id=None if homelab_baseline is None else homelab_baseline.signature,
    )


# ---------------------------------------------------------------------------
# Scenario reads
# ---------------------------------------------------------------------------


def list_scenarios(
    reporting: "ReportingService",
    *,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    return reporting.list_scenarios(include_archived=include_archived)


def get_scenario(
    reporting: "ReportingService",
    scenario_id: str,
) -> dict[str, Any] | None:
    return reporting.get_scenario(scenario_id)


def get_scenario_assumptions(
    reporting: "ReportingService",
    scenario_id: str,
) -> list[dict[str, Any]]:
    return reporting.get_scenario_assumptions(scenario_id)


def archive_scenario(
    svc: "TransformationService",
    scenario_id: str,
) -> bool:
    return svc.archive_scenario(scenario_id)


# ---------------------------------------------------------------------------
# Scenario views — the scenario registry dispatches on the stored scenario type
# ---------------------------------------------------------------------------


def _baseline_run_id(homelab_baseline: "HomelabCostBenefitBaseline | None") -> str | None:
    return None if homelab_baseline is None else homelab_baseline.signature


def load_scenario_comparison(
    reporting: "ReportingService",
    scenario_id: str,
    *,
    homelab_baseline: "HomelabCostBenefitBaseline | None" = None,
) -> "HomelabCostBenefitComparison | ComparisonResult | None":
    # Registered comparison views return a loan or homelab comparison model.
    return cast(
        "HomelabCostBenefitComparison | ComparisonResult | None",
        reporting.get_scenario_view(
            scenario_id,
            view=SCENARIO_VIEW_COMPARISON,
            current_baseline_run_id=_baseline_run_id(homelab_baseline),
        ),
    )


def load_scenario_cashflow(
    reporting: "ReportingService",
    scenario_id: str,
    *,
    homelab_baseline: "HomelabCostBenefitBaseline | None" = None,
) -> "HomelabCostBenefitComparison | IncomeCashflowComparison | None":
    # Registered cashflow views return an income-cashflow or homelab model.
    return cast(
        "HomelabCostBenefitComparison | IncomeCashflowComparison | None",
        reporting.get_scenario_view(
            scenario_id,
            view=SCENARIO_VIEW_CASHFLOW,
            current_baseline_run_id=_baseline_run_id(homelab_baseline),
        ),
    )


# ---------------------------------------------------------------------------
# Compare-set operations
# ---------------------------------------------------------------------------


def list_compare_sets(
    reporting: "ReportingService",
    *,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    return reporting.list_scenario_compare_sets(include_archived=include_archived)


def create_compare_set(
    svc: "TransformationService",
    *,
    left_scenario_id: str,
    right_scenario_id: str,
    label: str | None = None,
) -> "ScenarioCompareSetResult":
    return svc.create_scenario_compare_set(
        left_scenario_id=left_scenario_id,
        right_scenario_id=right_scenario_id,
        label=label,
    )


def update_compare_set_label(
    svc: "TransformationService",
    compare_set_id: str,
    *,
    label: str,
) -> "ScenarioCompareSetResult | None":
    return svc.update_scenario_compare_set_label(compare_set_id, label=label)


def archive_compare_set(
    svc: "TransformationService",
    compare_set_id: str,
) -> bool:
    return svc.archive_scenario_compare_set(compare_set_id)


def restore_compare_set(
    svc: "TransformationService",
    compare_set_id: str,
) -> "ScenarioCompareSetResult | None":
    return svc.restore_scenario_compare_set(compare_set_id)
