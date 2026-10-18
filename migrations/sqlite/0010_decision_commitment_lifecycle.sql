-- 0010_decision_commitment_lifecycle: commitment terms and lifecycle events
-- for the append-only decision ledger (HLA-K01 / HLA-K02).
-- decision_commitments pins, per decision record, the lifecycle terms of the
-- decision definition version it was made under (purpose, owner, baseline,
-- success measure, observation window, review triggers, stop conditions) and
-- the evidence fingerprint used for correction tracing.
-- decision_lifecycle_events records operator stop/reopen and evidence
-- supersession; dedupe_key makes repeated correction delivery idempotent.
-- Both tables are append-only; decision_records is unchanged.

CREATE TABLE IF NOT EXISTS decision_commitments (
    decision_id TEXT PRIMARY KEY REFERENCES decision_records (decision_id),
    purpose TEXT NOT NULL,
    owner_role TEXT NOT NULL,
    owner_principal TEXT,
    owner_verified INTEGER NOT NULL,
    baseline TEXT NOT NULL,
    success_measure TEXT NOT NULL,
    observation_window_start TEXT NOT NULL,
    observation_window_end TEXT NOT NULL,
    next_review_due_on TEXT NOT NULL,
    review_cadence_days INTEGER NOT NULL,
    review_triggers TEXT NOT NULL,
    stop_conditions TEXT NOT NULL,
    stop_conditions_met TEXT NOT NULL,
    evidence_fingerprint TEXT NOT NULL,
    evidence_components TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_lifecycle_events (
    event_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decision_records (decision_id),
    event_kind TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    reason_code TEXT NOT NULL,
    reason TEXT NOT NULL,
    details TEXT NOT NULL,
    actor TEXT NOT NULL,
    actor_role TEXT,
    actor_auth_provider TEXT NOT NULL,
    actor_authenticated INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_lifecycle_events_decision
    ON decision_lifecycle_events (decision_id, occurred_at);
