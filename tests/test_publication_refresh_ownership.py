"""Publication refresh handlers are owned by domain packs (sprint #512 item #1881)."""

from __future__ import annotations

from datetime import datetime, timezone

from packages.domains.finance.pipelines.transformation_transactions import (
    get_monthly_cashflow,
)
from packages.pipelines.household_transformation_refresh import (
    BUILTIN_PUBLICATION_REFRESH_HANDLERS,
)
from packages.pipelines.transformation_refresh_registry import (
    StoreRefreshHandler,
    get_default_publication_refresh_registry,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


def _owner_module(handler: object) -> str:
    if isinstance(handler, StoreRefreshHandler):
        return handler.refresh.__module__
    return handler.__module__  # type: ignore[attr-defined]


def test_every_builtin_refresh_handler_is_domain_owned() -> None:
    assert BUILTIN_PUBLICATION_REFRESH_HANDLERS
    misplaced = {
        key: _owner_module(handler)
        for key, handler in BUILTIN_PUBLICATION_REFRESH_HANDLERS.items()
        if not _owner_module(handler).startswith("packages.domains.")
    }
    assert misplaced == {}
    assert set(get_default_publication_refresh_registry().publication_keys()) == set(
        BUILTIN_PUBLICATION_REFRESH_HANDLERS
    )


def test_facade_exposes_no_per_publication_refresh_methods() -> None:
    refresh_methods = sorted(
        name for name in dir(TransformationService) if name.startswith("refresh_")
    )
    assert refresh_methods == ["refresh_publications"]


def test_store_refresh_handler_runs_the_domain_function_on_the_facade_store() -> None:
    store = DuckDBStore.memory()
    service = TransformationService(store)
    service.load_transactions(
        [
            {
                "booked_at": "2026-01-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            }
        ],
        run_id="run-refresh-001",
    )

    assert service.refresh_publications(["mart_monthly_cashflow"]) == ["mart_monthly_cashflow"]
    assert len(get_monthly_cashflow(store)) == 1


def test_battery_plan_refresh_uses_the_injected_clock_and_profile_loader() -> None:
    from packages.domains.utilities.pipelines.battery_plan_outcome import (
        load_battery_plan_profile,
    )

    calls: list[str] = []
    fixed = datetime(2026, 3, 1, tzinfo=timezone.utc)

    def loader():
        calls.append("loader")
        return load_battery_plan_profile()

    def clock() -> datetime:
        calls.append("clock")
        return fixed

    service = TransformationService(
        DuckDBStore.memory(), battery_plan_profile_loader=loader, clock=clock
    )
    service.refresh_publications(["mart_battery_plan_outcome"])

    assert calls == ["loader", "clock"]
