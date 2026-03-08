# Storage Package

Object storage, DuckDB, Parquet, and Postgres access abstractions.

Current foundation:

- local landing-store ingestion for raw CSV copies and manifest output
- SQL-backed ingestion run metadata persistence for local development and future worker integration
- explicit blob-store and metadata-store abstractions with filesystem and SQLite implementations as the current default backends
- persisted ingestion configuration entities for source systems, dataset contracts, and column mappings
- persisted source assets and ingestion definitions for config-driven folder and HTTP pull execution, including request headers and timeout settings
