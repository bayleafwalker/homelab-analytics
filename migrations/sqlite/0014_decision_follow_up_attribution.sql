-- 0014_decision_follow_up_attribution: attribution review on follow-ups (HLA-K03)
-- and operator attention capture (HLA-K04). A follow-up keeps the measured
-- result apart from an estimated baseline, and records the attribution
-- hypothesis, confounders, uncertainty and missing evidence. Every column is
-- nullable (lists default to empty): rows written before this migration read
-- back as "not recorded", never as zero. Rows stay append-only.
-- Mirrored in the inline bootstrap (sqlite_control_plane_schema.py).

ALTER TABLE decision_follow_ups ADD COLUMN estimated_baseline_eur TEXT;
ALTER TABLE decision_follow_ups ADD COLUMN estimated_baseline_basis TEXT;
ALTER TABLE decision_follow_ups ADD COLUMN attribution_hypothesis TEXT;
ALTER TABLE decision_follow_ups ADD COLUMN confounders TEXT NOT NULL DEFAULT '[]';
ALTER TABLE decision_follow_ups ADD COLUMN attribution_uncertainty TEXT;
ALTER TABLE decision_follow_ups ADD COLUMN missing_evidence TEXT NOT NULL DEFAULT '[]';
ALTER TABLE decision_follow_ups ADD COLUMN attention_minutes INTEGER;
