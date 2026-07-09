-- 0011_infra_energy_marts: mart tables for the domain-marts-fillout infra track.
-- mart_energy_daily (utilities), mart_cluster_utilization, mart_uptime_summary,
-- and mart_infra_cost (infrastructure). Rebuilt via DELETE + INSERT on refresh.

CREATE TABLE IF NOT EXISTS mart_energy_daily (
    usage_day DATE NOT NULL,
    utility_type VARCHAR NOT NULL,
    meter_id VARCHAR NOT NULL,
    meter_name VARCHAR NOT NULL,
    total_quantity DECIMAL(18,4) NOT NULL,
    usage_unit VARCHAR,
    reading_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_cluster_utilization (
    period_day DATE NOT NULL,
    hostname VARCHAR NOT NULL,
    node_name VARCHAR,
    resource_type VARCHAR NOT NULL,
    avg_value DECIMAL(18,4),
    max_value DECIMAL(18,4),
    metric_unit VARCHAR,
    sample_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_uptime_summary (
    period_month VARCHAR NOT NULL,
    subject_type VARCHAR NOT NULL,
    subject_id VARCHAR NOT NULL,
    subject_name VARCHAR,
    availability_pct DECIMAL(6,3) NOT NULL,
    up_samples INTEGER NOT NULL,
    total_samples INTEGER NOT NULL,
    first_observed_at TIMESTAMP,
    last_observed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mart_infra_cost (
    billing_month VARCHAR NOT NULL,
    cost_type VARCHAR NOT NULL,
    subject_id VARCHAR NOT NULL,
    subject_name VARCHAR,
    est_kwh DECIMAL(18,4),
    unit_price DECIMAL(18,4),
    currency VARCHAR,
    est_cost DECIMAL(18,4),
    cost_basis VARCHAR NOT NULL
);
