# homelab-analytics

Homelab and household analytics platform for ingesting heterogeneous personal datasets, normalizing them into reusable models, and publishing dashboards and APIs from the same core data products.

## Intended scope

The initial target is a single-household, self-hosted platform that can grow from manual imports to scheduled pipelines without rebuilding the architecture. Source classes include:

- file-based imports such as CSV, XLSX, and batch extracts
- watched input folders on NFS or synced folders from OneDrive, Nextcloud, or Google Drive
- direct API ingestion such as utility providers and other authenticated REST endpoints
- financial datasets such as account transactions, card transactions, daily balances, loans, and planned repayments
- internal homelab telemetry such as Prometheus-derived metrics and Home Assistant exports or APIs

Derived outputs include:

- household budget and cost models
- electricity and utility summaries
- loan repayment plans and estimates
- profitability and affordability views
- reusable marts for dashboards, automations, and API consumers

## Repository layout

```text
homelab-analytics/
├── apps/
│   ├── api/
│   ├── worker/
│   └── web/
├── packages/
│   ├── analytics/
│   ├── connectors/
│   ├── pipelines/
│   ├── shared/
│   └── storage/
├── charts/
│   └── homelab-analytics/
├── infra/
│   ├── docker/
│   └── examples/
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── notes/
│   └── plans/
└── tests/
```

## Documentation

- `requirements/` contains the baseline requirements across five domains: data ingestion, data platform, analytics and reporting, application services, and security and operations. Each requirement is phased, status-tracked, and linked to acceptance criteria.
- `docs/README.md` contains the document index for architecture, decisions, plans, and notes.
- `docs/architecture/data-platform-architecture.md` defines the source-to-reporting data architecture.
- `docs/decisions/compute-and-orchestration-options.md` compares Spark and other execution/orchestration options and records the recommended initial path.
- `docs/notes/appservice-cluster-integration-notes.md` captures cluster deployment assumptions.

## Current status

This repository now has a working end-to-end bootstrap aligned to the target architecture:

- the initial runtime/package/chart directory structure exists
- repository-contract tests protect the agreed starting shape
- architecture and decision docs define the first implementation path
- the first landing-layer CSV contract validation module exists with project-specific fixture tests
- a local landing-store flow now copies raw CSV files and writes per-run manifests with validation results
- ingestion run metadata can now be persisted in a small SQL-backed repository for worker/control-plane use
- the first transformation and reporting slice exists for account transactions and monthly cash-flow summaries
- a FastAPI-based API and worker-facing service now expose ingestion runs, config surfaces, and monthly cash-flow reporting
- shared settings and executable `apps/api` and `apps/worker` entrypoints now make the current slice runnable locally
- project metadata, console scripts, and Docker/Compose bootstrap files now make the slice installable and containerizable
- a schedule-dispatch worker loop and a minimal Helm chart now cover the first Kubernetes deployment path
- a Next.js web shell now exposes dashboard, filterable run-monitoring, run-detail drill-down, and control-plane admin views as a separate workload
- the Next.js web shell now also exposes operator-facing browser uploads for built-in datasets plus config-driven source-asset uploads that redirect into run detail on success and render inline validation/run feedback on failure
- the control-plane and run-detail surfaces now add version diffs, operational freshness summaries, dispatch drill-down, retry actions for runs with supported retry context, and worker-heartbeat plus stale-dispatch visibility for queue operations
- landing now uses explicit blob-store and metadata-store boundaries, with the current local filesystem and SQLite path kept as the default backend
- the transaction transform and reporting path now consume landed bytes directly, so reporting no longer depends on staging artifacts back to the local filesystem
- built-in landing, transformation, reporting, and application capabilities are now exposed through a shared extension registry that can also load external modules from configured custom paths
- executable extension handlers can now be invoked through the worker CLI and API for landing, transformation, and reporting layers
- source systems, dataset contracts, column mappings, source assets, ingestion definitions, transformation packages, and publication definitions now exist as persisted ingestion configuration entities
- dataset contracts and column mappings now support saved-version preview plus archived-version lifecycle in the control plane, and source assets, ingestion definitions, and execution schedules now also support archive/delete lifecycle with dependency-aware control-plane visibility
- config-driven CSV onboarding can land a new mapped dataset without new Python modules, and source-asset promotion now dispatches through the configured transformation package instead of account-specific heuristics
- filesystem and HTTP ingestion definitions can now execute through the same runtime config path, and HTTP request headers are stored as secret references resolved only at runtime
- the transaction transformation layer now persists UTC-normalized timestamps and normalized currency codes in DuckDB, and the reporting layer publishes current-dimension snapshots for the implemented SCD dimensions
- config-driven sources now preserve original bronze payload bytes while storing a canonical projection artifact for validation and promotion
- manual and config-driven account-transaction ingests now share the same retry-safe promotion path into DuckDB-backed marts and current-dimension views
- explicit subscription and temporal contract-pricing domains now exist alongside transactions, including `mart_subscription_summary`, `mart_contract_price_current`, and `mart_electricity_price_current`

