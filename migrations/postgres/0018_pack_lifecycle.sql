-- 0018_pack_lifecycle: operator-governed pack lifecycle state.
-- Postgres port of sqlite migration 0011_pack_lifecycle. pack_installations
-- holds one row per installed extension pack (installed version, cached
-- registry entry identity, rollback slot, pin, enablement, available versions
-- and compatibility snapshot); pack_lifecycle_events is the append-only audit
-- history of applied and refused lifecycle actions with actor and reason.

CREATE TABLE IF NOT EXISTS pack_installations (
    pack_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    pack_kind TEXT NOT NULL,
    trust_level TEXT NOT NULL,
    installed_version TEXT NOT NULL,
    previous_version TEXT,
    pinned_version TEXT,
    enabled BOOLEAN NOT NULL,
    extension_registry_source_id TEXT NOT NULL,
    extension_registry_revision_id TEXT NOT NULL,
    entry_digest TEXT NOT NULL,
    previous_entry_digest TEXT,
    available_versions TEXT NOT NULL,
    compatibility_snapshot TEXT NOT NULL,
    installed_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pack_lifecycle_events (
    event_id TEXT PRIMARY KEY,
    pack_key TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    from_version TEXT,
    to_version TEXT,
    reason TEXT NOT NULL,
    extension_registry_source_id TEXT,
    extension_registry_revision_id TEXT,
    entry_digest TEXT,
    compatibility_snapshot TEXT NOT NULL,
    plan TEXT NOT NULL,
    actor TEXT NOT NULL,
    actor_role TEXT,
    actor_auth_provider TEXT NOT NULL,
    actor_authenticated BOOLEAN NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pack_lifecycle_events_pack
    ON pack_lifecycle_events (pack_key, occurred_at);
