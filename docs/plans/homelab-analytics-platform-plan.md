# Homelab Analytics Platform Plan

## Objective

Initialize this repository as the build home for a self-hosted data platform that can ingest household and homelab datasets, normalize them into reusable models, and publish both dashboards and APIs.

The target problem space includes:

- manual CSV and XLSX ingestion
- watched file drops from NFS or synced folders
- provider API pulls such as utility data
- authenticated batch extracts fetched with curl or equivalent jobs
- financial exports for transactions, balances, loans, and repayments
- internal platform sources such as Prometheus and Home Assistant

## Current repository state

This repository started as a high-level planning home. The main missing notes were:

- no explicit source-to-landing pattern
- no landing data quality or dataset contract model
- no transformation model for reusable facts and dimensions
- no SCD strategy for dimensions
- no reporting publication model for dashboard and API consumers
- no clear recommendation between Spark and lighter-weight alternatives
- no concrete security and secret management posture
- no minimal project-specific agent guidance

This bootstrap addresses those gaps.

## Core architecture

The implementation should follow one data lifecycle:

1. Input and landing
   - accept uploads, watched folders, synced folders, and scheduled API or curl pulls
   - persist original payloads in immutable object storage
   - validate each run against a dataset contract
   - stop promotion on data quality failures
2. Transformation
   - normalize source-specific structures into canonical facts and dimensions
   - persist historical dimensions as Type 2 SCD where needed
   - keep this layer reusable and independent from dashboard layout
3. Reporting
   - publish current-time dimension views and dashboard-ready marts
   - expose the same curated models to the web UI and API consumers

The detailed architecture is recorded in `docs/architecture/data-platform-architecture.md`.

## Recommended technology path

### Default path

- API: FastAPI
- worker runtime: Python
- transform engine: Polars + DuckDB + PyArrow
- relational metadata and reporting store: Postgres
- raw landing archive: S3-compatible object storage
- web UI: Next.js with a charting library
- deployment: Docker plus Helm on Kubernetes

### Why not Spark first

Spark is credible and fully open-source, but it is the wrong default here:

- the early problem is source heterogeneity and contract handling, not distributed compute
- the operational cost is high for a homelab-first platform
- local iteration and packaging are slower

Spark should remain a future backend option for larger batch workloads, not the initial baseline.

### Workload management

Recommended starting point:

- in-application scheduling for user-defined jobs
- Kubernetes Jobs for isolated manual or triggered runs
- Kubernetes CronJobs for recurring system-managed ingestion

Later options:

- Dagster if richer lineage and dependency management becomes necessary
- Argo Workflows if multi-step Kubernetes-native execution grows
- KEDA if queue-backed autoscaling becomes necessary

The comparison and trigger points are documented in `docs/decisions/compute-and-orchestration-options.md`.

## Source and ingestion strategy

The platform should support multiple source onboarding patterns without changing the downstream model.

### Manual and folder-based ingestion

- direct upload through the web UI
- folder watchers on mounted NFS or similar shares
- synced folders from OneDrive, Nextcloud, and Google Drive
- manual mapping from source columns to landing and curated models

Recommendation:

- treat folder-like external systems as synced file sources first
- use `rclone`, WebDAV, or mount-based sync rather than building every proprietary connector immediately

### Direct API ingestion

Initial connector categories:

- utility provider APIs such as Elisa Kotiakku or Helen where available
- generic authenticated REST pullers
- internal endpoints for Home Assistant and Prometheus-derived pulls

### Batch extract ingestion

- user-managed exports dropped into source folders
- scheduled curl jobs with headers or bearer tokens
- batch downloads converted to landing artifacts exactly as received

## Data modeling principles

### Landing

Landing is the system boundary for source correctness:

- immutable raw payload storage
- contract validation
- schema profiling
- duplicate and freshness checks
- ingestion audit trail

### Transformation

Transformation is source-agnostic and reusable:

- canonical facts for transactions, balances, utility usage, bills, and repayments
- canonical dimensions for accounts, counterparties, meters, contracts, loans, services, and household members
- SCD persistence for dimensions whose attributes change over time

### Reporting

