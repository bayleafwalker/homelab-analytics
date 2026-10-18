"""Home automation state, sensors, automation events, and HA ingest."""

from __future__ import annotations

from datetime import date
from typing import Any

from packages.domains.homelab.pipelines.ha_service import (
    get_ha_entities,
    get_ha_entity_history,
    ingest_ha_states,
)
from packages.domains.homelab.pipelines.transformation_home_automation import (
    count_automation_event_rows,
    count_home_automation_state_rows,
    count_sensor_reading_rows,
    get_automation_reliability,
    get_climate_summary,
    get_current_entities,
    get_device_battery,
    load_automation_events,
    load_home_automation_state_rows,
    load_sensor_readings,
    refresh_automation_reliability,
    refresh_climate_summary,
    refresh_device_battery,
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

    def get_current_entities(self) -> list[dict[str, Any]]:
        return get_current_entities(self._store)

    def refresh_climate_summary(self) -> int:
        return refresh_climate_summary(self._store)

    def refresh_automation_reliability(self) -> int:
        return refresh_automation_reliability(self._store)

    def refresh_device_battery(self) -> int:
        return refresh_device_battery(self._store)

    def get_climate_summary(
        self,
        *,
        area: str | None = None,
        measure: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_climate_summary(self._store, area=area, measure=measure)

    def get_automation_reliability(
        self,
        *,
        entity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_automation_reliability(self._store, entity_id=entity_id)

    def get_device_battery(
        self,
        *,
        battery_status: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_device_battery(self._store, battery_status=battery_status)

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

    def get_ha_entities(self) -> list[dict[str, Any]]:
        return get_ha_entities(self._store)

    def get_ha_entity_history(
        self, entity_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        return get_ha_entity_history(self._store, entity_id, limit=limit)
