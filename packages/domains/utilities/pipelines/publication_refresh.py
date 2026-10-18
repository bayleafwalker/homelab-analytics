"""Utilities-pack publication refresh handlers.

Each handler refreshes one reporting publication from this pack's
transformation functions; the household composition registers them with the
publication refresh registry.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from packages.domains.utilities.pipelines.battery_plan_outcome import (
    BatteryPlanProfileResolution,
    refresh_battery_plan_outcome,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    refresh_contract_renewal_watchlist,
    refresh_contract_review_candidates,
    refresh_energy_daily,
    refresh_usage_vs_price_summary,
    refresh_utility_cost_summary,
    refresh_utility_cost_trend_monthly,
)
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshHandler,
    StoreRefreshHandler,
)
from packages.storage.duckdb_store import DuckDBStore


class BatteryPlanRefreshTarget(Protocol):
    """What the battery-plan refresh needs from the transformation facade."""

    @property
    def store(self) -> DuckDBStore: ...

    @property
    def battery_plan_profile_loader(self) -> Callable[[], BatteryPlanProfileResolution]: ...

    @property
    def clock(self) -> Callable[[], datetime]: ...


def refresh_battery_plan_publication(service: BatteryPlanRefreshTarget) -> int:
    """Rebuild mart_battery_plan_outcome and its value disclosures together."""
    return refresh_battery_plan_outcome(
        service.store,
        resolution=service.battery_plan_profile_loader(),
        assessed_at=service.clock(),
    )


UTILITIES_PUBLICATION_REFRESH_HANDLERS: dict[str, PublicationRefreshHandler] = {
    "mart_utility_cost_summary": StoreRefreshHandler(refresh_utility_cost_summary),
    "mart_utility_cost_trend_monthly": StoreRefreshHandler(refresh_utility_cost_trend_monthly),
    "mart_usage_vs_price_summary": StoreRefreshHandler(refresh_usage_vs_price_summary),
    "mart_energy_daily": StoreRefreshHandler(refresh_energy_daily),
    "mart_battery_plan_outcome": refresh_battery_plan_publication,
    "mart_battery_plan_outcome_values": refresh_battery_plan_publication,
    "mart_contract_review_candidates": StoreRefreshHandler(refresh_contract_review_candidates),
    "mart_contract_renewal_watchlist": StoreRefreshHandler(refresh_contract_renewal_watchlist),
}
