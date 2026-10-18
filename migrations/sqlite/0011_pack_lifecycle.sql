-- 0011_pack_lifecycle: operator-governed pack lifecycle state.
-- pack_installations holds one row per installed extension pack: the
-- installed version and the cached registry entry it came from (source,
-- revision, entry digest), the version parked for rollback, an optional
-- operator pin, enablement, the available versions observed at the last
-- lifecycle action and the compatibility diagnostics snapshot.
-- pack_lifecycle_events is the append-only audit history of every applied or
-- refused install/upgrade/rollback/disable/enable/pin/unpin with actor and
-- reason. Events are never updated.

CREATE TABLE IF NOT EXISTS pack_installations (
    pack_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    pack_kind TEXT NOT NULL,
    trust_level TEXT NOT NULL,
    installed_version TEXT NOT NULL,
    previous_version TEXT,
    pinned_version TEXT,
    enabled INTEGER NOT NULL,
    extension_registry_source_id TEXT NOT NULL,
    extension_registry_revision_id TEXT NOT NULL,
    entry_digest TEXT NOT NULL,
    previous_entry_digest TEXT,
    available_versions TEXT NOT NULL,
    compatibility_snapshot TEXT NOT NULL,
    installed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
    actor_authenticated INTEGER NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pack_lifecycle_events_pack
    ON pack_lifecycle_events (pack_key, occurred_at);
