from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition, DuckDBStore

DIM_ENTITY = DimensionDefinition(
    table_name="dim_entity",
    natural_key_columns=("entity_id",),
    attribute_columns=(
        DimensionColumn("entity_name", "VARCHAR"),
        DimensionColumn("entity_domain", "VARCHAR"),
        DimensionColumn("entity_class", "VARCHAR"),
        DimensionColumn("device_name", "VARCHAR"),
        DimensionColumn("area", "VARCHAR"),
        DimensionColumn("integration", "VARCHAR"),
        DimensionColumn("unit", "VARCHAR"),
    ),
)

CURRENT_DIM_ENTITY_VIEW = "rpt_current_dim_entity"

FACT_SENSOR_READING_TABLE = "fact_sensor_reading"

FACT_SENSOR_READING_COLUMNS: list[tuple[str, str]] = [
    ("sensor_reading_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("entity_id", "VARCHAR NOT NULL"),
    ("entity_name", "VARCHAR NOT NULL"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
    ("state", "VARCHAR NOT NULL"),
    ("unit", "VARCHAR"),
    ("attributes", "VARCHAR"),
    ("source_system", "VARCHAR"),
]

FACT_AUTOMATION_EVENT_TABLE = "fact_automation_event"

FACT_AUTOMATION_EVENT_COLUMNS: list[tuple[str, str]] = [
    ("automation_event_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("entity_id", "VARCHAR NOT NULL"),
    ("entity_name", "VARCHAR NOT NULL"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
    ("state", "VARCHAR NOT NULL"),
    ("trigger", "VARCHAR"),
    ("result", "VARCHAR NOT NULL"),
    ("attributes", "VARCHAR"),
    ("source_system", "VARCHAR"),
]

_KNOWN_CLASSES = frozenset(
    {
        "sensor",
        "binary_sensor",
        "switch",
        "light",
        "climate",
        "cover",
        "fan",
        "lock",
        "media_player",
        "weather",
        "person",
        "zone",
        "device_tracker",
        "input_boolean",
        "input_number",
        "input_select",
        "number",
        "select",
        "button",
        "scene",
        "script",
        "automation",
    }
)
_AUTOMATION_CLASSES = frozenset({"automation", "script"})


def entity_class_from_id(entity_id: str) -> str:
    prefix = entity_id.split(".", 1)[0] if "." in entity_id else entity_id
    return prefix if prefix in _KNOWN_CLASSES else "other"


def ensure_home_automation_storage(store: DuckDBStore) -> None:
    store.ensure_dimension(DIM_ENTITY)
    store.ensure_current_dimension_view(DIM_ENTITY, CURRENT_DIM_ENTITY_VIEW)
    store.ensure_table(FACT_SENSOR_READING_TABLE, FACT_SENSOR_READING_COLUMNS)
    store.ensure_table(FACT_AUTOMATION_EVENT_TABLE, FACT_AUTOMATION_EVENT_COLUMNS)


def load_home_automation_state_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: Callable[..., None],
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    ensure_home_automation_storage(store)
    entity_rows = _extract_entities(rows, source_system=source_system)
    sensor_rows = _extract_sensor_readings(rows, run_id=run_id, source_system=source_system)
    automation_rows = _extract_automation_events(
        rows,
        run_id=run_id,
        source_system=source_system,
    )
    eff = effective_date or _infer_effective_date(rows) or date.today()

    with store.atomic():
        entities_upserted = store.upsert_dimension_rows(
            DIM_ENTITY,
            entity_rows,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )
        sensor_inserted = store.insert_rows(FACT_SENSOR_READING_TABLE, sensor_rows)
        automation_inserted = store.insert_rows(
            FACT_AUTOMATION_EVENT_TABLE,
            automation_rows,
        )

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_entity", "dimension", entities_upserted),
            (FACT_SENSOR_READING_TABLE, "fact", sensor_inserted),
            (FACT_AUTOMATION_EVENT_TABLE, "fact", automation_inserted),
        ],
    )
    return sensor_inserted + automation_inserted


def load_sensor_readings(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: Callable[..., None],
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    return load_home_automation_state_rows(
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
    record_lineage: Callable[..., None],
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    return load_home_automation_state_rows(
        store,
        rows=rows,
        record_lineage=record_lineage,
        run_id=run_id,
        effective_date=effective_date,
        source_system=source_system,
    )


def get_current_entities(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(f"SELECT * FROM {CURRENT_DIM_ENTITY_VIEW} ORDER BY entity_id")


def count_sensor_reading_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_SENSOR_READING_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_SENSOR_READING_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def count_automation_event_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_AUTOMATION_EVENT_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_AUTOMATION_EVENT_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def count_home_automation_state_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    return count_sensor_reading_rows(store, run_id=run_id) + count_automation_event_rows(
        store,
        run_id=run_id,
    )


def _extract_entities(
    rows: list[dict[str, Any]],
    *,
    source_system: str | None,
) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        entity_id = str(row.get("entity_id", "")).strip()
        if not entity_id:
            continue
        attrs = _coerce_attributes(row.get("attributes"))
        entity_class = entity_class_from_id(entity_id)
        entity_name = _entity_name(row, attrs, entity_id)
        seen[entity_id] = {
            "entity_id": entity_id,
            "entity_name": entity_name,
            "entity_domain": entity_class,
            "entity_class": entity_class,
            "device_name": attrs.get("device_name") or attrs.get("device_id"),
            "area": attrs.get("area") or attrs.get("area_id"),
            "integration": attrs.get("integration") or source_system,
            "unit": attrs.get("unit_of_measurement") or row.get("unit"),
        }
    return list(seen.values())


def _extract_sensor_readings(
    rows: list[dict[str, Any]],
    *,
    run_id: str | None,
    source_system: str | None,
) -> list[dict[str, Any]]:
    fact_rows: list[dict[str, Any]] = []
    for row in rows:
        entity_id = str(row.get("entity_id", "")).strip()
        if not entity_id or _is_automation_row(row):
            continue
        attrs = _coerce_attributes(row.get("attributes"))
        recorded_at = _coerce_datetime(
            row.get("recorded_at") or row.get("last_changed") or row.get("last_updated")
        )
        state = str(row.get("state", "unknown"))
        fact_rows.append(
            {
                "sensor_reading_id": uuid.uuid4().hex[:16],
                "run_id": run_id,
                "entity_id": entity_id,
                "entity_name": _entity_name(row, attrs, entity_id),
                "recorded_at": recorded_at,
                "state": state,
                "unit": attrs.get("unit_of_measurement") or row.get("unit"),
                "attributes": json.dumps(attrs) if attrs else None,
                "source_system": source_system,
            }
        )
    return fact_rows


def _extract_automation_events(
    rows: list[dict[str, Any]],
    *,
    run_id: str | None,
    source_system: str | None,
) -> list[dict[str, Any]]:
    fact_rows: list[dict[str, Any]] = []
    for row in rows:
        entity_id = str(row.get("entity_id", "")).strip()
        if not entity_id or not _is_automation_row(row):
            continue
        attrs = _coerce_attributes(row.get("attributes"))
        recorded_at = _coerce_datetime(
            row.get("recorded_at")
            or row.get("last_changed")
            or row.get("last_triggered")
            or row.get("last_updated")
        )
        state = str(row.get("state", "unknown"))
        event_result = str(row.get("result") or attrs.get("result") or state)
        fact_rows.append(
            {
                "automation_event_id": uuid.uuid4().hex[:16],
                "run_id": run_id,
                "entity_id": entity_id,
                "entity_name": _entity_name(row, attrs, entity_id),
                "recorded_at": recorded_at,
                "state": state,
                "trigger": row.get("trigger") or attrs.get("trigger"),
                "result": event_result,
                "attributes": json.dumps(attrs) if attrs else None,
                "source_system": source_system,
            }
        )
    return fact_rows


def _is_automation_row(row: dict[str, Any]) -> bool:
    if str(row.get("record_type", "")).strip() == "automation_event":
        return True
    entity_class = entity_class_from_id(str(row.get("entity_id", "")))
    return entity_class in _AUTOMATION_CLASSES


def _entity_name(
    row: dict[str, Any],
    attrs: dict[str, Any],
    fallback: str,
) -> str:
    return str(
        row.get("entity_name")
        or attrs.get("friendly_name")
        or attrs.get("name")
        or fallback
    )


def _coerce_attributes(value: object | None) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _coerce_datetime(value: object | None) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=UTC)
    if value is None or value == "":
        return datetime.now(UTC)
    return datetime.fromisoformat(str(value))


def _infer_effective_date(rows: list[dict[str, Any]]) -> date | None:
    timestamps = [
        _coerce_datetime(
            row.get("recorded_at") or row.get("last_changed") or row.get("last_updated")
        )
        for row in rows
        if row.get("entity_id")
    ]
    if not timestamps:
        return None
    return min(ts.date() for ts in timestamps)
