# Application Services Requirements

## Overview

The platform exposes its capabilities through three application workloads: a JSON/REST API for programmatic access, a web UI for interactive dashboards and administration, and a CLI worker for batch processing and scheduled execution. All three consume the same underlying service and storage layers.

---

## Requirements

### APP-01: REST API — ingestion endpoints

**Description:** The API accepts file uploads, source path submissions, and on-demand API pull triggers. Every ingestion request returns a run ID for tracking.

**Rationale:** Programmatic ingestion access is required for automation, CI/CD integration, and the web UI upload flow.

**Phase:** 1
**Status:** in-progress (FastAPI app replaces stdlib WSGI; multipart file upload and server-side path submission both work; config/admin routes now use typed request models in OpenAPI; duplicate ingests return `409`, validation failures return `400`, docs are available at `/docs`, and built-in endpoints exist for configured CSV, subscription, contract-price, and persisted ingestion-definition execution; web UI upload form is not yet built)

**Acceptance criteria:**
- `POST /ingest` accepts multipart file upload with source/dataset metadata, returns `{"run_id": "..."}`.
- `POST /ingest` also accepts `{"source_path": "..."}` for server-side file paths.
- API returns appropriate HTTP status codes (201 created, 400 validation failure, 409 duplicate).
- FastAPI is the framework (replaces current stdlib WSGI).
- Tests verify upload, validation failure, and duplicate detection flows.

**Dependencies:** ING-01, PLT-02

---

### APP-02: REST API — run and metadata endpoints

**Description:** The API exposes ingestion run history, status, validation results, and source/dataset metadata.

**Rationale:** Run visibility is essential for debugging, monitoring, and building the web UI ingestion history view.

**Phase:** 1
**Status:** implemented (`GET /runs` supports pagination via `limit`/`offset` query params and filtering by `dataset`, `status`, `from_date`, and `to_date`; response includes a `pagination` envelope with `total`, `limit`, and `offset`; `GET /runs/{id}` returns full run detail; `GET /sources` returns registered systems and assets; OpenAPI docs available at `/docs`; tests verify response shape and filtering)

**Acceptance criteria:**
- `GET /runs` returns paginated run list with filtering by dataset, status, and date range.
- `GET /runs/{id}` returns full run detail including validation issues.
- `GET /sources` returns registered source systems and their assets.
- FastAPI auto-generated OpenAPI docs are available at `/docs`.
- Tests verify response shapes and filtering.

**Dependencies:** PLT-02, ING-07

---

### APP-03: REST API — reporting endpoints

**Description:** The API exposes reporting marts and metrics with filtering, date ranges, and pagination.

**Rationale:** Dashboard UI and external consumers (e.g. Home Assistant) access analytics data through the same API.

**Phase:** 1–3
**Status:** in-progress (`GET /reports/monthly-cashflow` and the other built-in marts read through the reporting-service contract; when Postgres published reporting is configured, API/web app-facing reads now require published relations instead of falling back to DuckDB; current-dimension, subscription-summary, contract-price, electricity-price, and utility-cost-summary endpoints are exposed from reporting-layer models; executable reporting extensions now advertise whether they are `published` or `warehouse` backed, published extensions can declare publication relations for Postgres-backed execution, and config-driven publication definitions can include those relation keys during promotion; export formats and remaining mart endpoints are still pending)

**Acceptance criteria:**
- `GET /reports/{mart_name}` returns mart data with query parameters for date range and filters.
- Response supports JSON format; CSV and Parquet export via `Accept` header or query parameter (Phase 2).
- Each mart from PLT-12 has a corresponding API endpoint.
- Tests verify response content from known fixture data.

**Dependencies:** PLT-12

---

### APP-04: REST API — admin endpoints

**Description:** Admin endpoints for managing sources, contracts, mappings, schedules, and users. Require elevated authentication.

**Rationale:** Operational management through API enables both UI administration and scripted configuration.

**Phase:** 4
**Status:** in-progress (CRUD-style config endpoints exist for source systems, dataset contracts, column mappings, transformation packages, publication definitions, source assets, ingestion definitions, and execution schedules; control-plane read endpoints expose schedule dispatches, source lineage, and publication audit; publication-definition creation rejects unknown built-in or extension relation keys; local auth now protects admin/control routes with an `admin` role, while `HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN` remains only as a temporary local bypass)

**Acceptance criteria:**
- CRUD endpoints for source systems, dataset contracts, column mappings, transformation packages, publication definitions, and schedules.
- Admin endpoints require authentication and an admin role.
- Tests verify authorization enforcement (unauthenticated requests are rejected).

**Dependencies:** SEC-01, SEC-04, ING-07

---

### APP-05: Web UI — dashboard views

**Description:** Interactive dashboards displaying reporting marts with charts and tables. Responsive and navigable.

**Rationale:** The primary user interaction surface. Dashboards must present derived analytics clearly.

**Phase:** 2
**Status:** in-progress (a minimal Next.js shell now exists for login, dashboard, runs, and reporting views; it consumes the API only and replaces the old server-rendered Python dashboard, but broader product/admin surface work is still pending)

**Acceptance criteria:**
- Dashboard pages render from reporting API data.
- At least: cash-flow trend chart, summary cards, monthly breakdown table.
- UI is responsive on desktop and tablet.
- Built with React/Next.js (replaces current server-rendered HTML).
- Tests verify component rendering with mock API data.

