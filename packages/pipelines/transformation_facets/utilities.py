"""Utility usage, bills, energy, and battery-plan outcome marts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from packages.domains.utilities.pipelines.battery_plan_outcome import (
    BatteryPlanProfileResolution,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    count_bills,
    count_utility_usage,
    load_bills,
    load_utility_usage,
)
from packages.domains.utilities.pipelines.utility_models import (
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
