"""Home Assistant integration service — entity ingest and history retrieval.

Phase 1 scope (read-only ingest):
- ``ensure_ha_storage``   — create tables if they don't exist (DuckDB)
- ``ingest_ha_states``    — accept a HA /api/states batch, write dim + fact rows
- ``get_ha_entities``     — current state per entity
- ``get_ha_entity_history`` — historian log for one entity

HA state object schema (from HA REST /api/states or WebSocket snapshot):
  entity_id   str        e.g. "sensor.living_room_temp"
  state       str        e.g. "21.3"
  attributes  dict       e.g. {"unit_of_measurement": "°C", "friendly_name": "LR Temp"}
  last_changed str       ISO-8601 timestamp
  last_updated str       ISO-8601 timestamp (ignored — we use last_changed)
  context     dict       ignored in Phase 1
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from packages.pipelines.ha_models import (
    DIM_HA_ENTITY_COLUMNS,
    DIM_HA_ENTITY_TABLE,
    FACT_HA_STATE_CHANGE_COLUMNS,
    FACT_HA_STATE_CHANGE_TABLE,
    entity_class_from_id,
)
from packages.storage.duckdb_store import DuckDBStore


def ensure_ha_storage(store: DuckDBStore) -> None:
    """Create HA tables in DuckDB if they don't exist."""
    store.ensure_table(DIM_HA_ENTITY_TABLE, DIM_HA_ENTITY_COLUMNS)
    store.ensure_table(FACT_HA_STATE_CHANGE_TABLE, FACT_HA_STATE_CHANGE_COLUMNS)


def ingest_ha_states(
    store: DuckDBStore,
    states: list[dict[str, Any]],
    *,
    run_id: str | None = None,
    source_system: str = "home_assistant",
) -> int:
    """Ingest a batch of HA state objects.

    Writes one ``fact_ha_state_change`` row per state and upserts
    ``dim_ha_entity`` (insert new entity or update last_seen / last_state).

    Returns the number of entities upserted.
    """
    ensure_ha_storage(store)

    if not states:
        return 0

    resolved_run_id = run_id or uuid.uuid4().hex[:16]
    now = datetime.now(UTC).isoformat()

    fact_rows: list[dict[str, Any]] = []
    dim_rows: list[dict[str, Any]] = []

    for state in states:
        entity_id = str(state.get("entity_id", "")).strip()
        if not entity_id:
            continue

        raw_state = str(state.get("state", "unknown"))
        attrs = state.get("attributes") or {}
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except (json.JSONDecodeError, ValueError):
                attrs = {}

        changed_at = str(state.get("last_changed") or state.get("last_updated") or now)
        friendly_name = attrs.get("friendly_name") or None
        unit = attrs.get("unit_of_measurement") or None
        area = attrs.get("area_id") or None
        attrs_json = json.dumps(attrs) if attrs else None

        fact_rows.append({
            "entity_id":    entity_id,
            "canonical_id": entity_id,
            "state":        raw_state,
            "attributes":   attrs_json,
            "changed_at":   changed_at,
            "ingested_at":  now,
            "run_id":       resolved_run_id,
        })
        dim_rows.append({
            "entity_id":     entity_id,
            "canonical_id":  entity_id,
            "entity_class":  entity_class_from_id(entity_id),
            "friendly_name": friendly_name,
            "area":          area,
            "unit":          unit,
            "last_seen":     changed_at,
            "last_state":    raw_state,
            "source_system": source_system,
            "ingested_at":   now,
        })

    # Append all fact rows (historian model — no dedup).
    store.insert_rows(FACT_HA_STATE_CHANGE_TABLE, fact_rows)

    # Upsert dim rows: insert if new entity, update last_seen/last_state if existing.
    for row in dim_rows:
        store.execute(
            f"""
            INSERT INTO {DIM_HA_ENTITY_TABLE}
                (entity_id, canonical_id, entity_class, friendly_name, area, unit,
                 last_seen, last_state, source_system, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (entity_id) DO UPDATE SET
                last_seen     = excluded.last_seen,
                last_state    = excluded.last_state,
                friendly_name = COALESCE(excluded.friendly_name, {DIM_HA_ENTITY_TABLE}.friendly_name),
                area          = COALESCE(excluded.area, {DIM_HA_ENTITY_TABLE}.area),
                unit          = COALESCE(excluded.unit, {DIM_HA_ENTITY_TABLE}.unit),
                ingested_at   = excluded.ingested_at
            """,
            [
                row["entity_id"], row["canonical_id"], row["entity_class"],
                row["friendly_name"], row["area"], row["unit"],
                row["last_seen"], row["last_state"], row["source_system"],
                row["ingested_at"],
            ],
        )

    return len(dim_rows)


def get_ha_entities(store: DuckDBStore) -> list[dict[str, Any]]:
    """Return all entities (current state), ordered by entity_id."""
    ensure_ha_storage(store)
    return store.fetchall_dicts(
        f"SELECT * FROM {DIM_HA_ENTITY_TABLE} ORDER BY entity_id"
    )


def get_ha_entity_history(
    store: DuckDBStore,
    entity_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return state-change history for one entity, most recent first."""
    ensure_ha_storage(store)
    return store.fetchall_dicts(
        f"SELECT * FROM {FACT_HA_STATE_CHANGE_TABLE}"
        " WHERE entity_id = ?"
        " ORDER BY changed_at DESC"
        " LIMIT ?",
        [entity_id, limit],
    )