The main remaining gaps are OIDC/service-token auth and broader production hardening. S3-compatible landing plus Postgres-backed control-plane/reporting backends now exist, local username/password auth is available as the bootstrap path, the worker now claims and processes queued dispatches continuously with recorded heartbeats, and the web surface now has a real Next.js shell that consumes the API only.

## Run locally

Current API entrypoints use FastAPI; the worker remains a lightweight Python entrypoint; and the web workload is now a Next.js frontend with a thin Python launcher for the built standalone server.

When a DuckDB transformation service is configured, built-in datasets auto-promote successful runs into the current silver/gold path through source-asset transformation bindings and publication definitions. Re-running promotion for the same run is idempotent and refreshes marts without duplicating facts, and config-driven publication definitions can now include registered extension publication relations. Publication-definition creation rejects unknown `publication_key` values unless they match a built-in mart or a registered published extension relation.

Environment variables:

- `HOMELAB_ANALYTICS_DATA_DIR` defaults to `.local/homelab-analytics` under the current working directory
- `HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH` overrides the SQLite ingestion-config database path (default: `<data_dir>/config.db`)
- `HOMELAB_ANALYTICS_CONFIG_BACKEND` selects `sqlite` or `postgres` for control-plane configuration, schedules, lineage, and publication audit (default: `sqlite`)
- `HOMELAB_ANALYTICS_METADATA_BACKEND` selects `sqlite` or `postgres` for ingestion run metadata (default: `sqlite`)
- `HOMELAB_ANALYTICS_POSTGRES_DSN` configures the shared Postgres backend used by control-plane, metadata, and published-reporting adapters when enabled
- `HOMELAB_ANALYTICS_CONTROL_SCHEMA` sets the Postgres schema for control-plane and metadata state (default: `control`)
- `HOMELAB_ANALYTICS_REPORTING_BACKEND` selects `duckdb` or `postgres` for published reporting reads (default: `duckdb`)
- `HOMELAB_ANALYTICS_REPORTING_SCHEMA` sets the Postgres schema for published reporting relations (default: `reporting`)
- `HOMELAB_ANALYTICS_API_HOST` defaults to `0.0.0.0`
- `HOMELAB_ANALYTICS_API_PORT` defaults to `8080`
- `HOMELAB_ANALYTICS_API_BASE_URL` overrides the backend API origin used by the Next.js web workload (default: `http://127.0.0.1:<api_port>`)
- `HOMELAB_ANALYTICS_WORKER_ID` optionally sets a stable worker identifier for queue claims and heartbeat records (default: `<hostname>-<pid>`)
- `HOMELAB_ANALYTICS_DISPATCH_LEASE_SECONDS` sets the running-dispatch claim window used for stale-dispatch detection (default: `300`)
- `HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH` overrides the DuckDB warehouse path (default: `<data_dir>/analytics/warehouse.duckdb`)
- `HOMELAB_ANALYTICS_BLOB_BACKEND` selects `filesystem` or `s3` for landed payload storage (default: `filesystem`)
- `HOMELAB_ANALYTICS_S3_ENDPOINT_URL`, `HOMELAB_ANALYTICS_S3_BUCKET`, `HOMELAB_ANALYTICS_S3_REGION`, `HOMELAB_ANALYTICS_S3_ACCESS_KEY_ID`, `HOMELAB_ANALYTICS_S3_SECRET_ACCESS_KEY`, and `HOMELAB_ANALYTICS_S3_PREFIX` configure the S3/MinIO landing adapter when enabled
- `HOMELAB_ANALYTICS_AUTH_MODE` selects `disabled` or `local` authentication (default: `disabled`; Compose and Helm examples use `local`)
- `HOMELAB_ANALYTICS_SESSION_SECRET` configures the HTTP-only signed session cookie secret for local auth
- `HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_USERNAME` and `HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_PASSWORD` optionally create the first local admin user at startup
- `HOMELAB_ANALYTICS_AUTH_FAILURE_WINDOW_SECONDS`, `HOMELAB_ANALYTICS_AUTH_FAILURE_THRESHOLD`, and `HOMELAB_ANALYTICS_AUTH_LOCKOUT_SECONDS` tune bootstrap local-auth login lockout behavior
- `HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN` keeps a temporary dev-only bypass for unauthenticated admin/control routes when needed (default: `false`)
- `HOMELAB_ANALYTICS_EXTENSION_PATHS` adds custom import roots for external extension repositories or mounted code paths
- `HOMELAB_ANALYTICS_EXTENSION_MODULES` lists Python modules to import and register into the layer extension registry
- `HOMELAB_ANALYTICS_SECRET__<SECRET_NAME>__<SECRET_KEY>` provides runtime values for secret references used by HTTP ingestion definitions

