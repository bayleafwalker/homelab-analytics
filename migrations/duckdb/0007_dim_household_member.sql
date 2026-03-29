-- 0007_dim_household_member: Stage 1 carryover — canonical household-member dimension
-- SCD Type 2 table managed via DimensionDefinition (consistent with dim_account, dim_counterparty).
-- A default 'household' member is seeded by the transformation layer on first access.

CREATE TABLE IF NOT EXISTS dim_household_member (
    sk VARCHAR PRIMARY KEY,
    member_id VARCHAR NOT NULL,
    display_name VARCHAR,
    role VARCHAR,
    active BOOLEAN,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

-- Reporting-layer current view (mirrors pattern used by dim_account and dim_counterparty).
CREATE OR REPLACE VIEW rpt_current_dim_household_member AS
SELECT
    sk,
    member_id,
    display_name,
    role,
    active
FROM dim_household_member
WHERE is_current = TRUE;
