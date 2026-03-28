-- 0004_source_freshness_config: companion freshness config for source assets

CREATE TABLE IF NOT EXISTS source_freshness_configs (
    source_asset_id TEXT PRIMARY KEY,
    acquisition_mode TEXT NOT NULL,
    expected_frequency TEXT NOT NULL,
    coverage_kind TEXT NOT NULL,
    due_day_of_month INTEGER,
    expected_window_days INTEGER NOT NULL,
    freshness_sla_days INTEGER NOT NULL,
    sensitivity_class TEXT NOT NULL,
    reminder_channel TEXT NOT NULL,
    requires_human_action INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_asset_id) REFERENCES source_assets (source_asset_id) ON DELETE CASCADE
);
