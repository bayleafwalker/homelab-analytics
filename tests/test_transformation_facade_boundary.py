"""TransformationService stays a thin orchestration facade (sprint #512 item #1882).

Domain behaviour belongs to the domain packs and is reached through the
registries the facade dispatches to:

- ingestion: ``TransformationDomainRegistry`` (``load_domain_rows`` / ``count_domain_rows``)
- publication refresh: ``PublicationRefreshRegistry`` (``refresh_publications``)
- scenario types: ``ScenarioRegistry`` (``create_scenario`` / ``get_scenario_view``)
- current dimensions: ``CurrentDimensionRegistry`` (``get_current_dimension_rows``)
- reporting mart reads: ``MartReadRegistry`` (``ReportingService`` via ``read_warehouse_mart``)

The surface below is a ratchet. Adding a public method fails this test: put
the behaviour in the domain pack and register it, or add an application use
case. Removing one also fails until the baseline is shrunk to match, so the
list never overstates what the facade exposes.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from packages.pipelines.transformation_service import TransformationService

pytestmark = [pytest.mark.architecture]

ROOT = Path(__file__).resolve().parents[1]

# Public methods per defining module (transformation_service or a facet).
# Shrink-only: see the module docstring before editing.
FACADE_SURFACE_BASELINE: dict[str, frozenset[str]] = {
    "assets": frozenset(
        {
            "count_asset_event_rows",
            "load_asset_events",
            "load_asset_register",
        }
    ),
    "commitments": frozenset(
        {
            "count_budget_targets",
            "count_contract_prices",
            "count_loan_repayments",
            "count_subscriptions",
            "load_budget_targets",
            "load_contract_prices",
            "load_loan_repayments",
            "load_subscriptions",
        }
    ),
    "home_automation": frozenset(
        {
            "count_automation_event_rows",
            "count_home_automation_state_rows",
            "count_sensor_reading_rows",
            "get_ha_entities",
            "get_ha_entity_history",
            "ingest_ha_states",
            "load_automation_events",
            "load_home_automation_state",
            "load_sensor_readings",
        }
    ),
    "homelab": frozenset(
        {
            "count_backup_run_rows",
            "count_cluster_metric_rows",
            "count_power_consumption_rows",
            "count_service_health_rows",
            "count_storage_sensor_rows",
            "count_workload_sensor_rows",
            "get_backup_freshness",
            "get_service_health_current",
            "get_storage_risk",
            "get_workload_cost_7d",
            "load_backup_runs",
            "load_cluster_metrics",
            "load_power_consumption",
            "load_service_health",
            "load_storage_sensors",
            "load_workload_sensors",
        }
    ),
    "overview": frozenset(
        {
            "get_affordability_ratios",
            "get_cost_trend_12m",
            "get_current_operating_baseline",
            "get_homelab_roi",
            "get_household_cost_model",
            "get_household_overview",
            "get_open_attention_items",
            "get_recent_significant_changes",
            "get_recurring_cost_baseline",
        }
    ),
    "scenarios": frozenset(
        {
            "archive_scenario",
            "archive_scenario_compare_set",
            "create_scenario",
            "create_scenario_compare_set",
            "ensure_scenario_storage",
            "get_scenario",
            "get_scenario_assumptions",
            "get_scenario_view",
            "list_scenario_compare_sets",
            "list_scenarios",
            "restore_scenario_compare_set",
            "update_scenario_compare_set_label",
        }
    ),
    "transactions": frozenset(
        {
            "add_category_rule",
            "count_transactions",
            "list_category_overrides",
            "list_category_rules",
            "load_transactions",
            "populate_counterparty_category_ids",
            "remove_category_override",
            "remove_category_rule",
            "set_category_override",
        }
    ),
    "transformation_service": frozenset(
        {
            "count_domain_rows",
            "get_current_dimension_rows",
            "get_household_members",
            "load_domain_rows",
            "record_publication_confidence",
            "refresh_publications",
            "upsert_household_member",
        }
    ),
    "utilities": frozenset(
        {
            "count_bills",
            "count_utility_usage",
            "get_battery_plan_outcome",
            "get_battery_plan_outcome_values",
            "get_contract_renewal_watchlist",
            "get_contract_review_candidates",
            "get_usage_vs_price_summary",
            "get_utility_cost_summary",
            "get_utility_cost_trend_monthly",
            "load_bills",
            "load_utility_usage",
        }
    ),
}

# Registry-dispatch replacements for method families that used to accrete.
_BANNED_FAMILIES = {
    r"refresh_(?!publications$)\w+": "register a publication refresh handler in the domain pack",
    r"get_current_(?!dimension_rows$)(accounts|counterparties|contracts|categories|meters"
    r"|budgets|loans|assets|entities|nodes|devices|services|workloads)": (
        "register a current-dimension reader in the domain pack"
    ),
    r"create_\w+_scenario|get_\w+_comparison": "register a ScenarioTypeHandler in the domain pack",
}

# Ingestion/lineage entrypoints and orchestration hooks are documented
# extension-facing contracts even without an in-repo caller.
_UNCALLED_ALLOWED_PREFIXES = ("load_", "count_", "ingest_", "ensure_", "populate_", "upsert_")


def _public_surface() -> dict[str, frozenset[str]]:
    by_module: dict[str, set[str]] = {}
    for name, _ in inspect.getmembers(TransformationService, callable):
        if name.startswith("_"):
            continue
        owner = next(cls for cls in TransformationService.__mro__ if name in cls.__dict__)
        by_module.setdefault(owner.__module__.rsplit(".", 1)[-1], set()).add(name)
    return {module: frozenset(names) for module, names in by_module.items()}


def test_facade_surface_does_not_grow() -> None:
    surface = _public_surface()
    added = {
        module: sorted(names - FACADE_SURFACE_BASELINE.get(module, frozenset()))
        for module, names in surface.items()
        if names - FACADE_SURFACE_BASELINE.get(module, frozenset())
    }
    assert added == {}, (
        "New public methods on TransformationService. Put the behaviour in the domain pack "
        "and register it with the matching registry (or add an application use case) "
        f"instead of growing the facade: {added}"
    )


def test_facade_surface_baseline_is_not_stale() -> None:
    surface = _public_surface()
    removed = {
        module: sorted(names - surface.get(module, frozenset()))
        for module, names in FACADE_SURFACE_BASELINE.items()
        if names - surface.get(module, frozenset())
    }
    assert removed == {}, f"Shrink FACADE_SURFACE_BASELINE to match the facade: {removed}"


def test_facade_has_no_method_from_a_registry_dispatched_family() -> None:
    names = [name for names in _public_surface().values() for name in names]
    offenders = {
        name: remedy
        for pattern, remedy in _BANNED_FAMILIES.items()
        for name in names
        if re.fullmatch(pattern, name)
    }
    assert offenders == {}


def test_every_facade_reader_has_a_caller_outside_tests() -> None:
    """A facet getter only earns a facade slot while apps/ or packages/ consume it.

    Methods defined on TransformationService itself are orchestration hooks
    (dispatch, confidence, household membership) and are exempt.
    """
    sources = [
        path.read_text()
        for root in ("apps", "packages")
        for path in (ROOT / root).rglob("*.py")
        if "transformation_facets" not in path.parts and path.name != "transformation_service.py"
    ]
    uncalled = sorted(
        name
        for module, names in _public_surface().items()
        if module != "transformation_service"
        for name in names
        if not name.startswith(_UNCALLED_ALLOWED_PREFIXES)
        and not any(re.search(rf"\.{name}\b", source) for source in sources)
    )
    assert uncalled == [], (
        "Facade methods with no caller outside tests; call the domain function directly "
        f"from the test and remove the pass-through: {uncalled}"
    )


def test_facade_does_not_reach_facet_methods_through_self() -> None:
    """transformation_service.py dispatches through registries, not facet methods."""
    source = (ROOT / "packages" / "pipelines" / "transformation_service.py").read_text()
    facet_names = {
        name
        for module, names in _public_surface().items()
        if module != "transformation_service"
        for name in names
    }
    reached = sorted(name for name in facet_names if f"self.{name}(" in source)
    assert reached == []
