"""Home automation state, sensors, automation events, and HA ingest."""

from __future__ import annotations

from datetime import date
from typing import Any

from packages.domains.homelab.pipelines.ha_service import (
    ingest_ha_states,
)
from packages.domains.homelab.pipelines.transformation_home_automation import (
    count_automation_event_rows,
    count_home_automation_state_rows,
    count_sensor_reading_rows,
    load_automation_events,
    load_home_automation_state_rows,
    load_sensor_readings,
)
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class HomeAutomationTransformationMixin(TransformationFacetBase):
    """Home automation state, sensors, automation events, and HA ingest."""

    def load_home_automation_state(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_home_automation_state_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def load_sensor_readings(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_sensor_readings(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def load_automation_events(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_automation_events(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def count_sensor_reading_rows(self, run_id: str | None = None) -> int:
        return count_sensor_reading_rows(self._store, run_id=run_id)

    def count_automation_event_rows(self, run_id: str | None = None) -> int:
        return count_automation_event_rows(self._store, run_id=run_id)

    def count_home_automation_state_rows(self, run_id: str | None = None) -> int:
        return count_home_automation_state_rows(self._store, run_id=run_id)

    def ingest_ha_states(
        self,
        states: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str = "home_assistant",
    ) -> int:
        return ingest_ha_states(
            self._store,
            states,
            run_id=run_id,
            source_system=source_system,
        )
