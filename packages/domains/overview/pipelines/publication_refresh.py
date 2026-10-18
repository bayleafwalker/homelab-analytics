"""Overview-pack publication refresh handlers.

Each handler refreshes one reporting publication from this pack's
transformation functions; the household composition registers them with the
publication refresh registry.
"""

from __future__ import annotations

from packages.domains.overview.pipelines.transformation_overview import (
    refresh_affordability_ratios,
    refresh_cost_trend_12m,
    refresh_current_operating_baseline,
    refresh_homelab_roi,
    refresh_household_cost_model,
    refresh_household_overview,
    refresh_open_attention_items,
    refresh_recent_significant_changes,
    refresh_recurring_cost_baseline,
)
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshHandler,
    StoreRefreshHandler,
)

OVERVIEW_PUBLICATION_REFRESH_HANDLERS: dict[str, PublicationRefreshHandler] = {
    "mart_household_overview": StoreRefreshHandler(refresh_household_overview),
    "mart_homelab_roi": StoreRefreshHandler(refresh_homelab_roi),
    "mart_open_attention_items": StoreRefreshHandler(refresh_open_attention_items),
    "mart_recent_significant_changes": StoreRefreshHandler(refresh_recent_significant_changes),
    "mart_current_operating_baseline": StoreRefreshHandler(refresh_current_operating_baseline),
    "mart_household_cost_model": StoreRefreshHandler(refresh_household_cost_model),
    "mart_cost_trend_12m": StoreRefreshHandler(refresh_cost_trend_12m),
    "mart_affordability_ratios": StoreRefreshHandler(refresh_affordability_ratios),
    "mart_recurring_cost_baseline": StoreRefreshHandler(refresh_recurring_cost_baseline),
}
