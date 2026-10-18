"""Scenario-type dispatch: domain packs own scenario logic, the registry dispatches.

Each domain pack registers a :class:`ScenarioTypeHandler` per scenario type it
owns: how to create the scenario and how to render each read view
(``comparison``, ``cashflow``) of a stored scenario. ``TransformationService``
exposes one generic create and one generic view method that dispatch here, so
adding a scenario type never adds a method to the facade.

The registry is domain-agnostic: it never imports a domain pack. The built-in
composition lives in ``packages.pipelines.household_scenario_handlers``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from packages.storage.duckdb_store import DuckDBStore

SCENARIO_VIEW_COMPARISON = "comparison"
SCENARIO_VIEW_CASHFLOW = "cashflow"
SCENARIO_VIEWS: tuple[str, ...] = (SCENARIO_VIEW_COMPARISON, SCENARIO_VIEW_CASHFLOW)


@dataclass(frozen=True)
class ScenarioViewContext:
    """Caller-supplied context a view handler may use; unused fields are ignored."""

    current_baseline_run_id: str | None = None


ScenarioCreateHandler = Callable[..., Any]
"""``create(store, **params)`` — params are the scenario type's own keywords."""

ScenarioViewHandler = Callable[[DuckDBStore, str, ScenarioViewContext], Any]
"""``view(store, scenario_id, context)`` — returns the view model or ``None``."""


@dataclass(frozen=True)
class ScenarioTypeHandler:
    scenario_type: str
    create: ScenarioCreateHandler
    views: Mapping[str, ScenarioViewHandler] = field(default_factory=dict)


class ScenarioRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ScenarioTypeHandler] = {}
        self._fallback_views: dict[str, ScenarioViewHandler] = {}

    def register(self, handler: ScenarioTypeHandler) -> None:
        unknown_views = sorted(set(handler.views) - set(SCENARIO_VIEWS))
        if unknown_views:
            raise ValueError(
                f"Unknown scenario views for {handler.scenario_type}: {unknown_views}"
            )
        existing = self._handlers.get(handler.scenario_type)
        if existing is not None and existing != handler:
            raise ValueError(f"Scenario type already registered: {handler.scenario_type}")
        self._handlers[handler.scenario_type] = handler

    def register_fallback_views(self, views: Mapping[str, ScenarioViewHandler]) -> None:
        """Views used for stored scenarios whose type has no handler for that view."""
        unknown_views = sorted(set(views) - set(SCENARIO_VIEWS))
        if unknown_views:
            raise ValueError(f"Unknown scenario fallback views: {unknown_views}")
        for view, handler in views.items():
            existing = self._fallback_views.get(view)
            if existing is not None and existing is not handler:
                raise ValueError(f"Scenario fallback view already registered: {view}")
            self._fallback_views[view] = handler

    def create(self, store: DuckDBStore, scenario_type: str, **params: Any) -> Any:
        try:
            handler = self._handlers[scenario_type]
        except KeyError as exc:
            raise ValueError(f"Unsupported scenario type: {scenario_type}") from exc
        return handler.create(store, **params)

    def view(
        self,
        store: DuckDBStore,
        *,
        scenario_type: str,
        scenario_id: str,
        view: str,
        context: ScenarioViewContext | None = None,
    ) -> Any:
        return self.view_handler(scenario_type, view)(
            store,
            scenario_id,
            context or ScenarioViewContext(),
        )

    def view_handler(self, scenario_type: str, view: str) -> ScenarioViewHandler:
        if view not in SCENARIO_VIEWS:
            raise ValueError(f"Unsupported scenario view: {view}")
        handler = self._handlers.get(scenario_type)
        if handler is not None and view in handler.views:
            return handler.views[view]
        try:
            return self._fallback_views[view]
        except KeyError as exc:
            raise ValueError(
                f"No {view} view registered for scenario type: {scenario_type}"
            ) from exc

    def scenario_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def handlers(self) -> tuple[ScenarioTypeHandler, ...]:
        return tuple(self._handlers[key] for key in sorted(self._handlers))

    def fallback_views(self) -> Mapping[str, ScenarioViewHandler]:
        return dict(self._fallback_views)


_DEFAULT_SCENARIO_REGISTRY: ScenarioRegistry | None = None


def get_default_scenario_registry() -> ScenarioRegistry:
    global _DEFAULT_SCENARIO_REGISTRY
    if _DEFAULT_SCENARIO_REGISTRY is None:
        from packages.pipelines.household_scenario_handlers import (
            register_builtin_scenario_handlers,
        )

        registry = ScenarioRegistry()
        register_builtin_scenario_handlers(registry)
        _DEFAULT_SCENARIO_REGISTRY = registry
    return _DEFAULT_SCENARIO_REGISTRY
