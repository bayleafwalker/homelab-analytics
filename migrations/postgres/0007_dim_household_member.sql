-- 0007_dim_household_member: Stage 1 carryover — canonical household-member dimension
-- Postgres control-plane companion to the DuckDB warehouse table.
-- Used for operator-managed member configuration; DuckDB holds the analytical projection.

CREATE TABLE IF NOT EXISTS dim_household_member (
    sk TEXT PRIMARY KEY,
    member_id TEXT NOT NULL UNIQUE,
    display_name TEXT,
    role TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system TEXT,
    source_run_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_household_member_member_id
    ON dim_household_member (member_id);
