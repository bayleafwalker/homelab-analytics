-- 0015_battery_plan_outcome_marts: reporting marts for the household outcome
-- evidence loop (Kotiakku battery-plan decision). mart_battery_plan_outcome
-- holds one verdict row per assessed decision month; the _values mart holds
-- one disclosure row per material value. Timestamps are ISO-8601 strings with
-- an explicit UTC offset. Rebuilt via DELETE + INSERT on refresh.

CREATE TABLE IF NOT EXISTS mart_battery_plan_outcome (
    assessment_id VARCHAR NOT NULL,
    decision_key VARCHAR NOT NULL,
    decision_version VARCHAR NOT NULL,
    decision_month VARCHAR NOT NULL,
    household_timezone VARCHAR,
    assessed_at VARCHAR NOT NULL,
    profile_status VARCHAR NOT NULL,
    evidence_status VARCHAR NOT NULL,
    verdict VARCHAR NOT NULL,
    claim_basis VARCHAR NOT NULL,
    source_recommendation VARCHAR NOT NULL,
    recommendation_scope VARCHAR NOT NULL,
    actuation_authorized BOOLEAN NOT NULL,
    estimated_savings_eur DECIMAL(18,4),
    effective_monthly_cost_eur DECIMAL(18,4),
    estimated_net_benefit_eur DECIMAL(18,4),
    cost_basis_method VARCHAR,
    expected_window_count INTEGER NOT NULL,
    complete_window_count INTEGER NOT NULL,
    missing_window_count INTEGER NOT NULL,
    coverage_pct DECIMAL(9,4) NOT NULL,
    duplicate_snapshot_count INTEGER NOT NULL,
    conflicting_window_count INTEGER NOT NULL,
    invalid_record_count INTEGER NOT NULL,
    unknown_scope_timestamp_count INTEGER NOT NULL,
    backfill_status VARCHAR NOT NULL,
    source_last_period_end VARCHAR,
    freshness_status VARCHAR NOT NULL,
    freshness_age_minutes DECIMAL(18,2),
    freshness_limit_minutes INTEGER NOT NULL,
    tariff_snapshot_id VARCHAR,
    tariff_snapshot_json VARCHAR,
    source_calculation_method VARCHAR,
    source_evidence_contract_version VARCHAR,
    reason_codes_json VARCHAR NOT NULL,
    missing_fields_json VARCHAR NOT NULL,
    remediation VARCHAR,
    limitations_json VARCHAR NOT NULL,
    source_entity_ids_json VARCHAR NOT NULL,
    source_run_ids_json VARCHAR NOT NULL,
    source_report_ingested_at VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_battery_plan_outcome_values (
    assessment_id VARCHAR NOT NULL,
    decision_month VARCHAR NOT NULL,
    display_order INTEGER NOT NULL,
    value_key VARCHAR NOT NULL,
    value_label VARCHAR NOT NULL,
    value_numeric DECIMAL(18,4),
    value_text VARCHAR,
    unit VARCHAR,
    value_status VARCHAR NOT NULL,
    value_role VARCHAR NOT NULL,
    is_missing BOOLEAN NOT NULL,
    source_reference VARCHAR,
    note VARCHAR
);