Reporting is consumer-facing:

- current snapshots of SCD dimensions
- dashboard-oriented marts
- metrics and aggregates for APIs and automations
- Home Assistant-friendly endpoints for selected measures

## Security and authentication

### Secrets

Recommended options:

- External Secrets Operator if the cluster already uses it
- SOPS-encrypted Secret manifests as a simpler fallback

Secret classes to isolate:

- provider API credentials
- drive or sync credentials
- database credentials
- OIDC client secrets

### User access

Recommended auth progression:

- local username/password bootstrap for the first internal deployment
- OIDC for normal UI access once the product is externally reachable
- service tokens for automation or Home Assistant API consumers

### Cluster exposure

- publish through the existing ingress or Gateway API path
- keep admin and ingestion endpoints protected
- use least-privilege credentials per workload

## Runtime and repository shape

The repository should continue toward this structure:

```text
apps/
  api/
  worker/
  web/
packages/
  analytics/
  connectors/
  pipelines/
  shared/
  storage/
charts/
  homelab-analytics/
infra/
  docker/
  examples/
docs/
tests/
```

Implementation boundaries:

- `apps/api`: control plane, run metadata, dataset definitions, auth, public API
- `apps/worker`: ingestion, validation, transformation, materialization
- `apps/web`: dashboard UI and future ingestion mapping UI
- `packages/connectors`: provider and file connectors
- `packages/pipelines`: contracts, checks, orchestration, transformation workflows
- `packages/storage`: object, DuckDB, and Postgres access
- `packages/analytics`: reusable marts and metric logic

## Reporting surface

The reporting layer should support both user-facing UI and programmatic access.

Required output surfaces:

- dashboards in the web application
- API endpoints for Home Assistant or other consumers
- exportable datasets for offline analysis

Planned future UI areas:

- dashboard browsing
- ingestion history
- source and mapping administration
- contract failure inspection
- schedule management

## Cluster deployment direction

Target deployment pattern:

- one Helm chart
- separate `api`, `worker`, and `web` workloads
- optional scheduler workload
- Postgres and object storage referenced externally
- ingress handled by the cluster ingress controller or Gateway API

Release direction:

- Docker images published from this repository
- Helm chart published for cluster consumption
- generalizable release packaging for GitHub or Forgejo

`docs/notes/appservice-cluster-integration-notes.md` holds the current cluster assumptions.

## Testing-first bootstrap strategy

At this stage, tests should protect structure and contract more than runtime behavior.

Implemented now:

- repository-contract tests for required directories and planning docs

Next tests to add with code:

- connector contract tests using sample fixtures
- landing validation tests for schema drift and bad inputs
- transformation tests around canonical models and SCD behavior
- API tests for ingestion run visibility and reporting endpoints
- chart render smoke tests

## Recommended implementation sequence

### Phase 0: bootstrap

- finalize docs and repository layout
- keep tests protecting the agreed shape
- add local development container or Compose examples

### Phase 1: vertical slice

- implement one CSV/manual upload connector
- persist raw payload to landing storage
- run contract and data quality checks
- normalize into one canonical fact and one dimension
- publish one dashboard and one API endpoint

Suggested first slice:

- card or account transactions to monthly household cash-flow reporting

### Phase 2: generalized ingestion

- add watched folder ingestion
- add generic REST puller
- add mapping configuration persistence
- add current-view publication from SCD dimensions

### Phase 3: household packs

- electricity and utility models
- loan and repayment models
- recurring bills and budget derivations
- profitability or affordability assessments

### Phase 4: productization

- OIDC
- hardened secret handling
- chart release automation
- example Docker and Helm values
- documentation for external adopters

## Implementation choices taken now

The repository bootstrap now takes these positions:

- default compute is Polars and DuckDB, not Spark
- default orchestration is application scheduling plus Kubernetes Jobs and CronJobs
- dimensions belong as SCD in transformation and as current snapshots in reporting
- landing owns contract and data quality enforcement
- reporting serves both dashboard and API consumers
- secrets should be cluster-managed through External Secrets or SOPS
- packaging should target Docker and Helm for later public release

These are deliberate defaults, not permanent constraints.