Examples:

```bash
python -m apps.worker.main ingest-account-transactions tests/fixtures/account_transactions_valid.csv
python -m apps.worker.main ingest-subscriptions tests/fixtures/subscriptions_valid.csv
python -m apps.worker.main ingest-contract-prices tests/fixtures/contract_prices_valid.csv
python -m apps.worker.main list-runs
python -m apps.worker.main list-ingestion-definitions
python -m apps.worker.main list-execution-schedules
python -m apps.worker.main list-local-users
python -m apps.worker.main create-local-admin-user admin replace-me-password
python -m apps.worker.main reset-local-user-password admin replace-me-new-password
python -m apps.worker.main enqueue-due-schedules --as-of 2026-01-01T00:00:00+00:00
python -m apps.worker.main list-schedule-dispatches
python -m apps.worker.main list-worker-heartbeats
python -m apps.worker.main mark-schedule-dispatch <dispatch_id> --status completed
python -m apps.worker.main process-schedule-dispatch <dispatch_id>
python -m apps.worker.main watch-schedule-dispatches
python -m apps.worker.main export-control-plane /tmp/control-plane.json
python -m apps.worker.main import-control-plane /tmp/control-plane.json
python -m apps.worker.main verify-config
python -m apps.worker.main list-extensions
python -m apps.worker.main report-monthly-cashflow
python -m apps.worker.main report-subscription-summary
python -m apps.worker.main report-contract-prices
python -m apps.worker.main report-electricity-prices
python -m apps.worker.main report-utility-cost-summary
python -m apps.worker.main run-transformation-extension account_transactions_canonical <run_id>
python -m apps.worker.main run-reporting-extension monthly_cashflow_summary <run_id>
python -m apps.worker.main process-ingestion-definition <ingestion_definition_id>
python -m apps.worker.main process-account-transactions-inbox
python -m apps.api.main
python -m apps.web.main
```

Verification:

```bash
make verify-fast
make verify-config
make test-e2e-local
make verify-domain DOMAIN=account
make verify-domain DOMAIN=subscriptions
make verify-domain DOMAIN=contract_prices
make verify-domain DOMAIN=utility
make test-storage-adapters
make compose-smoke
```

