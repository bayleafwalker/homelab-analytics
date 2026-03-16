# Storage Package

Object storage, DuckDB, Parquet, and Postgres access abstractions.

Current foundation:

- local landing-store ingestion for raw CSV copies and manifest output
- SQL-backed ingestion run metadata persistence for local development and future worker integration
- explicit blob-store and metadata-store abstractions with filesystem and SQLite implementations as the current default backends
- production-oriented adapter scaffolding for S3-compatible blob storage and Postgres-backed run metadata
- Postgres-backed publication storage for reporting marts and current-dimension snapshots
- persisted ingestion configuration entities for source systems, dataset contracts, and column mappings
- SQLite and Postgres config backends now split source-system, contract, mapping, transformation-package, and publication-definition persistence into backend-specific source/contract catalog modules
- SQLite and Postgres config backends now split source-asset and ingestion-definition persistence into backend-specific asset/definition catalog modules
- SQLite and Postgres config backends now split execution schedules, schedule dispatches, and worker heartbeat persistence into backend-specific execution control-plane modules
- SQLite and Postgres config backends now split source-lineage and publication-audit persistence into backend-specific provenance control-plane modules
- SQLite and Postgres config backends now split local-user, service-token, and auth-audit persistence into backend-specific auth control-plane modules
- backend-neutral ingestion catalog models plus shared serialization, publication-validation, and built-in package seed helpers used by both SQLite and Postgres config repositories
- persisted source assets and ingestion definitions for config-driven folder and HTTP pull execution, including request headers and timeout settings
- aggregate-scoped control-plane protocols for source registry, contract catalog, asset catalog, scheduling, and audit surfaces shared across SQLite and Postgres backends
