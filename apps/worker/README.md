# Worker App

Batch execution runtime for ingestion, validation, transformation, and publication jobs.

Current foundation:

- account-transaction ingestion service that orchestrates landing, metadata persistence, and report generation inputs
- runnable CLI entrypoint in `python -m apps.worker.main`
- parser, runtime/environment builders, command handlers, and control-plane execution helpers are now split into dedicated worker modules instead of one monolithic CLI file
- watched-folder polling commands for `process-account-transactions-inbox` and `watch-account-transactions-inbox`, now backed by a bootstrap config-driven ingestion definition for compatibility
- successful manual and configured built-in ingests auto-promote through the shared promotion flow when the analytics store is configured
- source-asset processing resolves transformation packages and publication definitions from persisted configuration
- extension-registry CLI commands cover source lifecycle, discovered handler/publication/function listing, and archived-aware transformation-package/publication-definition catalog inspection
- subscription and contract-price domains have first-class ingest and report commands
- `refresh-battery-plan-outcome` assesses the Kotiakku battery-plan decision from Home Assistant history (profile from `HOMELAB_ANALYTICS_BATTERY_PLAN_PROFILE`), rebuilds `mart_battery_plan_outcome` and `mart_battery_plan_outcome_values`, publishes them, and records reporting lineage from the source ingest runs; it is read-only toward the battery
- `promote-run` is retry-safe and refreshes marts without duplicating already promoted fact rows
- `backup`, `verify-backup`, and `restore` produce and restore a checksummed bundle of the SQLite control plane, DuckDB warehouse, and filesystem landing payloads; they run before the runtime is built and refuse checksum/schema mismatches or non-empty targets without `--force` (see `docs/runbooks/backup-and-restore.md`)
