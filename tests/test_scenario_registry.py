"""Scenario-type dispatch through the registry (sprint #512 item #1880)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from packages.domains.finance.pipelines.scenario_service import (
    get_income_scenario_comparison,
    get_scenario_comparison,
)
from packages.pipelines.scenario_registry import (
    SCENARIO_VIEW_CASHFLOW,
    SCENARIO_VIEW_COMPARISON,
    ScenarioRegistry,
    ScenarioTypeHandler,
    ScenarioViewContext,
    get_default_scenario_registry,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


def _view(tag: str):
    def handler(store: Any, scenario_id: str, context: ScenarioViewContext) -> Any:
        return (tag, scenario_id, context.current_baseline_run_id)

    return handler


def test_registry_dispatches_create_and_views_by_scenario_type() -> None:
    registry = ScenarioRegistry()
    registry.register(
        ScenarioTypeHandler(
            scenario_type="demo",
            create=lambda store, **params: ("created", store, params),
            views={SCENARIO_VIEW_COMPARISON: _view("demo-comparison")},
        )
    )
    registry.register_fallback_views({SCENARIO_VIEW_CASHFLOW: _view("fallback-cashflow")})

    assert registry.create("store", "demo", delta=1) == ("created", "store", {"delta": 1})
    assert registry.view(
        "store",  # type: ignore[arg-type]
        scenario_type="demo",
        scenario_id="s1",
        view=SCENARIO_VIEW_COMPARISON,
        context=ScenarioViewContext(current_baseline_run_id="sig"),
    ) == ("demo-comparison", "s1", "sig")
    # A type without its own view falls back; so does an unregistered stored type.
    assert registry.view(
        "store",  # type: ignore[arg-type]
        scenario_type="demo",
        scenario_id="s1",
        view=SCENARIO_VIEW_CASHFLOW,
    ) == ("fallback-cashflow", "s1", None)
    assert registry.view_handler("legacy", SCENARIO_VIEW_CASHFLOW) is registry.fallback_views()[
        SCENARIO_VIEW_CASHFLOW
    ]


def test_registry_rejects_unknown_types_views_and_conflicting_registrations() -> None:
    registry = ScenarioRegistry()
    handler = ScenarioTypeHandler(scenario_type="demo", create=lambda store, **_: None)
    registry.register(handler)
    registry.register(handler)  # idempotent for the same handler

    with pytest.raises(ValueError, match="already registered"):
        registry.register(ScenarioTypeHandler(scenario_type="demo", create=lambda store: 1))
    with pytest.raises(ValueError, match="Unknown scenario views"):
        registry.register(
            ScenarioTypeHandler(scenario_type="x", create=lambda store: 1, views={"chart": _view("c")})
        )
    with pytest.raises(ValueError, match="Unsupported scenario type"):
        registry.create("store", "missing")
    with pytest.raises(ValueError, match="Unsupported scenario view"):
        registry.view_handler("demo", "chart")
    with pytest.raises(ValueError, match="No comparison view"):
        registry.view_handler("demo", SCENARIO_VIEW_COMPARISON)


def test_default_registry_is_composed_from_domain_packs() -> None:
    registry = get_default_scenario_registry()

    assert registry.scenario_types() == (
        "expense_shock",
        "homelab_cost_benefit",
        "income_change",
        "loan_what_if",
        "tariff_shock",
    )
    for handler in registry.handlers():
        assert handler.create.__module__.startswith("packages.domains."), handler
        for view in handler.views.values():
            assert view.__module__.startswith("packages.domains."), handler
    for view in registry.fallback_views().values():
        assert view.__module__.startswith("packages.domains."), view


def test_default_registry_preserves_pre_registry_route_dispatch() -> None:
    """Views match the branches scenario_management used before #1880."""
    registry = get_default_scenario_registry()
    homelab_comparison = registry.view_handler("homelab_cost_benefit", SCENARIO_VIEW_COMPARISON)
    assert registry.view_handler("homelab_cost_benefit", SCENARIO_VIEW_CASHFLOW) is (
        homelab_comparison
    )
    for scenario_type in ("loan_what_if", "income_change", "expense_shock", "tariff_shock"):
        assert registry.view_handler(scenario_type, SCENARIO_VIEW_COMPARISON) is not (
            homelab_comparison
        )
        assert registry.view_handler(scenario_type, SCENARIO_VIEW_CASHFLOW) is not (
            homelab_comparison
        )


def test_facade_creates_and_renders_scenarios_through_the_registry(tmp_path: Path) -> None:
    store = DuckDBStore.open(str(tmp_path / "warehouse.duckdb"))
    service = TransformationService(store)
    service.load_transactions(
        [
            {
                "booked_at": f"2026-0{month}-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            }
            for month in (1, 2, 3)
        ],
        run_id="run-registry-001",
    )
    service.refresh_publications(["mart_monthly_cashflow"])

    result = service.create_scenario(
        "income_change",
        monthly_income_delta=Decimal("100"),
        label="raise",
        projection_months=3,
    )

    cashflow = service.get_scenario_view(result.scenario_id, view=SCENARIO_VIEW_CASHFLOW)
    assert cashflow == get_income_scenario_comparison(store, result.scenario_id)
    assert len(cashflow.cashflow_rows) == 3
    comparison = service.get_scenario_view(result.scenario_id, view=SCENARIO_VIEW_COMPARISON)
    assert comparison == get_scenario_comparison(store, result.scenario_id)
    assert service.get_scenario_view("missing", view=SCENARIO_VIEW_CASHFLOW) is None
    with pytest.raises(ValueError, match="Unsupported scenario type"):
        service.create_scenario("lottery_win")


def test_facade_accepts_an_injected_scenario_registry(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []
    registry = ScenarioRegistry()
    registry.register(
        ScenarioTypeHandler(
            scenario_type="demo",
            create=lambda store, **params: calls.append(params) or "made",
        )
    )
    service = TransformationService(
        DuckDBStore.open(str(tmp_path / "warehouse.duckdb")),
        scenario_registry=registry,
    )

    assert service.create_scenario("demo", delta=2) == "made"
    assert calls == [{"delta": 2}]
