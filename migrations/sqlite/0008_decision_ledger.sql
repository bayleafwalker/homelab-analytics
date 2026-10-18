-- 0008_decision_ledger: append-only household decision ledger.
-- decision_records pin a declared decision (key + version) to the exact
-- subject publication row (publication key, schema version, period, row ref)
-- and a lineage reference, with the outcome or explicit non-decision,
-- rationale, acknowledged evidence gaps and the acting identity.
-- decision_follow_ups record later observed results. Rows are never updated.

CREATE TABLE IF NOT EXISTS decision_records (
    decision_id TEXT PRIMARY KEY,
    decision_key TEXT NOT NULL,
    decision_version TEXT NOT NULL,
    subject_publication_key TEXT NOT NULL,
    subject_schema_version TEXT NOT NULL,
    subject_period TEXT NOT NULL,
    subject_row_ref TEXT NOT NULL,
    subject_verdict TEXT NOT NULL,
    lineage_reference TEXT NOT NULL,
    evidence_snapshot TEXT NOT NULL,
    outcome TEXT NOT NULL,
    is_non_decision INTEGER NOT NULL,
    rationale TEXT NOT NULL,
    evidence_gaps_acknowledged TEXT NOT NULL,
    uncertainty TEXT,
    actor TEXT NOT NULL,
    actor_role TEXT,
    actor_auth_provider TEXT NOT NULL,
    actor_authenticated INTEGER NOT NULL,
    follow_up_due_on TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_records_key_period
    ON decision_records (decision_key, subject_period);

CREATE TABLE IF NOT EXISTS decision_follow_ups (
    follow_up_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decision_records (decision_id),
    observed_at TEXT NOT NULL,
    observation_period TEXT,
    realized_result TEXT NOT NULL,
    realized_value_eur TEXT,
    realized_value_status TEXT,
    evidence_effect TEXT NOT NULL,
    notes TEXT,
    actor TEXT NOT NULL,
    actor_role TEXT,
    actor_auth_provider TEXT NOT NULL,
    actor_authenticated INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_follow_ups_decision
    ON decision_follow_ups (decision_id, observed_at);
