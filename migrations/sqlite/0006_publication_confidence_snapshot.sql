-- 0005_publication_confidence_snapshot: Publication confidence model for Stage 9
-- Stores deterministic confidence snapshots for each publication after mart refresh.

CREATE TABLE IF NOT EXISTS publication_confidence_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    publication_key TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    freshness_state TEXT NOT NULL,
    completeness_pct INTEGER NOT NULL,
    quality_flags TEXT,
    confidence_verdict TEXT NOT NULL,
    contributing_run_ids TEXT,
    source_freshness_states TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_publication_confidence_publication_key_assessed
    ON publication_confidence_snapshot (publication_key, assessed_at DESC);
