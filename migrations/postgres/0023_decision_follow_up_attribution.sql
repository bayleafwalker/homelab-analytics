-- 0023_decision_follow_up_attribution: attribution review on follow-ups (HLA-K03)
-- and operator attention capture (HLA-K04). Postgres port of sqlite migration
-- 0014_decision_follow_up_attribution. Every column is nullable (lists default
-- to empty): rows written before this migration read back as "not recorded",
-- never as zero. Rows stay append-only.

ALTER TABLE decision_follow_ups ADD COLUMN IF NOT EXISTS estimated_baseline_eur NUMERIC(18,4);
ALTER TABLE decision_follow_ups ADD COLUMN IF NOT EXISTS estimated_baseline_basis TEXT;
ALTER TABLE decision_follow_ups ADD COLUMN IF NOT EXISTS attribution_hypothesis TEXT;
ALTER TABLE decision_follow_ups ADD COLUMN IF NOT EXISTS confounders TEXT NOT NULL DEFAULT '[]';
ALTER TABLE decision_follow_ups ADD COLUMN IF NOT EXISTS attribution_uncertainty TEXT;
ALTER TABLE decision_follow_ups ADD COLUMN IF NOT EXISTS missing_evidence TEXT NOT NULL DEFAULT '[]';
ALTER TABLE decision_follow_ups ADD COLUMN IF NOT EXISTS attention_minutes INTEGER;
