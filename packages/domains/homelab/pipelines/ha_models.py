"""Home Assistant entity normalization bridge — table definitions.

Defines canonical storage for HA entity state (dim_ha_entity) and the
historian state-change log (fact_ha_state_change).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Dimension: dim_ha_entity
# Flat current-state table; one row per entity_id, upserted on each ingest.
# ---------------------------------------------------------------------------

DIM_HA_ENTITY_TABLE = "dim_ha_entity"

DIM_HA_ENTITY_COLUMNS: list[tuple[str, str]] = [
    ("entity_id",     "VARCHAR PRIMARY KEY"),
    ("canonical_id",  "VARCHAR NOT NULL"),
    ("entity_class",  "VARCHAR NOT NULL"),   # sensor | binary_sensor | switch | light | climate | other
    ("friendly_name", "VARCHAR"),
    ("area",          "VARCHAR"),
    ("unit",          "VARCHAR"),            # unit_of_measurement from HA attributes
    ("last_seen",     "VARCHAR"),            # ISO timestamp of most recent state change
    ("last_state",    "VARCHAR"),            # most recent state value
    ("source_system", "VARCHAR"),
    ("ingested_at",   "VARCHAR NOT NULL"),
]

# ---------------------------------------------------------------------------
# Fact: fact_ha_state_change
# Historian log — every ingest appends a row, no deduplication.
# ---------------------------------------------------------------------------

FACT_HA_STATE_CHANGE_TABLE = "fact_ha_state_change"

FACT_HA_STATE_CHANGE_COLUMNS: list[tuple[str, str]] = [
    ("entity_id",    "VARCHAR NOT NULL"),
    ("canonical_id", "VARCHAR NOT NULL"),
    ("state",        "VARCHAR NOT NULL"),
    ("attributes",   "VARCHAR"),            # JSON blob of HA attributes
    ("changed_at",   "VARCHAR NOT NULL"),   # last_changed from HA (ISO timestamp)
    ("ingested_at",  "VARCHAR NOT NULL"),   # platform ingest timestamp
    ("run_id",       "VARCHAR"),
]

# ---------------------------------------------------------------------------
# Entity class derivation
# ---------------------------------------------------------------------------

_KNOWN_CLASSES = frozenset({
    "sensor", "binary_sensor", "switch", "light", "climate",
    "cover", "fan", "lock", "media_player", "weather",
    "person", "zone", "device_tracker", "input_boolean",
    "input_number", "input_select", "number", "select",
    "button", "scene", "script", "automation",
})


def entity_class_from_id(entity_id: str) -> str:
    """Derive entity class from HA entity_id prefix (e.g. 'sensor.temp' → 'sensor')."""
    prefix = entity_id.split(".")[0] if "." in entity_id else entity_id
    return prefix if prefix in _KNOWN_CLASSES else "other"
