-- 0001_initial_schema: baseline control-plane + run-metadata tables
-- Captures the full schema as of Sprint F-pre (stabilization).
-- All statements use CREATE TABLE IF NOT EXISTS so this migration is safe
-- against existing databases that were initialized by the legacy schema-init code.

CREATE TABLE IF NOT EXISTS source_systems (
    source_system_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    transport TEXT NOT NULL,
    schedule_mode TEXT NOT NULL,
    description TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_contracts (
    dataset_contract_id TEXT PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    allow_extra_columns INTEGER NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    columns_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS column_mappings (
    column_mapping_id TEXT PRIMARY KEY,
    source_system_id TEXT NOT NULL,
    dataset_contract_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    rules_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_system_id) REFERENCES source_systems (source_system_id),
    FOREIGN KEY (dataset_contract_id) REFERENCES dataset_contracts (dataset_contract_id)
);

CREATE TABLE IF NOT EXISTS transformation_packages (
    transformation_package_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    handler_key TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publication_definitions (
    publication_definition_id TEXT PRIMARY KEY,
    transformation_package_id TEXT NOT NULL,
    publication_key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (transformation_package_id) REFERENCES transformation_packages (transformation_package_id)
);

CREATE TABLE IF NOT EXISTS source_assets (
    source_asset_id TEXT PRIMARY KEY,
    source_system_id TEXT NOT NULL,
    dataset_contract_id TEXT NOT NULL,
    column_mapping_id TEXT NOT NULL,
    transformation_package_id TEXT,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    description TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_system_id) REFERENCES source_systems (source_system_id),
    FOREIGN KEY (dataset_contract_id) REFERENCES dataset_contracts (dataset_contract_id),
    FOREIGN KEY (column_mapping_id) REFERENCES column_mappings (column_mapping_id),
    FOREIGN KEY (transformation_package_id) REFERENCES transformation_packages (transformation_package_id)
);

CREATE TABLE IF NOT EXISTS ingestion_definitions (
    ingestion_definition_id TEXT PRIMARY KEY,
    source_asset_id TEXT NOT NULL,
    transport TEXT NOT NULL,
    schedule_mode TEXT NOT NULL,
    source_path TEXT NOT NULL,
    file_pattern TEXT NOT NULL,
    processed_path TEXT,
    failed_path TEXT,
    poll_interval_seconds INTEGER,
    request_url TEXT,
    request_method TEXT,
    request_headers_json TEXT,
    request_timeout_seconds INTEGER,
    response_format TEXT,
    output_file_name TEXT,
    enabled INTEGER NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    source_name TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_asset_id) REFERENCES source_assets (source_asset_id)
);

CREATE TABLE IF NOT EXISTS extension_registry_sources (
    extension_registry_source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    location TEXT NOT NULL,
    desired_ref TEXT,
    subdirectory TEXT,
    auth_secret_name TEXT,
    auth_secret_key TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extension_registry_revisions (
    extension_registry_revision_id TEXT PRIMARY KEY,
    extension_registry_source_id TEXT NOT NULL,
    resolved_ref TEXT,
    runtime_path TEXT,
    manifest_path TEXT,
    manifest_digest TEXT,
    manifest_version INTEGER,
    content_fingerprint TEXT,
    import_paths_json TEXT NOT NULL DEFAULT '[]',
    extension_modules_json TEXT NOT NULL DEFAULT '[]',
    function_modules_json TEXT NOT NULL DEFAULT '[]',
    minimum_platform_version TEXT,
    sync_status TEXT NOT NULL,
    validation_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (extension_registry_source_id) REFERENCES extension_registry_sources (extension_registry_source_id)
);

CREATE TABLE IF NOT EXISTS extension_registry_activations (
    extension_registry_source_id TEXT PRIMARY KEY,
    extension_registry_revision_id TEXT NOT NULL,
    activated_at TEXT NOT NULL,
    FOREIGN KEY (extension_registry_source_id) REFERENCES extension_registry_sources (extension_registry_source_id),
    FOREIGN KEY (extension_registry_revision_id) REFERENCES extension_registry_revisions (extension_registry_revision_id)
);

CREATE TABLE IF NOT EXISTS execution_schedules (
    schedule_id TEXT PRIMARY KEY,
    target_kind TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    timezone TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    max_concurrency INTEGER NOT NULL,
    next_due_at TEXT,
    last_enqueued_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_dispatches (
    dispatch_id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    enqueued_at TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    run_ids_json TEXT NOT NULL DEFAULT '[]',
    failure_reason TEXT,
    worker_detail TEXT,
    claimed_by_worker_id TEXT,
    claimed_at TEXT,
    claim_expires_at TEXT,
    FOREIGN KEY (schedule_id) REFERENCES execution_schedules (schedule_id)
);

CREATE TABLE IF NOT EXISTS worker_heartbeats (
    worker_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    active_dispatch_id TEXT,
    detail TEXT,
    observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_lineage (
    lineage_id TEXT PRIMARY KEY,
    input_run_id TEXT,
    target_layer TEXT NOT NULL,
    target_name TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    row_count INTEGER,
    source_system TEXT,
    source_run_id TEXT,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publication_audit (
    publication_audit_id TEXT PRIMARY KEY,
    run_id TEXT,
    publication_key TEXT NOT NULL,
    relation_name TEXT NOT NULL,
    status TEXT NOT NULL,
    published_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS local_users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS auth_audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    success INTEGER NOT NULL,
    actor_user_id TEXT,
    actor_username TEXT,
    subject_user_id TEXT,
    subject_username TEXT,
    remote_addr TEXT,
    user_agent TEXT,
    detail TEXT,
    occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS service_tokens (
    token_id TEXT PRIMARY KEY,
    token_name TEXT NOT NULL,
    token_secret_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT
);

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
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL
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
