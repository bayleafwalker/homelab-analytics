"""Built-in scenario-type composition: registers each domain pack's handlers."""

from __future__ import annotations

from packages.domains.finance.pipelines.scenario_handlers import (
    register_finance_scenario_handlers,
)
from packages.domains.overview.pipelines.scenario_handlers import (
    register_overview_scenario_handlers,
)
from packages.pipelines.scenario_registry import ScenarioRegistry


def register_builtin_scenario_handlers(registry: ScenarioRegistry) -> None:
    register_finance_scenario_handlers(registry)
    register_overview_scenario_handlers(registry)