Use `make verify-config VERIFY_CONFIG_ARGS="--source-asset-id <source_asset_id>"` to preflight a single config-driven slice before running ingestion or promotion. The account, subscriptions, contract-prices, and utility `verify-domain` harnesses now run both global and scoped preflight checks before processing ingestion definitions.

## Extension model

The application keeps core ingestion, transformation, and reporting logic in-repo, but it now also supports external extension modules.

- built-in features remain the default and are registered in a shared layer registry
- external repositories or mounted custom paths can be added with `HOMELAB_ANALYTICS_EXTENSION_PATHS`
- extension modules are imported from `HOMELAB_ANALYTICS_EXTENSION_MODULES`
- each extension module must define `register_extensions(registry)` and register one or more entries for `landing`, `transformation`, `reporting`, or `application`
- executable landing, transformation, and reporting extensions can be run through the worker CLI and selected API endpoints once they register a handler
- executable reporting extensions must declare `data_access="published"` or `data_access="warehouse"` so application-facing execution does not silently fall back to landing reads
- published reporting extensions can also declare `publication_relations` so their named relations can be mirrored into the Postgres reporting store by publication key

That pattern keeps key product logic inside this repository while allowing custom source connectors, transformations, marts, and UI/API additions to live outside the main codebase.

Current execution surfaces:

`/health` and `/metrics` stay public. In local-auth mode, `/runs*`, `/reports*`, `/transformation-audit`, `GET /control/source-lineage`, `GET /control/publication-audit`, and the Next.js dashboard/run-detail views require at least a `reader`; `/ingest*` requires `operator`; `/config/*`, `/control/auth-audit`, `/control/schedule-dispatches`, `/extensions`, `/sources`, `/landing/*`, `/transformations/*`, persisted-ingestion processing, `/auth/users*`, and the `/control`, `/control/catalog`, and `/control/execution` admin pages require `admin`. Cookie-authenticated `POST` routes now require a CSRF token, login failures are rate-limited via control-plane auth audit history, and `HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN=true` remains a temporary local/dev-only escape hatch that is not used by the Compose or Helm defaults.

- `POST /landing/{extension_key}` for executable landing extensions
- `GET /metrics` for Prometheus-compatible operational metrics
- `GET /runs/{run_id}` for run-detail inspection in the API and Next.js web shell
- `POST /runs/{run_id}/retry` for operator retry of built-in and saved-binding configured runs
- `GET /auth/users`, `POST /auth/users`, `PATCH /auth/users/{user_id}`, and `POST /auth/users/{user_id}/password` for bootstrap local-user management
- `GET /sources` for the current source-system and source-asset catalog
- `GET`, `POST`, and `PATCH /config/source-systems/{id}` for source-system configuration
- `GET` and `POST /config/dataset-contracts`, `GET /config/dataset-contracts/{id}/diff`, and `PATCH /config/dataset-contracts/{id}/archive` for dataset-contract configuration, diffing, and archived-version lifecycle
- `GET` and `POST /config/column-mappings`, `GET /config/column-mappings/{id}/diff`, `PATCH /config/column-mappings/{id}/archive`, and `POST /config/column-mappings/preview` for column-mapping configuration, preview, diffing, and archived-version lifecycle
- `GET` and `POST /config/transformation-packages` for binding source assets to canonical transforms
- `GET` and `POST /config/publication-definitions` for declaring published reporting outputs
- `GET`, `POST`, `PATCH /config/source-assets/{id}`, `PATCH /config/source-assets/{id}/archive`, and `DELETE /config/source-assets/{id}` for source-asset configuration and lifecycle control
- `GET`, `POST`, `PATCH /config/ingestion-definitions/{id}`, `PATCH /config/ingestion-definitions/{id}/archive`, and `DELETE /config/ingestion-definitions/{id}` for transport, watch-folder, direct-API, and batch-extract configuration
- `GET`, `POST`, `PATCH /config/execution-schedules/{id}`, `PATCH /config/execution-schedules/{id}/archive`, and `DELETE /config/execution-schedules/{id}` for enqueue-only schedule definitions
- `GET /control/source-lineage`, `GET /control/publication-audit`, `GET /control/operational-summary`, `GET /control/schedule-dispatches`, `GET /control/schedule-dispatches/{id}`, and `POST /control/schedule-dispatches` for control-plane visibility and queueing
- `GET /control/auth-audit` for local-auth login, logout, and admin-user audit events
- `POST /ingest` for JSON path-based ingestion and multipart file uploads
- `POST /ingest/configured-csv` for config-driven CSV ingestion from server-side paths or multipart browser uploads bound by `source_asset_id`
- `POST /ingest/subscriptions` and `POST /ingest/contract-prices` for built-in non-transaction domains
- `POST /ingest/ingestion-definitions/{id}/process` for config-driven watch-folder, direct-API, and batch-extract execution
- `GET /reports/current-dimensions/{dimension_name}` for current SCD-dimension snapshots from the reporting layer
- `GET /reports/subscription-summary`, `GET /reports/contract-prices`, `GET /reports/electricity-prices`, and `GET /reports/utility-cost-summary` for built-in domain marts
- `GET /transformations/{extension_key}?run_id=...` for executable transformation extensions
- `GET /reports/{extension_key}?run_id=...` for executable reporting extensions

