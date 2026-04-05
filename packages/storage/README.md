# Storage Package

Object storage, DuckDB, Parquet, and Postgres access abstractions.

Support model:

- Postgres is the canonical operational store for control-plane state, landing metadata, run metadata, and published reporting.
- SQLite is retained only for local bootstrap, smoke tests, and snapshot portability.
- DuckDB remains the warehouse engine for transformation and local analytical work.

Schema evolution ownership:

- Postgres control-plane schema changes are tracked in `migrations/postgres`.
- Postgres run-metadata schema changes are tracked in `migrations/postgres_run_metadata`.
- SQLite schema/bootstrap helpers remain a local compatibility path for developer bootstrap and smoke coverage; they are best-effort, not a parity commitment.
- DuckDB schema migrations stay isolated to `migrations/duckdb` for warehouse concerns.

Current foundation:

- local landing-store ingestion for raw CSV copies and manifest output
- SQL-backed ingestion run metadata persistence for local development and shared-deployment operation
- explicit blob-store abstractions with filesystem and S3-compatible implementations
- Postgres-backed control-plane, run-metadata, and publication-storage adapters for the canonical operational path
- SQLite control-plane and metadata adapters retained for local bootstrap and compatibility flows
- Postgres-backed publication storage for reporting marts and current-dimension snapshots
- DuckDB-backed warehouse persistence for transformation-layer facts, dimensions, and analytical workloads
- persisted ingestion configuration entities for source systems, dataset contracts, and column mappings
- backend-specific source/contract catalog modules for both the canonical Postgres control plane and the retained SQLite fallback
- backend-specific asset/definition catalog modules for both the canonical Postgres control plane and the retained SQLite fallback
- backend-specific execution control-plane modules for both the canonical Postgres control plane and the retained SQLite fallback
- backend-specific provenance control-plane modules for both the canonical Postgres control plane and the retained SQLite fallback
- backend-specific auth control-plane modules for both the canonical Postgres control plane and the retained SQLite fallback
- SQLite control-plane schema bootstrap compatibility shim for retained local fallback support
- backend-neutral control-plane snapshot export/import helpers that replay shared catalog, execution, provenance, and auth state across SQLite and Postgres repositories where practical
- backend-neutral ingestion catalog models plus shared serialization, publication-validation, and built-in package seed helpers used by both control-plane repositories
- persisted source assets and ingestion definitions for config-driven folder and HTTP pull execution, including request headers and timeout settings
- aggregate-scoped control-plane protocols shared across the canonical Postgres path and the retained SQLite bootstrap fallback
