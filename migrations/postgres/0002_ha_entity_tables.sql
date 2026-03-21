-- 0002_ha_entity_tables: Home Assistant entity normalization bridge
-- dim_ha_entity holds one row per HA entity (upserted on ingest: last_seen / last_state updated).
-- fact_ha_state_change is a historian log — every ingest writes a new row, no dedup.

CREATE TABLE IF NOT EXISTS dim_ha_entity (
    entity_id     VARCHAR PRIMARY KEY,
    canonical_id  VARCHAR NOT NULL,
    entity_class  VARCHAR NOT NULL,
    friendly_name VARCHAR,
    area          VARCHAR,
    unit          VARCHAR,
    last_seen     VARCHAR,
    last_state    VARCHAR,
    source_system VARCHAR,
    ingested_at   VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_ha_state_change (
    entity_id    VARCHAR NOT NULL,
    canonical_id VARCHAR NOT NULL,
    state        VARCHAR NOT NULL,
    attributes   TEXT,
    changed_at   VARCHAR NOT NULL,
    ingested_at  VARCHAR NOT NULL,
    run_id       VARCHAR
);
