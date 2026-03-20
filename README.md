# homelab-analytics

Self-hosted household operating platform for ingesting heterogeneous personal datasets, normalizing them into reusable canonical models, and publishing household operating views through dashboards, APIs, and automation surfaces.

The platform answers recurring household questions about money, utilities, and infrastructure operations through a composable Household Operating Picture built on explicit bronze/silver/gold data boundaries, canonical facts and dimensions, and stable publication contracts.

This is not a Home Assistant add-on. Home Assistant is a first-class integration partner: it is the edge runtime, device hub, family-facing operational UI, and primary actuation surface. This platform provides what a HA add-on cannot — canonical cross-domain household semantics spanning finance, utilities, assets, contracts, loans, and homelab telemetry; long-horizon history; planning, simulation, and policy evaluation logic; trust and lineage; and multi-surface publishing. Platform outputs flow back to HA as synthetic entities for visualization, voice responses, and automation triggers. See `docs/product/homeassistant-and-smart-home-hub.md` for the product boundary and `docs/architecture/homeassistant-integration-hub.md` for the integration architecture.

## Product direction

The project follows a 10-stage roadmap from analytics platform to household operating platform:

0. Documentation reset and direction lock
1. Canonical household model
2. Operating views
3. Planning and control surfaces
4. Simulation and scenario engine
5. Policy, automation, and action engine
6. Multi-renderer and semantic delivery layer
7. Extension and pack ecosystem
8. Trust, governance, and operator confidence
9. Agentic and assistant layer

The project is currently delivering Stage 2 (Operating Views) through the 4-sprint product loop. See `docs/plans/household-operating-platform-roadmap.md` for stage details and `docs/decisions/household-operating-platform-direction.md` for the direction ADR.

## Current capabilities (v0.1.0 — Household Operating Picture)

- Three domain capability packs: finance (transactions, subscriptions, budgets, loans), utilities (usage, bills, contracts), and cross-domain overview
- Thirty-six publications: monthly cashflow, budget variance and progress, loan schedule and overview, utility cost trends, affordability ratios, recurring cost baseline, household cost model, and more
- Full data pipeline: landing (bronze) → transformation (silver) → reporting (gold)
- Budget vs Reality: per-category budget targets against actual spend with variance and utilisation tracking
- Debt and Cost Truth: amortization engine, loan schedule projection, repayment variance, and balance estimates
- Household Cost Model: unified cost picture aggregated from all domains with 12-month trend
- Affordability Ratios: housing-to-income, total-cost-to-income, and debt-service ratio with threshold assessments
- Recurring Cost Baseline: active subscriptions, loan payments, and detected utility fixed charges
- Config-driven source onboarding for CSV, XLSX, JSON, and HTTP sources
- SCD Type 2 dimensions with current-dimension reporting views
- Authentication: local bootstrap, OIDC, and scoped service tokens with role separation
- FastAPI-based REST API with Prometheus metrics and structured JSON logging
- Next.js web shell with dashboard, budgets, loans, costs, upload, and control-plane admin
- Source freshness operator view: staleness indicators and quick-action upload links
- Worker CLI with schedule dispatch, lease renewal, and stale-dispatch recovery
- Docker Compose and Helm/Kubernetes deployment paths
- Extension model for external connectors, transformations, and marts
- 727 tests passing (702 unit + 25 household integration)

## Repository layout

```text
homelab-analytics/
├── apps/
│   ├── api/                    # FastAPI application
│   ├── worker/                 # Worker CLI and dispatch
│   └── web/                    # Next.js web shell
├── packages/
│   ├── adapters/               # API and worker adapter layer
│   ├── analytics/              # Reporting logic
│   ├── application/            # Use-case orchestration
│   ├── connectors/             # External connectors
│   ├── domains/                # Domain capability packs
│   │   ├── finance/            # Cash flow, subscriptions, transactions
│   │   ├── utilities/          # Utility costs, contracts, metering
│   │   └── overview/           # Cross-domain composition
│   ├── pipelines/              # Transformation and mart logic
│   ├── platform/               # Runtime, auth, capability types
│   ├── shared/                 # Extension registry, auth shim, contracts
│   └── storage/                # DuckDB, Postgres, SQLite, S3 adapters
├── charts/
│   └── homelab-analytics/      # Helm chart
├── infra/
│   ├── docker/                 # Dockerfiles
│   └── examples/               # Compose, secrets examples
├── docs/
│   ├── architecture/           # Data platform architecture
│   ├── agents/                 # Agent mode guidance
│   ├── decisions/              # ADRs
│   ├── plans/                  # Strategic plans and roadmap
│   ├── product/                # Product scope and design
│   ├── sprints/                # Sprint plans and scope
│   ├── runbooks/               # Operational guides
│   └── notes/                  # Integration notes
├── requirements/               # Requirements baseline
└── tests/                      # Pytest suite and architecture tests
```