## Install locally

The repository now includes `pyproject.toml` with console scripts.

```bash
python -m pip install -e .
homelab-analytics-worker list-runs
homelab-analytics-api
# build apps/web/frontend first, or use the Docker web image below
homelab-analytics-web
```

## Run with Docker

Bootstrap artifacts now exist for image and Compose-based execution.

```bash
docker build -f infra/docker/Dockerfile -t homelab-analytics .
docker build -f infra/docker/web.Dockerfile -t homelab-analytics-web .
docker run --rm -p 8080:8080 -v "$(pwd)/.local/homelab-analytics:/data" homelab-analytics

make compose-smoke
docker compose -f infra/examples/compose.yaml up --build
docker compose -f infra/examples/compose.yaml run --rm worker ingest-account-transactions /data/input.csv
```

The example Compose stack now includes Postgres and MinIO and configures the workloads to use them for control-plane state, published reporting reads, landed payload storage, bootstrap local auth, and the dedicated Next.js web image. DuckDB remains local to the shared `/data` volume as the transformation-layer store.
`make compose-smoke` is the operator-facing startup check for that stack: it reuses the shared `homelab-analytics:latest` image when present, waits for API and web health, runs the worker CLI once, and then tears the stack down.
The Compose services also now define container healthchecks for API and web, so runtime tooling can observe the same readiness contract the smoke target uses.
The example stack pins third-party images as well, so release-ops verification is not silently tracking upstream `latest` tags.
The repo also now ships a `.dockerignore` that strips local virtualenvs, caches, tests, and docs from the build context so routine container verification stays cheap.

For Kubernetes-facing secret handling, the repository now includes example Secret manifests under `infra/examples/secrets/` for the current credential classes: database, bootstrap local auth, blob storage, OIDC, and provider API access. It also includes an External Secrets Operator example for the Postgres DSN and a SOPS-style encrypted Secret example for provider credentials. These are placeholders only and meant to show the intended cluster-managed patterns, not to be applied unchanged.

## Run with Helm

The repository now includes a minimal chart for the current API and watched-folder worker slice.

```bash
helm lint charts/homelab-analytics
helm template homelab-analytics charts/homelab-analytics
helm install homelab-analytics charts/homelab-analytics
```

The Helm verification gate now parses rendered manifests and asserts workload image/command wiring plus per-workload `secretEnvFrom` references, while also checking that chart output does not render inline credentials or Secret objects for the runtime stack.
The chart also now includes `charts/homelab-analytics/values.runtime-secrets-example.yaml`, which demonstrates the intended Secret isolation split between API/web reporting access, shared bootstrap local-auth/session secrets, and worker landing/transformation access.
The default chart values now enable `HOMELAB_ANALYTICS_AUTH_MODE=local`; runtime session/bootstrap admin values are expected to come from Secret references rather than inline chart values.
