from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from packages.domains.homelab.pipelines.home_automation_models import (
    CURRENT_DIM_ENTITY_VIEW,
    DIM_ENTITY,
    FACT_AUTOMATION_EVENT_COLUMNS,
    FACT_AUTOMATION_EVENT_TABLE,
    FACT_SENSOR_READING_COLUMNS,
    FACT_SENSOR_READING_TABLE,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    count_automation_event_rows as _count_automation_event_rows,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    count_home_automation_state_rows as _count_home_automation_state_rows,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    count_sensor_reading_rows as _count_sensor_reading_rows,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    get_current_entities as _get_current_entities,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    load_automation_events as _load_automation_events,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    load_home_automation_state_rows as _load_home_automation_state_rows,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    load_sensor_readings as _load_sensor_readings,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def ensure_home_automation_storage(store: DuckDBStore) -> None:
    store.ensure_dimension(DIM_ENTITY)
    store.ensure_current_dimension_view(DIM_ENTITY, CURRENT_DIM_ENTITY_VIEW)
    store.ensure_table(FACT_SENSOR_READING_TABLE, FACT_SENSOR_READING_COLUMNS)
    store.ensure_table(FACT_AUTOMATION_EVENT_TABLE, FACT_AUTOMATION_EVENT_COLUMNS)


def load_home_automation_state_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    return _load_home_automation_state_rows(
        store,
        rows=rows,
        record_lineage=record_lineage,
        run_id=run_id,
        effective_date=effective_date,
        source_system=source_system,
    )


def load_sensor_readings(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    return _load_sensor_readings(
        store,
        rows=rows,
        record_lineage=record_lineage,
        run_id=run_id,
        effective_date=effective_date,
        source_system=source_system,
    )


def load_automation_events(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    return _load_automation_events(
        store,
        rows=rows,
        record_lineage=record_lineage,
        run_id=run_id,
        effective_date=effective_date,
        source_system=source_system,
    )


def get_current_entities(store: DuckDBStore) -> list[dict[str, Any]]:
    return _get_current_entities(store)


def count_sensor_reading_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    return _count_sensor_reading_rows(store, run_id=run_id)


def count_automation_event_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    return _count_automation_event_rows(store, run_id=run_id)


def count_home_automation_state_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    return _count_home_automation_state_rows(store, run_id=run_id)
