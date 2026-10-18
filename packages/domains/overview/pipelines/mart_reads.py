"""Overview-pack mart readers served by ReportingService from the warehouse."""

from __future__ import annotations

from packages.domains.overview.pipelines.overview_models import (
    MART_AFFORDABILITY_RATIOS_TABLE,
    MART_COST_TREND_12M_TABLE,
    MART_CURRENT_OPERATING_BASELINE_TABLE,
    MART_HOMELAB_ROI_TABLE,
    MART_HOUSEHOLD_COST_MODEL_TABLE,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
    MART_RECURRING_COST_BASELINE_TABLE,
)
from packages.domains.overview.pipelines.transformation_overview import (
    get_affordability_ratios,
    get_cost_trend_12m,
    get_current_operating_baseline,
    get_homelab_roi,
    get_household_cost_model,
    get_household_overview,
    get_open_attention_items,
    get_recent_significant_changes,
    get_recurring_cost_baseline,
)
from packages.pipelines.mart_read_registry import MartReader

OVERVIEW_MART_READERS: dict[str, MartReader] = {
    MART_HOUSEHOLD_OVERVIEW_TABLE: get_household_overview,
    MART_HOMELAB_ROI_TABLE: get_homelab_roi,
    MART_OPEN_ATTENTION_ITEMS_TABLE: get_open_attention_items,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE: get_recent_significant_changes,
    MART_CURRENT_OPERATING_BASELINE_TABLE: get_current_operating_baseline,
    MART_HOUSEHOLD_COST_MODEL_TABLE: get_household_cost_model,
    MART_COST_TREND_12M_TABLE: get_cost_trend_12m,
    MART_AFFORDABILITY_RATIOS_TABLE: get_affordability_ratios,
    MART_RECURRING_COST_BASELINE_TABLE: get_recurring_cost_baseline,
}
