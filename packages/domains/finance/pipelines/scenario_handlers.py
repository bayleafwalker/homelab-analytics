"""Finance-pack scenario types: loan what-if, income change, expense shock.

The finance pack also owns the generic scenario views used for any stored
scenario type without its own view (loan comparison, income-cashflow
projection), which preserves the pre-registry route behaviour.
"""

from __future__ import annotations

from typing import Any

from packages.domains.finance.pipelines.scenario_service import (
    create_expense_shock_scenario,
    create_income_change_scenario,
    create_loan_what_if_scenario,
    get_expense_shock_comparison,
    get_income_scenario_comparison,
    get_scenario_comparison,
)
from packages.pipelines.scenario_registry import (
    SCENARIO_VIEW_CASHFLOW,
    SCENARIO_VIEW_COMPARISON,
    ScenarioRegistry,
    ScenarioTypeHandler,
    ScenarioViewContext,
    ScenarioViewHandler,
)
from packages.storage.duckdb_store import DuckDBStore


def loan_comparison_view(
    store: DuckDBStore, scenario_id: str, context: ScenarioViewContext
) -> Any:
    return get_scenario_comparison(store, scenario_id)


def income_cashflow_view(
    store: DuckDBStore, scenario_id: str, context: ScenarioViewContext
) -> Any:
    return get_income_scenario_comparison(store, scenario_id)


def expense_shock_cashflow_view(
    store: DuckDBStore, scenario_id: str, context: ScenarioViewContext
) -> Any:
    return get_expense_shock_comparison(store, scenario_id)


GENERIC_SCENARIO_VIEWS: dict[str, ScenarioViewHandler] = {
    SCENARIO_VIEW_COMPARISON: loan_comparison_view,
    SCENARIO_VIEW_CASHFLOW: income_cashflow_view,
}

FINANCE_SCENARIO_HANDLERS: tuple[ScenarioTypeHandler, ...] = (
    ScenarioTypeHandler(
        scenario_type="loan_what_if",
        create=create_loan_what_if_scenario,
        views=GENERIC_SCENARIO_VIEWS,
    ),
    ScenarioTypeHandler(
        scenario_type="income_change",
        create=create_income_change_scenario,
        views=GENERIC_SCENARIO_VIEWS,
    ),
    ScenarioTypeHandler(
        scenario_type="expense_shock",
        create=create_expense_shock_scenario,
        views={
            SCENARIO_VIEW_COMPARISON: loan_comparison_view,
            SCENARIO_VIEW_CASHFLOW: expense_shock_cashflow_view,
        },
    ),
)


def register_finance_scenario_handlers(registry: ScenarioRegistry) -> None:
    for handler in FINANCE_SCENARIO_HANDLERS:
        registry.register(handler)
    registry.register_fallback_views(GENERIC_SCENARIO_VIEWS)
