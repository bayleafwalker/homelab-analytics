"""Scenario lifecycle plus registry-dispatched scenario creation and views.

Type-specific scenario logic lives in the domain packs and is registered with
``packages.pipelines.scenario_registry``; this facet only dispatches.
"""

from __future__ import annotations

from typing import Any

from packages.domains.finance.pipelines.scenario_service import (
    ScenarioCompareSetResult,
    archive_scenario,
    archive_scenario_compare_set,
    create_scenario_compare_set,
    ensure_scenario_storage,
    get_scenario,
    get_scenario_assumptions,
    list_scenario_compare_sets,
    list_scenarios,
    restore_scenario_compare_set,
    update_scenario_compare_set_label,
)
from packages.pipelines.scenario_registry import ScenarioViewContext
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class ScenarioTransformationMixin(TransformationFacetBase):
    """Scenario lifecycle plus registry-dispatched scenario creation and views."""

    def create_scenario(self, scenario_type: str, **params: Any) -> Any:
        """Create a scenario of a registered type; params are that type's keywords."""
        return self._scenario_registry.create(self._store, scenario_type, **params)

    def get_scenario_view(
        self,
        scenario_id: str,
        *,
        view: str,
        current_baseline_run_id: str | None = None,
    ) -> Any:
        """Render a stored scenario's view via the handler for its scenario type."""
        scenario = get_scenario(self._store, scenario_id)
        if scenario is None:
            return None
        return self._scenario_registry.view(
            self._store,
            scenario_type=scenario["scenario_type"],
            scenario_id=scenario_id,
            view=view,
            context=ScenarioViewContext(current_baseline_run_id=current_baseline_run_id),
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
