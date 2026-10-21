-- 0024_decision_record_decided_at: retrospective decision entry (HLA-K03).
-- Postgres port of sqlite migration 0015_decision_record_decided_at. NULL
-- decided_at means decided when recorded, so existing rows keep their meaning.

ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;
ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS retrospective_basis TEXT;
