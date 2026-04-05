-- 0009_publication_confidence_snapshot: Publication confidence model for Stage 9
-- DuckDB warehouse table for storing publication confidence snapshots.

CREATE TABLE IF NOT EXISTS publication_confidence_snapshot (
    snapshot_id VARCHAR PRIMARY KEY,
    publication_key VARCHAR NOT NULL,
    assessed_at TIMESTAMP NOT NULL,
    freshness_state VARCHAR NOT NULL,
    completeness_pct INTEGER NOT NULL,
    quality_flags JSON DEFAULT '{}',
    confidence_verdict VARCHAR NOT NULL,
    contributing_run_ids VARCHAR[],
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_publication_confidence_publication_key_assessed
    ON publication_confidence_snapshot (publication_key, assessed_at DESC);
