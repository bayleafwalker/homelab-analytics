"""Utility usage, bills, energy, and battery-plan outcome marts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from packages.domains.utilities.pipelines.battery_plan_outcome import (
    BatteryPlanProfileResolution,
    get_battery_plan_outcome,
    get_battery_plan_outcome_values,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    count_bills,
    count_utility_usage,
    get_contract_renewal_watchlist,
    get_contract_review_candidates,
    get_energy_daily,
    get_usage_vs_price_summary,
    get_utility_cost_summary,
    get_utility_cost_trend_monthly,
    load_bills,
    load_utility_usage,
)
from packages.domains.utilities.pipelines.utility_models import (
    CURRENT_DIM_METER_VIEW,
    DIM_METER,
)
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class UtilityTransformationMixin(TransformationFacetBase):
    """Utility usage, bills, energy, and battery-plan outcome marts."""

    _battery_plan_profile_loader: Callable[[], BatteryPlanProfileResolution]
    _clock: Callable[[], datetime]

    def count_utility_usage(self, run_id: str | None = None) -> int:
        return count_utility_usage(self._store, run_id=run_id)

    def count_bills(self, run_id: str | None = None) -> int:
        return count_bills(self._store, run_id=run_id)

    def get_current_meters(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_METER_VIEW} ORDER BY meter_id"
        )

    def load_utility_usage(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_utility_usage(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            dim_meter=DIM_METER,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def load_bills(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_bills(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            dim_meter=DIM_METER,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def get_utility_cost_trend_monthly(
        self,
        utility_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_utility_cost_trend_monthly(self._store, utility_type=utility_type)

    def get_battery_plan_outcome(
        self, *, decision_month: str | None = None
    ) -> list[dict[str, Any]]:
        return get_battery_plan_outcome(self._store, decision_month=decision_month)

    def get_battery_plan_outcome_values(
        self, *, decision_month: str | None = None
    ) -> list[dict[str, Any]]:
        return get_battery_plan_outcome_values(self._store, decision_month=decision_month)

    def get_energy_daily(
        self,
        *,
        utility_type: str | None = None,
        from_day: date | str | None = None,
        to_day: date | str | None = None,
    ) -> list[dict[str, Any]]:
        return get_energy_daily(
            self._store,
            utility_type=utility_type,
            from_day=from_day,
            to_day=to_day,
        )

    def get_usage_vs_price_summary(
        self,
        utility_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_usage_vs_price_summary(self._store, utility_type=utility_type)

    def get_contract_review_candidates(self) -> list[dict[str, Any]]:
        return get_contract_review_candidates(self._store)

    def get_contract_renewal_watchlist(self) -> list[dict[str, Any]]:
        return get_contract_renewal_watchlist(self._store)

    def get_utility_cost_summary(
        self,
        *,
        utility_type: str | None = None,
        meter_id: str | None = None,
        from_period: date | str | None = None,
        to_period: date | str | None = None,
        granularity: str = "month",
    ) -> list[dict[str, Any]]:
        return get_utility_cost_summary(
            self._store,
            utility_type=utility_type,
            meter_id=meter_id,
            from_period=from_period,
            to_period=to_period,
            granularity=granularity,
        )
