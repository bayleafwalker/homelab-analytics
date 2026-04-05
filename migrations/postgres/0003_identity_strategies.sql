-- 0003_identity_strategies: per-source entity key resolution configuration
-- Stores the declared identity strategies that transformation layers use to
-- derive stable entity keys from source rows.  The priority_tiers_json column
-- holds an ordered JSON array of tier objects, each with "tier" (int) and
-- "fields" (string array).

CREATE TABLE IF NOT EXISTS identity_strategies (
    strategy_id           TEXT PRIMARY KEY,
    source_dataset_name   TEXT NOT NULL,
    priority_tiers_json   TEXT NOT NULL,
    fallback_mode         TEXT NOT NULL DEFAULT 'reject',
    created_at            TIMESTAMPTZ NOT NULL
);