## Documentation

- `docs/README.md` — full documentation index
- `requirements/README.md` — requirements baseline across five domains
- `docs/architecture/data-platform-architecture.md` — source-to-reporting data architecture and forward-looking layer definitions
- `docs/decisions/household-operating-platform-direction.md` — operating platform direction and 10-stage model
- `docs/decisions/household-platform-adr-and-refactor-blueprint.md` — modular monolith architecture and capability pack model
- `docs/product/core-household-operating-picture.md` — core product definition and acceptance criteria
- `docs/plans/household-operating-platform-roadmap.md` — 10-stage roadmap with deliverables and dependencies
- `docs/product/homeassistant-and-smart-home-hub.md` — Home Assistant as edge runtime and actuation layer, platform vs HA boundary, and build ordering
- `docs/architecture/homeassistant-integration-hub.md` — six-layer HA integration hub architecture

## Run locally

The API uses FastAPI, the worker is a lightweight Python entrypoint, and the web workload is a Next.js frontend with a thin Python launcher.

Key environment variables (see `docs/runbooks/configuration.md` for the full reference):

- `HOMELAB_ANALYTICS_DATA_DIR` — local data directory (default: `.local/homelab-analytics`)
- `HOMELAB_ANALYTICS_POSTGRES_DSN` — shared Postgres backend DSN
- `HOMELAB_ANALYTICS_AUTH_MODE` — `disabled`, `local`, or `oidc` (default: `disabled`)
- `HOMELAB_ANALYTICS_BLOB_BACKEND` — `filesystem` or `s3` (default: `filesystem`)
- `HOMELAB_ANALYTICS_EXTENSION_PATHS` — custom import roots for external extensions

Examples:

```bash
python -m apps.worker.main ingest-account-transactions tests/fixtures/account_transactions_valid.csv
python -m apps.worker.main list-runs
python -m apps.worker.main report-monthly-cashflow
python -m apps.worker.main watch-schedule-dispatches
python -m apps.api.main
python -m apps.web.main
```

When a DuckDB transformation service is configured, built-in datasets auto-promote successful runs into the current silver/gold path through source-asset transformation bindings and publication definitions. Re-running promotion for the same run is idempotent and refreshes marts without duplicating facts.

## Verification

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

The application keeps core ingestion, transformation, and reporting logic in-repo, but also supports external extension modules.

- Built-in features are registered in a shared layer registry
- External repositories or mounted custom paths can be added with `HOMELAB_ANALYTICS_EXTENSION_PATHS`
- Extension modules are imported from `HOMELAB_ANALYTICS_EXTENSION_MODULES`
- Each extension module must define `register_extensions(registry)` and register entries for `landing`, `transformation`, `reporting`, or `application`
- Executable extensions can be invoked through the worker CLI and API
- Published reporting extensions can declare `publication_relations` for Postgres mirroring

See `docs/architecture/data-platform-architecture.md` for the full extensibility model, pack ecosystem model, and registry source expectations.

## Install locally

```bash
python -m pip install -e .
homelab-analytics-worker list-runs
homelab-analytics-api
# build apps/web/frontend first, or use the Docker web image below
homelab-analytics-web
```

## Run with Docker

```bash
docker build -f infra/docker/Dockerfile -t homelab-analytics .
docker build -f infra/docker/web.Dockerfile -t homelab-analytics-web .
docker run --rm -p 8080:8080 -v "$(pwd)/.local/homelab-analytics:/data" homelab-analytics

make compose-smoke
docker compose -f infra/examples/compose.yaml up --build
```

The example Compose stack includes Postgres and MinIO and configures workloads for control-plane state, published reporting, landed payload storage, and local break-glass auth. `make compose-smoke` is the operator-facing startup check.

## Run with Helm

```bash
helm lint charts/homelab-analytics
helm template homelab-analytics charts/homelab-analytics
helm install homelab-analytics charts/homelab-analytics
```

The default chart values enable OIDC auth. See `docs/runbooks/operations.md` for ingress, readiness, and alert-response guidance. See `charts/homelab-analytics/values.runtime-secrets-example.yaml` for the intended Secret isolation split.
