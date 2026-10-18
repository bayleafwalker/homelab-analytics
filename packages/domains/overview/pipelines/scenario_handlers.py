"""Overview-pack scenario types: tariff shock and homelab cost/benefit."""

from __future__ import annotations

from typing import Any

from packages.domains.overview.pipelines.scenario_service_overview import (
    create_homelab_cost_benefit_scenario,
    create_tariff_shock_scenario,
    get_homelab_cost_benefit_comparison,
)
from packages.pipelines.scenario_registry import (
    SCENARIO_VIEW_CASHFLOW,
    SCENARIO_VIEW_COMPARISON,
    ScenarioRegistry,
    ScenarioTypeHandler,
    ScenarioViewContext,
)
from packages.storage.duckdb_store import DuckDBStore


def homelab_cost_benefit_view(
    store: DuckDBStore, scenario_id: str, context: ScenarioViewContext
) -> Any:
    return get_homelab_cost_benefit_comparison(
        store,
        scenario_id,
        current_baseline_run_id=context.current_baseline_run_id,
    )


OVERVIEW_SCENARIO_HANDLERS: tuple[ScenarioTypeHandler, ...] = (
    # Tariff shock keeps the generic finance views (registered as fallbacks):
    # the comparison and cashflow routes rendered it that way before dispatch
    # moved behind the registry.
    ScenarioTypeHandler(
        scenario_type="tariff_shock",
        create=create_tariff_shock_scenario,
    ),
    ScenarioTypeHandler(
        scenario_type="homelab_cost_benefit",
        create=create_homelab_cost_benefit_scenario,
        views={
            SCENARIO_VIEW_COMPARISON: homelab_cost_benefit_view,
            SCENARIO_VIEW_CASHFLOW: homelab_cost_benefit_view,
        },
    ),
)


def register_overview_scenario_handlers(registry: ScenarioRegistry) -> None:
    for handler in OVERVIEW_SCENARIO_HANDLERS:
        registry.register(handler)
