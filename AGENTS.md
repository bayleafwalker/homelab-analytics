# Agent Guidance

## Project intent

This repository is building a homelab and household analytics product with a strict layered model:

- landing is for immutable raw payloads plus input validation
- transformation is for reusable normalized models and SCD dimensions
- reporting is for dashboard and API-facing marts

Do not collapse those layers just to make an early feature faster.

## Current phase

The project is still in bootstrap and architecture mode. Prefer:

- small, testable scaffolding
- explicit contracts and sample-driven connector design
- documentation updates when architecture changes

Avoid introducing heavy infrastructure before the core ingestion and modeling path exists.

## Default technical direction

- API: FastAPI
- worker: Python with Polars and DuckDB
- web: React/Next.js
- published state and metadata: Postgres
- raw payload archive: S3-compatible object storage
- deployment target: Docker and Helm on Kubernetes

Spark, Dagster, Argo, and similar additions are optional later steps, not default assumptions.

## Agent modes

Detailed mode guides live under `docs/agents/`:

- `docs/agents/planning.md`
- `docs/agents/implementation.md`
- `docs/agents/review.md`
- `docs/agents/release-ops.md`

Choose the mode that matches the task. If a task spans modes, complete planning first, then implementation, then review or release work.

## Mandatory repo rules

- When adding a source connector, define its landing contract, validation checks, and canonical mapping target.
- When adding a dimension, decide whether it needs SCD handling in transformation and a current snapshot in reporting.
- When adding dashboard logic, build on reporting models instead of source-specific transforms.
- Keep key ingestion, transformation, and reporting logic in-repo unless there is a strong reason not to.
- When adding extensibility, prefer registering external code through configured modules and custom paths instead of asking users to fork core packages.
- Treat landing, transformation, reporting, and application additions as separate extension layers with explicit contracts.
- When changing architecture or stack choices, update the relevant docs under `docs/`.
- When changing or adding requirements, update the relevant file under `requirements/` and keep status and phase fields current.
- Keep tests aligned with the repository bootstrap contract in `tests/test_repository_contract.py`.
- Behavior changes must update or add tests in the same change.
- App-facing reporting paths must use reporting-layer models when configured; do not add new landing-to-dashboard shortcuts.
