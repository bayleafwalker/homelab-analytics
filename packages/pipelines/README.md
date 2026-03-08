# Pipelines Package

Dataset contracts, data quality checks, orchestration logic, and transformation workflows.

Current foundation:

- CSV dataset contract and typed landing validation
- canonical account-transaction transformation from validated CSV data
- DuckDB-backed transaction transformation with UTC timestamp and normalized-currency fields
- config-driven CSV ingestion that resolves persisted dataset contracts and source-to-canonical column mappings at runtime
- config-driven watch-folder processing that resolves source assets and ingestion definitions from persisted config
- config-driven HTTP processing for direct API and batch-extract CSV pulls through the same ingestion-definition runtime path
- reporting-layer current views for implemented SCD dimensions
