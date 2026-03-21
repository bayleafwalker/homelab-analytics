-- 0002_ha_entity_tables: Home Assistant entity normalization bridge
-- dim_ha_entity holds one row per HA entity (upserted on ingest: last_seen / last_state updated).
-- fact_ha_state_change is a historian log — every ingest writes a new row, no dedup.

CREATE TABLE IF NOT EXISTS dim_ha_entity (
    entity_id     TEXT PRIMARY KEY,
    canonical_id  TEXT NOT NULL,
    entity_class  TEXT NOT NULL,
    friendly_name TEXT,
    area          TEXT,
    unit          TEXT,
    last_seen     TEXT,
    last_state    TEXT,
    source_system TEXT,
    ingested_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_ha_state_change (
    entity_id    TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    state        TEXT NOT NULL,
    attributes   TEXT,
    changed_at   TEXT NOT NULL,
    ingested_at  TEXT NOT NULL,
    run_id       TEXT
);
