# Homelab Analytics Platform Plan

> **Note:** Detailed, phased requirements with acceptance criteria now live in `requirements/` at the repository root. This document records the strategic decisions and rationale that shaped the initial bootstrap.

## Objective

Build a self-hosted data platform that ingests household and homelab datasets, normalizes them into reusable models, and publishes dashboards and APIs from the same core data products.

## Technology decisions

### Default stack

- API: FastAPI
- Worker runtime: Python with Polars + DuckDB + PyArrow
- Metadata and reporting store: Postgres
- Raw landing archive: S3-compatible object storage
- Web UI: Next.js
- Deployment: Docker plus Helm on Kubernetes

### Why not Spark first

Spark is the wrong default for a homelab-first platform: the early problem is source heterogeneity and contract handling, not distributed compute. Spark remains a future backend option. See `docs/decisions/compute-and-orchestration-options.md` for the full comparison.

### Workload management

Start with in-application scheduling plus Kubernetes Jobs and CronJobs. Later options: Dagster, Argo Workflows, KEDA — only when measured workload requires them.

## Ingestion strategy

Support multiple source onboarding patterns without changing the downstream model:

- **Manual and folder-based:** web UI upload, folder watchers on NFS, synced folders from OneDrive, Nextcloud, and Google Drive via rclone or mount-based sync
- **Direct API:** utility providers (Elisa Kotiakku, Helen), Home Assistant, Prometheus, and generic authenticated REST endpoints
- **Batch extracts:** scheduled curl jobs, browser-exported files

All sources are onboarded through configuration (source system, dataset contract, column mapping), not hard-coded connectors.

## Extensibility

- Keep key ingestion, transformation, and reporting capabilities in-tree
- Support optional connectors, transforms, marts, and application add-ons from external repositories and custom paths
- Every layer exposes registration-based extension hooks instead of requiring forks
- Executable landing, transformation, and reporting extensions should be invokable through worker commands and API endpoints

## Security and authentication

- **Secrets:** External Secrets Operator or SOPS-encrypted Secrets — never checked-in values
- **Auth progression:** local username/password → OIDC → service tokens for Home Assistant and automation consumers
- **Credential isolation:** per-workload, least-privilege

## Release direction

- Docker images and Helm chart published from this repository
- Generalizable packaging for GitHub or Forgejo release

## Implementation choices taken now

These are deliberate defaults recorded during the bootstrap phase:

- Default compute is Polars and DuckDB, not Spark
- Default orchestration is application scheduling plus Kubernetes Jobs and CronJobs
- Dimensions belong as SCD in transformation and as current snapshots in reporting
- Landing owns contract and data quality enforcement
- Reporting serves both dashboard and API consumers
- Secrets should be cluster-managed through External Secrets or SOPS
- Packaging should target Docker and Helm for later public release

These are deliberate defaults, not permanent constraints.
