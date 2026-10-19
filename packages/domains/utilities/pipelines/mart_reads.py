"""Utilities-pack mart readers served by ReportingService from the warehouse."""

from __future__ import annotations

from packages.domains.utilities.pipelines.battery_plan_models import (
    MART_BATTERY_PLAN_OUTCOME_TABLE,
    MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE,
)
from packages.domains.utilities.pipelines.battery_plan_outcome import (
    get_battery_plan_outcome,
    get_battery_plan_outcome_values,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    get_contract_renewal_watchlist,
    get_contract_review_candidates,
    get_usage_vs_price_summary,
    get_utility_cost_summary,
    get_utility_cost_trend_monthly,
)
from packages.domains.utilities.pipelines.utility_models import (
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
    MART_USAGE_VS_PRICE_SUMMARY_TABLE,
    MART_UTILITY_COST_SUMMARY_TABLE,
    MART_UTILITY_COST_TREND_MONTHLY_TABLE,
)
from packages.pipelines.mart_read_registry import MartReader

UTILITIES_MART_READERS: dict[str, MartReader] = {
    MART_UTILITY_COST_SUMMARY_TABLE: get_utility_cost_summary,
    MART_UTILITY_COST_TREND_MONTHLY_TABLE: get_utility_cost_trend_monthly,
    MART_USAGE_VS_PRICE_SUMMARY_TABLE: get_usage_vs_price_summary,
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE: get_contract_review_candidates,
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE: get_contract_renewal_watchlist,
    MART_BATTERY_PLAN_OUTCOME_TABLE: get_battery_plan_outcome,
    MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE: get_battery_plan_outcome_values,
}
