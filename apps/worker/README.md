# Worker App

Batch execution runtime for ingestion, validation, transformation, and publication jobs.

Current foundation:

- account-transaction ingestion service that orchestrates landing, metadata persistence, and report generation inputs
- runnable CLI entrypoint in `python -m apps.worker.main`
- parser, runtime/environment builders, command handlers, and control-plane execution helpers are now split into dedicated worker modules instead of one monolithic CLI file
- watched-folder polling commands for `process-account-transactions-inbox` and `watch-account-transactions-inbox`, now backed by a bootstrap config-driven ingestion definition for compatibility
- successful manual and configured built-in ingests auto-promote through the shared promotion flow when the analytics store is configured
- source-asset processing resolves transformation packages and publication definitions from persisted configuration
- subscription and contract-price domains have first-class ingest and report commands
- `promote-run` is retry-safe and refreshes marts without duplicating already promoted fact rows