**Dependencies:** APP-03

---

### APP-06: Web UI — ingestion run monitoring

**Description:** Users view ingestion run history, status, validation results, and contract failure details.

**Rationale:** Visibility into ingestion status builds trust in the data and enables self-service troubleshooting.

**Phase:** 2
**Status:** in-progress (the Next.js shell now exposes a basic run-history view backed by the API; detail pages and richer filtering are still pending)

**Acceptance criteria:**
- Run list page shows recent runs with status badges.
- Run detail page shows validation issues with row/column references.
- Status filters allow viewing only failed or rejected runs.

**Dependencies:** APP-02, APP-05

---

### APP-07: Web UI — manual file upload

**Description:** Users upload files and assign them to source definitions through the web UI.

**Rationale:** Non-technical household members should be able to import data without CLI or API knowledge.

**Phase:** 2
**Status:** not-started

**Acceptance criteria:**
- Upload form allows file selection, source system choice, and dataset type choice.
- Upload triggers ingestion and redirects to the run detail page.
- Validation failures are displayed inline.

**Dependencies:** APP-01, APP-05

---

### APP-08: Web UI — source and mapping administration

**Description:** View and manage source system definitions, ingestion definitions, and column mappings through the UI. Later deliverable.

**Rationale:** Configuration-driven onboarding needs a management surface for non-developer users.

**Phase:** 4
**Status:** not-started

**Acceptance criteria:**
- List, create, edit, and deactivate source systems.
- View and version column mappings.
- Preview mapping results against sample data.

**Dependencies:** ING-07, ING-08, SEC-04, APP-05

---

### APP-09: Web UI — dataset exploration

**Description:** Browse and query datasets at each layer (landing, transformation, reporting). Read-only exploration.

**Rationale:** Data exploration builds understanding and enables ad-hoc analysis beyond pre-built dashboards.

**Phase:** 4
**Status:** not-started

**Acceptance criteria:**
- Users can select a layer and dataset, browse schema, and preview rows.
- Basic filtering and sorting are supported.
- No write operations are exposed.

**Dependencies:** PLT-14, APP-05

---

### APP-10: Web UI — schedule management

**Description:** View and manage ingestion schedules through the web UI.

**Rationale:** Schedule visibility and control reduce operational burden.

**Phase:** 4
**Status:** not-started

**Acceptance criteria:**
- List active schedules with next-run time and last-run status.
- Create, pause, and delete schedules.
- Schedule changes are persisted and take effect at next poll.

**Dependencies:** ING-03, ING-04, APP-05

---

### APP-11: Worker CLI

**Description:** CLI tool for batch ingestion, inbox processing, folder watching, run listing, and report generation. Usable both interactively and from Kubernetes Jobs/CronJobs.

**Rationale:** The worker is the execution engine for all data processing. CLI interface enables scripting, debugging, and Kubernetes Job integration.

**Phase:** 0
**Status:** implemented (JSON-emitting commands cover account ingestion, configured CSV ingestion, ingestion-definition processing, config preflight verification, inbox processing/watch, extension execution, subscription and contract-price ingestion/reporting, utility cost summary reporting, execution-schedule enqueue/list/mark flows, control-plane import/export, and local-user bootstrap/reset/list operations)

**Acceptance criteria:**
- All subcommands emit JSON for parseable output.
- Exit codes reflect success/failure.
- Worker can run as a Kubernetes Job with configurable arguments.
- Tests verify CLI argument parsing and output format.

**Dependencies:** none

---

### APP-12: Health endpoints

**Description:** All workloads expose `/health` for liveness and readiness probes.

**Rationale:** Kubernetes probes require health endpoints for reliable pod lifecycle management.

**Phase:** 0
**Status:** implemented (API and web both expose `/health`)

**Acceptance criteria:**
- `GET /health` returns 200 with `{"status": "ok"}` (API) or plain text "ok" (web).
- Worker health is implicit (process exit code).

**Dependencies:** none

---

## Traceability

| Requirement | Implementation module | Test file |
|---|---|---|
| APP-01 | `apps/api/app.py` | `tests/test_api_app.py` |
| APP-02 | `apps/api/app.py` | `tests/test_api_app.py` |
| APP-03 | `apps/api/app.py` | `tests/test_api_app.py`, `tests/test_utility_domain.py`, `tests/test_local_domain_harness.py` |
| APP-04 | `apps/api/app.py` | `tests/test_api_app.py` |
| APP-05 | `apps/web/frontend/app/page.js`, `apps/web/frontend/app/reports/page.js`, `apps/web/frontend/components/app-shell.js` | `tests/test_web_app.py`, `tests/test_web_auth.py` |
| APP-06 | `apps/web/frontend/app/runs/page.js`, `apps/web/frontend/lib/backend.js` | `tests/test_web_auth.py` |
| APP-07 | — | — |
| APP-08 | — | — |
| APP-09 | — | — |
| APP-10 | — | — |
| APP-11 | `apps/worker/main.py`, `packages/pipelines/config_preflight.py` | `tests/test_worker_cli.py`, `tests/test_config_preflight.py`, `tests/test_utility_domain.py`, `tests/test_local_domain_harness.py` |
| APP-12 | `apps/api/app.py`, `apps/web/frontend/app/health/route.js` | `tests/test_api_app.py`, `tests/test_web_app.py` |
