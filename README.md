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

- `docs/README.md` contains the document index.
- `docs/plans/homelab-analytics-platform-plan.md` is the primary delivery and implementation plan.
- `docs/architecture/data-platform-architecture.md` defines the source-to-reporting data architecture.
- `docs/decisions/compute-and-orchestration-options.md` compares Spark and other execution/orchestration options and records the recommended initial path.
- `docs/notes/appservice-cluster-integration-notes.md` captures cluster deployment assumptions.

## Current status

This repository is now bootstrapped as a planning and scaffolding home:

- the initial runtime/package/chart directory structure exists
- repository-contract tests protect the agreed starting shape
- architecture and decision docs define the first implementation path

Application code, Helm manifests, and production-ready connectors still need to be implemented.
