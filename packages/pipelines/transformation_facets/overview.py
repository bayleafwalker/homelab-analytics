"""Cross-domain household overview marts."""

from __future__ import annotations

from typing import Any

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
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class OverviewTransformationMixin(TransformationFacetBase):
    """Cross-domain household overview marts."""

    def refresh_household_overview(self) -> int:
        return refresh_household_overview(self._store)

    def get_household_overview(self) -> list[dict[str, Any]]:
        return get_household_overview(self._store)

    def refresh_homelab_roi(self) -> int:
        return refresh_homelab_roi(self._store)

    def get_homelab_roi(self) -> list[dict[str, Any]]:
        return get_homelab_roi(self._store)

    def refresh_open_attention_items(self) -> int:
        return refresh_open_attention_items(self._store)

    def get_open_attention_items(self) -> list[dict[str, Any]]:
        return get_open_attention_items(self._store)

    def refresh_recent_significant_changes(self) -> int:
        return refresh_recent_significant_changes(self._store)

    def get_recent_significant_changes(self) -> list[dict[str, Any]]:
        return get_recent_significant_changes(self._store)

    def refresh_current_operating_baseline(self) -> int:
        return refresh_current_operating_baseline(self._store)

    def get_current_operating_baseline(self) -> list[dict[str, Any]]:
        return get_current_operating_baseline(self._store)

    def refresh_household_cost_model(self) -> int:
        return refresh_household_cost_model(self._store)

    def get_household_cost_model(
        self,
        *,
        period_label: str | None = None,
        cost_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_household_cost_model(
            self._store, period_label=period_label, cost_type=cost_type
        )

    def refresh_cost_trend_12m(self) -> int:
        return refresh_cost_trend_12m(self._store)

    def get_cost_trend_12m(self) -> list[dict[str, Any]]:
        return get_cost_trend_12m(self._store)

    def refresh_affordability_ratios(self) -> int:
        return refresh_affordability_ratios(self._store)

    def get_affordability_ratios(self) -> list[dict[str, Any]]:
        return get_affordability_ratios(self._store)

    def refresh_recurring_cost_baseline(self) -> int:
        return refresh_recurring_cost_baseline(self._store)

    def get_recurring_cost_baseline(self) -> list[dict[str, Any]]:
        return get_recurring_cost_baseline(self._store)
