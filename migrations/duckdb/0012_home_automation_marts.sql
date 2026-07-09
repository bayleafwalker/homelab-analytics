-- 0012_home_automation_marts: mart tables for the domain-marts-fillout
-- home-automation track. mart_climate_summary, mart_automation_reliability,
-- and mart_device_battery. Rebuilt via DELETE + INSERT on refresh.

CREATE TABLE IF NOT EXISTS mart_climate_summary (
    period_day DATE NOT NULL,
    area VARCHAR NOT NULL,
    measure VARCHAR NOT NULL,
    avg_value DECIMAL(18,4) NOT NULL,
    min_value DECIMAL(18,4) NOT NULL,
    max_value DECIMAL(18,4) NOT NULL,
    unit VARCHAR,
    reading_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_automation_reliability (
    period_month VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    entity_name VARCHAR,
    run_count INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    failure_count INTEGER NOT NULL,
    success_rate_pct DECIMAL(6,3) NOT NULL,
    last_run_at TIMESTAMP,
    last_result VARCHAR
);

CREATE TABLE IF NOT EXISTS mart_device_battery (
    entity_id VARCHAR NOT NULL,
    entity_name VARCHAR,
    device_name VARCHAR,
    area VARCHAR,
    battery_pct DECIMAL(6,2) NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    avg_daily_drain_pct DECIMAL(10,4),
    est_days_to_empty INTEGER,
    battery_status VARCHAR NOT NULL
);
