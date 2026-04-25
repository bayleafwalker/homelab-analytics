-- 0007_policy_registry: Operator-authored policy definitions for Stage 5 policy engine.
-- Stores both seeded built-in policies and operator-authored policies.
-- rule_document is a validated JSON rule schema document (policy_schema.py).
-- source_kind: 'builtin' for seeded defaults, 'operator' for user-created.

CREATE TABLE IF NOT EXISTS policy_definitions (
    policy_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT,
    policy_kind TEXT NOT NULL,
    rule_schema_version TEXT NOT NULL DEFAULT '1.0',
    rule_document TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    source_kind TEXT NOT NULL DEFAULT 'operator',
    creator TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_policy_definitions_enabled_source_kind
    ON policy_definitions (enabled, source_kind);
