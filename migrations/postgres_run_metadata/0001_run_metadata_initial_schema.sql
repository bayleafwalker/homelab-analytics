-- 0001_run_metadata_initial_schema: Postgres run-metadata baseline
-- Dedicated migration track for ingestion run metadata so run-metadata
-- repositories do not need to initialize full control-plane schema objects.

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    file_name TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    manifest_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    header_json TEXT NOT NULL,
    status TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS ingestion_run_issues (
    run_id TEXT NOT NULL,
    issue_order INTEGER NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    column_name TEXT,
    row_number INTEGER,
    PRIMARY KEY (run_id, issue_order),
    FOREIGN KEY (run_id) REFERENCES ingestion_runs (run_id)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_dataset_status_created
    ON ingestion_runs (dataset_name, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_sha_dataset_created
    ON ingestion_runs (sha256, dataset_name, created_at ASC);
