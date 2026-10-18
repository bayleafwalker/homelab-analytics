-- 0016_action_proposal_queue: durable approval-gated action proposal queue.
-- Postgres port of sqlite migration 0009_action_proposal_queue.
-- action_proposals holds each proposal's current state; status changes are
-- compare-and-set on status, so a resolved proposal cannot be resolved again.
-- idempotency_key is unique: replaying a key returns the proposal it created.
-- Provenance columns keep the evidence trust stamped at draft time and
-- whether the server stamped it or the proposer supplied it.
-- action_proposal_events is the append-only lifecycle history (drafted,
-- refreshed, reopened, approved, dismissed); rows are never updated or deleted.

CREATE TABLE IF NOT EXISTS action_proposals (
    action_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    verdict TEXT NOT NULL,
    value TEXT,
    notification_id TEXT NOT NULL,
    adapter TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_key TEXT,
    source_summary TEXT,
    created_by TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    approved_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    metadata_json TEXT NOT NULL,
    provenance_publication_keys_json TEXT,
    provenance_confidence_verdict TEXT,
    provenance_freshness_state TEXT,
    provenance_assessed_at TEXT,
    provenance_trust_source TEXT,
    resolved_by TEXT,
    resolution_reason TEXT,
    idempotency_key TEXT UNIQUE,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_action_proposals_status_created
    ON action_proposals (status, created_at);

CREATE TABLE IF NOT EXISTS action_proposal_events (
    event_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES action_proposals (action_id),
    sequence INTEGER NOT NULL,
    kind TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    actor TEXT,
    actor_auth_provider TEXT,
    reason TEXT,
    UNIQUE (action_id, sequence)
);
