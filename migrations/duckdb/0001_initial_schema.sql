-- 0001_initial_schema: full DuckDB warehouse schema
-- Generated from Python model constants. Every statement uses
-- CREATE TABLE IF NOT EXISTS for idempotency against existing databases.

-- ===========================================================================
-- SCD Type 2 dimensions
-- ===========================================================================

-- Transaction domain
CREATE TABLE IF NOT EXISTS dim_account (
    sk VARCHAR PRIMARY KEY,
    account_id VARCHAR NOT NULL,
    currency VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_counterparty (
    sk VARCHAR PRIMARY KEY,
    counterparty_name VARCHAR NOT NULL,
    category VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

-- Subscription domain
CREATE TABLE IF NOT EXISTS dim_category (
    sk VARCHAR PRIMARY KEY,
    category_id VARCHAR NOT NULL,
    display_name VARCHAR,
    parent_id VARCHAR,
    domain VARCHAR,
    is_budget_eligible BOOLEAN,
    is_system BOOLEAN,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_contract (
    sk VARCHAR PRIMARY KEY,
    contract_id VARCHAR NOT NULL,
    contract_name VARCHAR,
    provider VARCHAR,
    contract_type VARCHAR,
    currency VARCHAR,
    start_date DATE,
    end_date DATE,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

-- Utility domain
CREATE TABLE IF NOT EXISTS dim_meter (
    sk VARCHAR PRIMARY KEY,
    meter_id VARCHAR NOT NULL,
    meter_name VARCHAR,
    utility_type VARCHAR,
    location VARCHAR,
    default_unit VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

-- Budget domain
CREATE TABLE IF NOT EXISTS dim_budget (
    sk VARCHAR PRIMARY KEY,
    budget_id VARCHAR NOT NULL,
    budget_name VARCHAR,
    category_id VARCHAR,
    period_type VARCHAR,
    currency VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

-- Loan domain
CREATE TABLE IF NOT EXISTS dim_loan (
    sk VARCHAR PRIMARY KEY,
    loan_id VARCHAR NOT NULL,
    loan_name VARCHAR,
    lender VARCHAR,
    loan_type VARCHAR,
    currency VARCHAR,
    principal DECIMAL(18,4),
    annual_rate DECIMAL(18,6),
    term_months INTEGER,
    start_date DATE,
    payment_frequency VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

-- Homelab domain
CREATE TABLE IF NOT EXISTS dim_service (
    sk VARCHAR PRIMARY KEY,
    service_id VARCHAR NOT NULL,
    service_name VARCHAR,
    service_type VARCHAR,
    host VARCHAR,
    criticality VARCHAR,
    managed_by VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_workload (
    sk VARCHAR PRIMARY KEY,
    workload_id VARCHAR NOT NULL,
    entity_id VARCHAR,
    display_name VARCHAR,
    host VARCHAR,
    workload_type VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL,
    source_system VARCHAR,
    source_run_id VARCHAR
);

-- ===========================================================================
-- Fact and mart tables
-- ===========================================================================

-- Immutable evidence + entity layer
CREATE TABLE IF NOT EXISTS ingest_batch (
    batch_id VARCHAR PRIMARY KEY,
    run_id VARCHAR,
    source_asset_id VARCHAR,
    file_sha256 VARCHAR,
    row_count INTEGER NOT NULL,
    landed_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS transaction_observation (
    observation_id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL,
    row_ordinal INTEGER NOT NULL,
    entity_key VARCHAR,
    match_tier INTEGER,
    confidence DECIMAL(5,4),
    booked_at DATE NOT NULL,
    account_id VARCHAR NOT NULL,
    counterparty_name VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    description VARCHAR,
    normalized_row_json VARCHAR NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS transaction_entity (
    entity_key VARCHAR PRIMARY KEY,
    status VARCHAR NOT NULL DEFAULT 'active',
    first_seen_batch_id VARCHAR NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_batch_id VARCHAR NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    observation_count INTEGER NOT NULL DEFAULT 1,
    current_observation_id VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_transaction_current (
    entity_key VARCHAR PRIMARY KEY,
    current_observation_id VARCHAR NOT NULL,
    booked_at DATE NOT NULL,
    booked_at_utc TIMESTAMPTZ NOT NULL,
    booking_month VARCHAR NOT NULL,
    account_id VARCHAR NOT NULL,
    counterparty_name VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    normalized_currency VARCHAR NOT NULL,
    description VARCHAR,
    direction VARCHAR NOT NULL,
    run_id VARCHAR,
    reconciled_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_balance_snapshot (
    snapshot_id VARCHAR PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    balance_kind VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    entity_label VARCHAR,
    balance_amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    run_id VARCHAR
);


-- Transaction domain
CREATE TABLE IF NOT EXISTS fact_transaction (
    transaction_id VARCHAR PRIMARY KEY,
    booked_at DATE NOT NULL,
    booked_at_utc TIMESTAMPTZ NOT NULL,
    booking_month VARCHAR NOT NULL,
    account_id VARCHAR NOT NULL,
    counterparty_name VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    normalized_currency VARCHAR NOT NULL,
    description VARCHAR,
    direction VARCHAR NOT NULL,
    run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_monthly_cashflow (
    booking_month VARCHAR NOT NULL,
    income DECIMAL(18,4) NOT NULL,
    expense DECIMAL(18,4) NOT NULL,
    net DECIMAL(18,4) NOT NULL,
    transaction_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_monthly_cashflow_by_counterparty (
    booking_month VARCHAR NOT NULL,
    counterparty_name VARCHAR NOT NULL,
    income DECIMAL(18,4) NOT NULL,
    expense DECIMAL(18,4) NOT NULL,
    net DECIMAL(18,4) NOT NULL,
    transaction_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_spend_by_category_monthly (
    booking_month VARCHAR NOT NULL,
    counterparty_name VARCHAR NOT NULL,
    category VARCHAR,
    total_expense DECIMAL(18,4) NOT NULL,
    transaction_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_recent_large_transactions (
    transaction_id VARCHAR NOT NULL,
    booked_at DATE NOT NULL,
    booking_month VARCHAR NOT NULL,
    account_id VARCHAR NOT NULL,
    counterparty_name VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    description VARCHAR,
    direction VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_account_balance_trend (
    booking_month VARCHAR NOT NULL,
    account_id VARCHAR NOT NULL,
    net_change DECIMAL(18,4) NOT NULL,
    cumulative_balance DECIMAL(18,4) NOT NULL,
    transaction_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_transaction_anomalies_current (
    transaction_id VARCHAR NOT NULL,
    booking_date DATE NOT NULL,
    counterparty_name VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    direction VARCHAR NOT NULL,
    anomaly_type VARCHAR NOT NULL,
    anomaly_reason VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS transformation_audit (
    audit_id VARCHAR PRIMARY KEY,
    input_run_id VARCHAR,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    duration_ms INTEGER NOT NULL,
    fact_rows INTEGER NOT NULL,
    accounts_upserted INTEGER NOT NULL,
    counterparties_upserted INTEGER NOT NULL
);


-- Budget domain
CREATE TABLE IF NOT EXISTS fact_budget_target (
    target_id VARCHAR PRIMARY KEY,
    budget_id VARCHAR NOT NULL,
    budget_name VARCHAR NOT NULL,
    category_id VARCHAR NOT NULL,
    period_type VARCHAR NOT NULL,
    period_label VARCHAR NOT NULL,
    target_amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_budget_variance (
    budget_name VARCHAR NOT NULL,
    category_id VARCHAR NOT NULL,
    period_label VARCHAR NOT NULL,
    target_amount DECIMAL(18,4) NOT NULL,
    actual_amount DECIMAL(18,4) NOT NULL,
    variance DECIMAL(18,4) NOT NULL,
    variance_pct DECIMAL(18,4),
    status VARCHAR NOT NULL,
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_budget_progress_current (
    budget_name VARCHAR NOT NULL,
    category_id VARCHAR NOT NULL,
    target_amount DECIMAL(18,4) NOT NULL,
    spent_amount DECIMAL(18,4) NOT NULL,
    remaining DECIMAL(18,4) NOT NULL,
    utilization_pct DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL
);


-- Subscription domain
CREATE TABLE IF NOT EXISTS fact_subscription_charge (
    charge_id VARCHAR PRIMARY KEY,
    contract_id VARCHAR NOT NULL,
    contract_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    billing_cycle VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_subscription_summary (
    contract_id VARCHAR NOT NULL,
    contract_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    billing_cycle VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    monthly_equivalent DECIMAL(18,4) NOT NULL,
    status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_upcoming_fixed_costs_30d (
    contract_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    frequency VARCHAR NOT NULL,
    expected_amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    expected_date DATE NOT NULL,
    confidence VARCHAR NOT NULL
);


-- Contract price domain
CREATE TABLE IF NOT EXISTS fact_contract_price (
    price_id VARCHAR PRIMARY KEY,
    contract_id VARCHAR NOT NULL,
    contract_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    contract_type VARCHAR NOT NULL,
    price_component VARCHAR NOT NULL,
    billing_cycle VARCHAR NOT NULL,
    unit_price DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    quantity_unit VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE,
    run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_contract_price_current (
    contract_id VARCHAR NOT NULL,
    contract_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    contract_type VARCHAR NOT NULL,
    price_component VARCHAR NOT NULL,
    billing_cycle VARCHAR NOT NULL,
    unit_price DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    quantity_unit VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE,
    status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_electricity_price_current (
    contract_id VARCHAR NOT NULL,
    contract_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    contract_type VARCHAR NOT NULL,
    price_component VARCHAR NOT NULL,
    billing_cycle VARCHAR NOT NULL,
    unit_price DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    quantity_unit VARCHAR,
    valid_from DATE NOT NULL,
    valid_to DATE,
    status VARCHAR NOT NULL
);


-- Utility domain
CREATE TABLE IF NOT EXISTS fact_utility_usage (
    usage_id VARCHAR PRIMARY KEY,
    meter_id VARCHAR NOT NULL,
    meter_name VARCHAR NOT NULL,
    utility_type VARCHAR NOT NULL,
    usage_start DATE NOT NULL,
    usage_end DATE NOT NULL,
    usage_quantity DECIMAL(18,4) NOT NULL,
    usage_unit VARCHAR NOT NULL,
    reading_source VARCHAR,
    run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_bill (
    bill_id VARCHAR PRIMARY KEY,
    meter_id VARCHAR NOT NULL,
    meter_name VARCHAR NOT NULL,
    provider VARCHAR,
    utility_type VARCHAR NOT NULL,
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    billed_amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    billed_quantity DECIMAL(18,4),
    usage_unit VARCHAR,
    invoice_date DATE,
    run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_utility_cost_summary (
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_day DATE NOT NULL,
    period_month VARCHAR NOT NULL,
    meter_id VARCHAR NOT NULL,
    meter_name VARCHAR NOT NULL,
    utility_type VARCHAR NOT NULL,
    usage_quantity DECIMAL(18,4) NOT NULL,
    usage_unit VARCHAR,
    billed_amount DECIMAL(18,4) NOT NULL,
    currency VARCHAR,
    unit_cost DECIMAL(18,4),
    bill_count INTEGER NOT NULL,
    usage_record_count INTEGER NOT NULL,
    coverage_status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_utility_cost_trend_monthly (
    billing_month VARCHAR NOT NULL,
    utility_type VARCHAR NOT NULL,
    total_cost DECIMAL(18,4) NOT NULL,
    usage_amount DECIMAL(18,4) NOT NULL,
    unit_price_effective DECIMAL(18,4),
    currency VARCHAR,
    meter_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_usage_vs_price_summary (
    utility_type VARCHAR NOT NULL,
    period VARCHAR NOT NULL,
    usage_change_pct DECIMAL(18,4),
    price_change_pct DECIMAL(18,4),
    cost_change_pct DECIMAL(18,4),
    dominant_driver VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_contract_review_candidates (
    contract_id VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    utility_type VARCHAR NOT NULL,
    reason VARCHAR NOT NULL,
    score INTEGER NOT NULL,
    current_price DECIMAL(18,4) NOT NULL,
    market_reference DECIMAL(18,4),
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_contract_renewal_watchlist (
    contract_id VARCHAR NOT NULL,
    contract_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    utility_type VARCHAR NOT NULL,
    renewal_date DATE NOT NULL,
    days_until_renewal INTEGER NOT NULL,
    current_price DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    contract_duration_days INTEGER
);


-- Loan domain
CREATE TABLE IF NOT EXISTS fact_loan_repayment (
    repayment_id VARCHAR PRIMARY KEY,
    loan_id VARCHAR NOT NULL,
    repayment_date DATE NOT NULL,
    repayment_month VARCHAR NOT NULL,
    payment_amount DECIMAL(18,4) NOT NULL,
    principal_portion DECIMAL(18,4),
    interest_portion DECIMAL(18,4),
    extra_amount DECIMAL(18,4),
    currency VARCHAR NOT NULL,
    run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_loan_schedule_projected (
    loan_id VARCHAR NOT NULL,
    loan_name VARCHAR NOT NULL,
    period INTEGER NOT NULL,
    payment_date DATE NOT NULL,
    payment DECIMAL(18,4) NOT NULL,
    principal_portion DECIMAL(18,4) NOT NULL,
    interest_portion DECIMAL(18,4) NOT NULL,
    remaining_balance DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_loan_repayment_variance (
    loan_id VARCHAR NOT NULL,
    loan_name VARCHAR NOT NULL,
    repayment_month VARCHAR NOT NULL,
    projected_payment DECIMAL(18,4) NOT NULL,
    actual_payment DECIMAL(18,4) NOT NULL,
    variance DECIMAL(18,4) NOT NULL,
    projected_balance DECIMAL(18,4) NOT NULL,
    actual_balance_estimate DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_loan_overview (
    loan_id VARCHAR NOT NULL,
    loan_name VARCHAR NOT NULL,
    lender VARCHAR NOT NULL,
    original_principal DECIMAL(18,4) NOT NULL,
    current_balance_estimate DECIMAL(18,4) NOT NULL,
    monthly_payment DECIMAL(18,4) NOT NULL,
    total_interest_projected DECIMAL(18,4) NOT NULL,
    total_interest_paid DECIMAL(18,4) NOT NULL,
    remaining_months INTEGER NOT NULL,
    currency VARCHAR NOT NULL
);


-- Homelab domain
CREATE TABLE IF NOT EXISTS fact_service_health (
    health_id VARCHAR PRIMARY KEY,
    run_id VARCHAR,
    service_id VARCHAR NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    state VARCHAR NOT NULL,
    uptime_seconds BIGINT,
    last_state_change TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_backup_run (
    backup_id VARCHAR PRIMARY KEY,
    run_id VARCHAR,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_s INTEGER,
    size_bytes BIGINT,
    target VARCHAR NOT NULL,
    status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_storage_sensor (
    sensor_id VARCHAR PRIMARY KEY,
    run_id VARCHAR,
    entity_id VARCHAR NOT NULL,
    device_name VARCHAR NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    capacity_bytes BIGINT NOT NULL,
    used_bytes BIGINT NOT NULL,
    sensor_type VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_workload_sensor (
    reading_id VARCHAR PRIMARY KEY,
    run_id VARCHAR,
    workload_id VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    cpu_pct DECIMAL(6,3),
    mem_bytes BIGINT
);

CREATE TABLE IF NOT EXISTS mart_service_health_current (
    service_id VARCHAR NOT NULL,
    service_name VARCHAR,
    service_type VARCHAR,
    host VARCHAR,
    criticality VARCHAR,
    managed_by VARCHAR,
    state VARCHAR NOT NULL,
    uptime_seconds BIGINT,
    last_state_change TIMESTAMP,
    recorded_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_backup_freshness (
    target VARCHAR NOT NULL,
    last_backup_at TIMESTAMP,
    last_status VARCHAR,
    last_size_bytes BIGINT,
    hours_since_backup DECIMAL(10,2),
    is_stale BOOLEAN NOT NULL,
    backup_count_7d INTEGER
);

CREATE TABLE IF NOT EXISTS mart_storage_risk (
    entity_id VARCHAR NOT NULL,
    device_name VARCHAR NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    capacity_bytes BIGINT NOT NULL,
    used_bytes BIGINT NOT NULL,
    free_bytes BIGINT NOT NULL,
    pct_used DECIMAL(6,3) NOT NULL,
    risk_tier VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_workload_cost_7d (
    workload_id VARCHAR NOT NULL,
    display_name VARCHAR,
    host VARCHAR,
    workload_type VARCHAR,
    avg_cpu_pct_7d DECIMAL(6,3),
    avg_mem_gb_7d DECIMAL(10,4),
    reading_count_7d INTEGER,
    est_monthly_cost DECIMAL(10,4)
);


-- HA Integration Hub
CREATE TABLE IF NOT EXISTS dim_ha_entity (
    entity_id VARCHAR PRIMARY KEY,
    canonical_id VARCHAR NOT NULL,
    entity_class VARCHAR NOT NULL,
    friendly_name VARCHAR,
    area VARCHAR,
    unit VARCHAR,
    last_seen VARCHAR,
    last_state VARCHAR,
    source_system VARCHAR,
    ingested_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_ha_state_change (
    entity_id VARCHAR NOT NULL,
    canonical_id VARCHAR NOT NULL,
    state VARCHAR NOT NULL,
    attributes VARCHAR,
    changed_at VARCHAR NOT NULL,
    ingested_at VARCHAR NOT NULL,
    run_id VARCHAR
);


-- Scenario domain
CREATE TABLE IF NOT EXISTS dim_scenario (
    scenario_id VARCHAR NOT NULL,
    scenario_type VARCHAR NOT NULL,
    subject_id VARCHAR NOT NULL,
    label VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    baseline_run_id VARCHAR,
    created_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_scenario_assumption (
    scenario_id VARCHAR NOT NULL,
    assumption_key VARCHAR NOT NULL,
    baseline_value VARCHAR,
    override_value VARCHAR NOT NULL,
    unit VARCHAR
);

CREATE TABLE IF NOT EXISTS proj_loan_schedule (
    scenario_id VARCHAR NOT NULL,
    loan_id VARCHAR NOT NULL,
    loan_name VARCHAR NOT NULL,
    period INTEGER NOT NULL,
    payment_date DATE NOT NULL,
    payment DECIMAL(18,4) NOT NULL,
    principal_portion DECIMAL(18,4) NOT NULL,
    interest_portion DECIMAL(18,4) NOT NULL,
    extra_repayment DECIMAL(18,4) NOT NULL,
    remaining_balance DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS proj_loan_repayment_variance (
    scenario_id VARCHAR NOT NULL,
    loan_id VARCHAR NOT NULL,
    period INTEGER NOT NULL,
    payment_date DATE NOT NULL,
    baseline_payment DECIMAL(18,4),
    scenario_payment DECIMAL(18,4) NOT NULL,
    baseline_balance DECIMAL(18,4),
    scenario_balance DECIMAL(18,4) NOT NULL,
    payment_delta DECIMAL(18,4),
    balance_delta DECIMAL(18,4),
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS proj_income_cashflow (
    scenario_id VARCHAR NOT NULL,
    period INTEGER NOT NULL,
    projected_month VARCHAR NOT NULL,
    baseline_income DECIMAL(18,4) NOT NULL,
    scenario_income DECIMAL(18,4) NOT NULL,
    baseline_expense DECIMAL(18,4) NOT NULL,
    scenario_expense DECIMAL(18,4) NOT NULL,
    baseline_net DECIMAL(18,4) NOT NULL,
    scenario_net DECIMAL(18,4) NOT NULL,
    net_delta DECIMAL(18,4) NOT NULL
);


-- Overview composition layer
CREATE TABLE IF NOT EXISTS mart_household_overview (
    current_month VARCHAR NOT NULL,
    cashflow_income DECIMAL(18,4) NOT NULL,
    cashflow_expense DECIMAL(18,4) NOT NULL,
    cashflow_net DECIMAL(18,4) NOT NULL,
    utility_cost_total DECIMAL(18,4) NOT NULL,
    subscription_total_monthly DECIMAL(18,4) NOT NULL,
    account_balance_direction VARCHAR NOT NULL,
    balance_net_change DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_open_attention_items (
    item_id VARCHAR NOT NULL,
    item_type VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    detail VARCHAR NOT NULL,
    severity INTEGER NOT NULL,
    source_domain VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_recent_significant_changes (
    change_type VARCHAR NOT NULL,
    period VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    current_value DECIMAL(18,4) NOT NULL,
    previous_value DECIMAL(18,4) NOT NULL,
    change_pct DECIMAL(18,4),
    direction VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_current_operating_baseline (
    baseline_type VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    value DECIMAL(18,4) NOT NULL,
    period_label VARCHAR NOT NULL,
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_household_cost_model (
    period_label VARCHAR NOT NULL,
    cost_type VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    source_domain VARCHAR NOT NULL,
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_cost_trend_12m (
    period_label VARCHAR NOT NULL,
    cost_type VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    prev_amount DECIMAL(18,4),
    change_pct DECIMAL(18,4),
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_affordability_ratios (
    ratio_name VARCHAR NOT NULL,
    numerator DECIMAL(18,4) NOT NULL,
    denominator DECIMAL(18,4) NOT NULL,
    ratio DECIMAL(18,6) NOT NULL,
    period_label VARCHAR NOT NULL,
    assessment VARCHAR NOT NULL,
    currency VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_recurring_cost_baseline (
    cost_source VARCHAR NOT NULL,
    counterparty_or_contract VARCHAR NOT NULL,
    monthly_amount DECIMAL(18,4) NOT NULL,
    confidence VARCHAR NOT NULL,
    last_occurrence VARCHAR,
    currency VARCHAR NOT NULL
);


-- Category governance
CREATE TABLE IF NOT EXISTS category_rule (
    rule_id VARCHAR PRIMARY KEY,
    pattern VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    priority INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS category_override (
    counterparty_name VARCHAR PRIMARY KEY,
    category VARCHAR NOT NULL
);
