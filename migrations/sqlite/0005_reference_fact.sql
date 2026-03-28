-- 0005_reference_fact: versioned manual reference facts for finance lane C

CREATE TABLE IF NOT EXISTS reference_facts (
    fact_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    source TEXT NOT NULL,
    created_by TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    closed_by TEXT,
    closed_at TEXT,
    UNIQUE (entity_type, entity_key, attribute, effective_from)
);

CREATE INDEX IF NOT EXISTS idx_reference_facts_entity_version
    ON reference_facts (entity_type, entity_key, attribute, effective_from);
