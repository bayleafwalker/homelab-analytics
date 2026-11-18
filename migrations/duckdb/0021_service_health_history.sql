-- Latest recorded health state per service in each observed ingestion batch.
CREATE TABLE IF NOT EXISTS mart_service_health_history (
    run_id VARCHAR NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    service_id VARCHAR NOT NULL,
    state VARCHAR NOT NULL
);
