-- 0015_decision_record_decided_at: retrospective decision entry (HLA-K03).
-- decided_at is when the household actually decided, when that is earlier
-- than the recording time (created_at); retrospective_basis names the record
-- that shows it. NULL means decided when recorded, so existing rows keep their
-- meaning. The observation window derives from decided_at when present.
-- Mirrored in the inline bootstrap (sqlite_control_plane_schema.py).

ALTER TABLE decision_records ADD COLUMN decided_at TEXT;
ALTER TABLE decision_records ADD COLUMN retrospective_basis TEXT;
