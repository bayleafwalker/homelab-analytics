# Application Services Requirements

## Overview

The platform exposes its capabilities through three application workloads: a JSON/REST API for programmatic access, a web UI for interactive dashboards and administration, and a CLI worker for batch processing and scheduled execution. All three consume the same underlying service and storage layers.

---

## Requirements

### APP-01: REST API — ingestion endpoints

**Description:** The API accepts file uploads, source path submissions, and on-demand API pull triggers. Every ingestion request returns a run ID for tracking.

**Rationale:** Programmatic ingestion access is required for automation, CI/CD integration, and the web UI upload flow.

**Phase:** 1
**Status:** in-progress (FastAPI app replaces stdlib WSGI; multipart file upload and server-side path submission both work; config/admin routes now use typed request models in OpenAPI; duplicate ingests return `409`, validation failures return `400`, docs are available at `/docs`, built-in endpoints exist for configured CSV, subscription, contract-price, and persisted ingestion-definition execution, and configured CSV now also supports multipart browser upload bound by `source_asset_id`; failed browser uploads now return structured run and validation context that the web surface renders inline)

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
**Status:** implemented (`GET /runs` supports pagination via `limit`/`offset` query params and filtering by `dataset`, `status`, `from_date`, and `to_date`; response includes a `pagination` envelope with `total`, `limit`, and `offset`; `GET /runs/{id}` now returns full run detail plus saved control-plane context and retry capability metadata; `POST /runs/{id}/retry` replays built-in and saved-binding configured runs; `GET /sources` returns registered systems and assets; OpenAPI docs available at `/docs`; tests verify response shape, filtering, retry, and operational-summary contracts)

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
**Status:** in-progress (`GET /reports/monthly-cashflow` and the other built-in marts read through the reporting-service contract; when Postgres published reporting is configured, API/web app-facing reads now require published relations instead of falling back to DuckDB; current-dimension, subscription-summary, contract-price, electricity-price, utility-cost-summary, and homelab ROI endpoints are exposed from reporting-layer models; `GET /contracts/publication-index` now provides a semantic retrieval view over publication contracts and UI descriptors for agent-facing consumers; executable reporting extensions now advertise whether they are `published` or `warehouse` backed, published extensions can declare publication relations for Postgres-backed execution, and config-driven publication definitions can include those relation keys during promotion; export formats and remaining mart endpoints are still pending)

**Acceptance criteria:**
- `GET /reports/{mart_name}` returns mart data with query parameters for date range and filters.
- `GET /contracts/publication-index` returns a semantic publication retrieval view with query/filter support and key-based lookup.
- Response supports JSON format; CSV and Parquet export via `Accept` header or query parameter (Phase 2).
- Each mart from PLT-12 has a corresponding API endpoint.
- Tests verify response content from known fixture data.

**Dependencies:** PLT-12

---

### APP-04: REST API — admin endpoints

**Description:** Admin endpoints for managing sources, contracts, mappings, schedules, and users. Require elevated authentication.

**Rationale:** Operational management through API enables both UI administration and scripted configuration.

**Phase:** 4
**Status:** in-progress (CRUD-style config endpoints now include create plus update flows for source systems, source assets, ingestion definitions, and execution schedules; dataset contracts and column mappings expose archived-version lifecycle plus saved-preview endpoints; source assets, ingestion definitions, and execution schedules now also expose archive/delete lifecycle with dependency checks and `include_archived` read filters; manual schedule-dispatch enqueue is exposed for operator queueing while execution remains worker-owned; control-plane read endpoints expose schedule dispatches, source lineage, publication audit, auth audit, and auth/token operational summary; publication-definition creation rejects unknown built-in or extension relation keys and built-in package/publication mismatches; API and worker startup now sync extension-declared transformation packages and publication definitions into the control plane; local auth, OIDC, and service-token paths now all protect admin/control routes with the shared role model; bootstrap local-user management and service-token lifecycle are available through both the API and the Next.js admin page while `HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN` remains only as a temporary local bypass; admin-only terminal endpoints under `/control/terminal` now expose an allowlisted command manifest and synchronous execution boundary with audit logging instead of host-shell access, including expanded read-only inspection commands for schedules, tokens, auth audit, publication audit, users, source systems, source assets, ingestion definitions, publication definitions, and lineage)

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
**Status:** in-progress (the Next.js shell now covers local login, OIDC sign-in/callback, dashboard, reporting, auth/security admin for local users and service tokens, token expiry/usage summaries, control-plane catalog edit/deactivate flows, execution-control queue actions, and filterable run views; it consumes the API only and replaces the old server-rendered Python dashboard; a parallel `/retro` CRT shell now ships as a route-scoped alternate renderer for the same reporting and control-plane APIs, with dedicated `/retro/money`, `/retro/utilities`, and `/retro/operations` detail routes in addition to the retro overview, and renderer-discovered launcher entries now deep-link into anchored sections on those retro detail pages, but broader product surface work is still pending; `/retro` remains experimental until the web-surface decision gate in `docs/product/retro-crt-shell.md` chooses primary, experimental, or harvest-and-freeze status)

**Acceptance criteria:**
- Dashboard pages render from reporting API data.
- At least: cash-flow trend chart, summary cards, monthly breakdown table.
- UI is responsive on desktop and tablet.
- Built with React/Next.js (replaces current server-rendered HTML).
- Tests verify component rendering with mock API data.
- The default shell remains the canonical product path unless a documented web-surface decision promotes `/retro` or harvests it into the default shell.

**Dependencies:** APP-03

---

### APP-06: Web UI — ingestion run monitoring

**Description:** Users view ingestion run history, status, validation results, and contract failure details.

**Rationale:** Visibility into ingestion status builds trust in the data and enables self-service troubleshooting.

**Phase:** 2
**Status:** implemented (the Next.js shell now exposes run history with dataset/status/date filters plus run-detail views backed by the API, including validation, saved control-plane context, retry actions, transformation audit, source lineage, and publication audit drill-down)

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
**Status:** implemented (the Next.js shell now exposes operator-facing browser uploads for account transactions, subscriptions, contract prices, and config-driven source-asset uploads; a guided upload panel accepts drag/drop files, detects likely source contract targets with confidence, and preselects the matching upload path; it now also runs a no-landing dry-run preview that reports row count, date range, and validation issues with an explicit accept/retry decision gate before upload; successful uploads redirect into run detail, and failed uploads render inline validation, run, and API-error feedback on the upload page)

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
**Status:** implemented (the Next.js admin surface now supports source-system and source-asset create/edit/deactivate flows, ingestion-definition and execution-schedule management, dataset-contract and column-mapping version creation, archive/delete lifecycle for source assets, ingestion definitions, and schedules, archived-version lifecycle for versioned config entities, dependency visibility for archived-but-still-bound config, saved mapping preview against sample CSV through the API, and version diffs plus operational impact summaries for contracts, mappings, and bound assets; a retro `/retro/control/catalog` counterpart now provides a parallel condensed catalog view over the same APIs)

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
**Status:** implemented (the Next.js execution-control view now lists schedules, supports create/edit/pause behavior through the API, can enqueue due or manual schedule dispatches, includes archive/delete lifecycle plus dependency and dispatch-history visibility, surfaces last-run and freshness summaries for assets/definitions/schedules, links into dispatch drill-down, highlights recent failed runs and queue issues, and now also shows worker heartbeats, heartbeat age, stale running-dispatch detection, and recovered stale-dispatch history; a retro `/retro/control/execution` counterpart reuses those same queue and schedule handlers with a denser CRT-style operator layout)

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
**Status:** implemented (JSON-emitting commands cover account ingestion, configured CSV ingestion, ingestion-definition processing, config preflight verification, inbox processing/watch, extension execution, subscription and contract-price ingestion/reporting, utility cost summary reporting, execution-schedule enqueue/list/mark flows, dispatch processing, worker heartbeat listing, stale-dispatch recovery, continuous schedule-dispatch watching with lease renewal and graceful-stop support, control-plane import/export, local-user bootstrap/reset/list operations, and service-token lifecycle operations; the legacy account-transactions inbox commands now bootstrap a persisted compatibility binding into the configured watch-folder flow instead of using a separate worker-only ingestion path)

**Acceptance criteria:**
- All subcommands emit JSON for parseable output.
- Exit codes reflect success/failure.
- Worker can run as a Kubernetes Job with configurable arguments.
- Tests verify CLI argument parsing and output format.

**Dependencies:** none

---

### APP-12: Health endpoints

**Description:** API and web workloads expose `/health` and `/ready` for liveness and readiness probes.

**Rationale:** Kubernetes probes require health endpoints for reliable pod lifecycle management.

**Phase:** 0
**Status:** implemented (API and web both expose `/health` and `/ready`, and the chart plus Compose examples now use `/ready` as the startup contract)

**Acceptance criteria:**
- `GET /health` returns 200 with `{"status": "ok"}` (API) or plain text `ok` (web).
- `GET /ready` returns 200 only after startup configuration validation succeeds.
- Worker health is implicit (process exit code).

**Dependencies:** none

---

### APP-13: External registry administration

**Description:** Admin API and web UI manage external registry sources, synced revisions, activation state, and discovered exports for external pipelines and custom functions.

**Rationale:** If external code remains environment-only, operators cannot safely onboard or rotate GitHub repositories and mounted custom folders through the product's control plane.

**Phase:** 3
**Status:** in-progress (admin API now supports external registry source CRUD, path- and Git-source sync, revision listing, explicit activation, discovered function listing, transformation-handler discovery, publication-key discovery, and update/archive flows for transformation packages plus publication definitions; worker CLI exposes the same lifecycle plus function listing and archived-aware package/publication inspection for operational use; and the admin web catalog now supports creating, editing, syncing, archiving, and activating external registry sources while surfacing loaded custom functions, handler keys, publication keys, transformation packages, and publication definitions for configuration binding and archive/restore workflows)

**Acceptance criteria:**
- Admin API supports create, update, list, archive, sync, validate, and activate operations for external registry sources.
- Admin UI shows source status, resolved revision, validation errors, and discovered extension/function exports before activation.
- Activation is explicit and auditable; the UI does not imply that saving a repository immediately hot-loads code into running requests.
- Existing config flows can browse discovered handler, publication, and function keys from active registry revisions.

**Dependencies:** APP-04, APP-08, PLT-19, SEC-05

---

### APP-14: REST API - auditable action proposals

**Description:** The API exposes a proposal draft surface for approval-gated actions, with read-only listing and detail views, explicit provenance fields, and permission-gated create/approve/dismiss operations.

**Rationale:** Agent- and operator-suggested actions must remain auditable drafts until the existing approval gate resolves them, and the mutate paths need an explicit write permission rather than the generic HA read fallback.

**Phase:** 10
**Status:** in-progress (`POST /api/ha/actions/proposals` now drafts a pending proposal record with source and creator metadata; `GET` read paths remain read-only; approval and dismissal are permission-gated separately from reads; the proposal model is being pinned in API and auth tests)

**Acceptance criteria:**
- `GET /api/ha/actions/proposals` and `GET /api/ha/actions/proposals/{action_id}` remain read-only proposal views.
- `POST /api/ha/actions/proposals` creates a pending proposal without dispatching HA service calls.
- `POST /api/ha/actions/proposals/{action_id}/approve` and `/dismiss` require the proposal write permission and update the stored proposal state.
- Proposal records retain source kind, source key, creator, and metadata fields for auditability.
- Tests verify the proposal draft flow and the permission mapping for create and resolution paths.

**Dependencies:** APP-04, APP-11

---

### APP-15: REST API - domain assistant answer entrypoint

**Description:** The API exposes a narrow read-first assistant query surface over finance, utilities, and operations publications, returning explainable answers with explicit publication and report pointers.

**Rationale:** Agentic and voice surfaces need a controlled query entrypoint that stays grounded in the semantic publication layer and does not bypass reporting or action-safety rails.

**Phase:** 10
**Status:** in-progress (`GET /api/assistant/answer` resolves finance, utilities, or operations questions through the publication index and reporting-service contract, returning explainable answers with publication-index/report-path pointers and evidence snippets; broader multi-turn or write-capable assistant behavior remains out of scope)

**Acceptance criteria:**
- `GET /api/assistant/answer` accepts a question and optional domain hint.
- Response returns a grounded answer plus publication and report pointers.
- The endpoint is read-first and cannot mutate canonical state or dispatch actions.
- Tests verify auth mapping, response shape, and grounding against publication-backed report data.

**Dependencies:** APP-03, APP-14

---

### APP-16: Web UI - contract-driven frontend delivery workflow

**Description:** Stable product-facing UI directions are defined and delivered through repo-tracked intent briefs, token baselines, primitive contracts, scenario coverage, and automated review surfaces instead of prose-only generation.

**Rationale:** Agent-heavy frontend work drifts quickly unless taste, reuse, and validation are all explicit and reviewable.

**Phase:** 4
**Status:** in-progress (the frontend now carries publish-lane contract artifacts for the default and retro shells, generated token CSS, Storybook review surfaces, MSW-backed mock scaffolding, and Playwright plus axe checks against curated stories; raw-style linting, broader story coverage, and the default-versus-retro support decision still remain)

**Acceptance criteria:**
- Each publish-lane UI direction has a repo-tracked `intent.md`, `baseline.tokens.json`, and `ui-contract.yaml`.
- Approved implementations consume the baseline and primitive contracts instead of ad hoc raw style values and one-off components.
- Primitive and screen review surfaces cover default, loading, empty, error, overflow, keyboard, and narrow-width scenarios where applicable.
- Shared mock fixtures or handlers are reusable across component review and browser tests.
- Curated browser checks cover interaction flows, screenshot baselines, and semantic/accessibility drift for stable product surfaces.
- Draft-lane experiments are explicitly marked as draft and do not bypass publish-lane requirements when promoted.
- Parallel shell contracts document whether each shell is primary, experimental, or frozen so publication-backed pages cannot quietly diverge.

**Dependencies:** APP-05

**Notes:** See `docs/product/frontend-ui-delivery-playbook.md`, `apps/web/README.md`, and `apps/web/frontend/ui-contracts/`.

---

### APP-17: REST API - operator-authored policy definitions

**Description:** The API exposes authenticated CRUD for operator-authored policy definitions backed by a persisted policy registry, while built-in HA policy examples remain seeded defaults rather than the exclusive policy catalog.

**Rationale:** Stage 5 has working policy/action plumbing, but it is not a finished operator-facing policy engine until policies can be authored and evaluated without editing Python source.

**Phase:** 4
**Status:** not-started (current `HaPolicyEvaluator` evaluates hardcoded built-in policies in `ha_policy.py`; no persisted `PolicyRegistry`, rule schema, CRUD routes, or runtime registry loading exists yet)

**Acceptance criteria:**
- Operators can create, update, disable, and delete at least one policy definition through authenticated API endpoints.
- Policy definitions are stored in the control plane with lifecycle/provenance metadata and a versioned rule document.
- The rule schema validates publication threshold, freshness threshold, and HA helper-state comparisons without arbitrary code execution.
- Runtime evaluation loads enabled registry policies plus seeded built-ins and produces `PolicyResult` outputs.
- At least one end-to-end test covers create policy -> evaluate policy -> produce `PolicyResult` -> publish the result to HA as synthetic state.

**Dependencies:** APP-04, APP-14, ANA-08

---

## Traceability

| Requirement | Implementation module | Test file |
|---|---|---|
| APP-01 | `apps/api/app.py`, `apps/api/support.py`, `apps/api/routes/ingest_routes.py` | `tests/test_api_app.py` |
| APP-02 | `apps/api/app.py`, `apps/api/support.py`, `apps/api/routes/run_routes.py`, `apps/api/routes/config_routes.py` | `tests/test_api_app.py` |
| APP-03 | `apps/api/app.py`, `apps/api/support.py`, `apps/api/routes/report_routes.py`, `apps/api/routes/contract_routes.py`, `packages/platform/publication_index.py` | `tests/test_api_app.py`, `tests/test_reporting_api_app.py`, `tests/test_utility_domain.py`, `tests/test_local_domain_harness.py`, `tests/test_publication_semantic_index.py` |
| APP-04 | `apps/api/app.py`, `apps/api/auth_runtime.py`, `apps/api/support.py`, `apps/api/runtime_state.py`, `apps/api/routes/auth_routes.py`, `apps/api/routes/config_routes.py`, `apps/api/routes/control_routes.py`, `apps/api/routes/ingest_routes.py` | `tests/test_api_app.py` |
| APP-05 | `apps/web/frontend/app/page.js`, `apps/web/frontend/app/reports/page.js`, `apps/web/frontend/app/control/page.js`, `apps/web/frontend/app/control/catalog/page.js`, `apps/web/frontend/app/control/execution/page.js`, `apps/web/frontend/app/homelab/page.js`, `apps/web/frontend/components/app-shell.js` | `tests/test_web_app.py`, `tests/test_web_auth.py`, `tests/test_architecture_contract.py` |
| APP-06 | `apps/web/frontend/app/runs/page.js`, `apps/web/frontend/app/runs/[runId]/page.js`, `apps/web/frontend/lib/backend.ts` | `tests/test_web_auth.py`, `tests/test_architecture_contract.py` |
| APP-07 | `apps/api/routes/ingest_routes.py`, `packages/pipelines/upload_detection.py`, `apps/web/frontend/app/upload/page.js`, `apps/web/frontend/components/upload-detection-wizard.js`, `apps/web/frontend/app/upload/*/route.js`, `apps/web/frontend/lib/upload-route.js` | `tests/test_manual_upload_and_preview_api.py`, `tests/test_web_auth.py`, `tests/test_architecture_contract.py` |
| APP-08 | `apps/web/frontend/app/control/catalog/page.js`, `apps/web/frontend/app/control/execution/page.js` | `tests/test_web_auth.py`, `tests/test_architecture_contract.py` |
| APP-09 | — | — |
| APP-10 | `apps/web/frontend/app/control/execution/page.js`, `apps/web/frontend/app/control/execution/schedule-dispatches/route.js` | `tests/test_web_auth.py`, `tests/test_architecture_contract.py`, `tests/test_control_plane_api_app.py` |
| APP-11 | `apps/worker/main.py`, `apps/worker/runtime.py`, `apps/worker/command_handlers.py`, `apps/worker/control_plane.py`, `apps/worker/serialization.py`, `packages/pipelines/config_preflight.py` | `tests/test_worker_cli.py`, `tests/test_control_plane_worker_cli.py`, `tests/test_config_preflight.py`, `tests/test_utility_domain.py`, `tests/test_local_domain_harness.py` |
| APP-12 | `apps/api/app.py`, `apps/api/support.py`, `apps/api/runtime_state.py`, `apps/web/frontend/app/health/route.js` | `tests/test_api_app.py`, `tests/test_web_app.py` |
| APP-13 | `apps/api/app.py`, `apps/api/models.py`, `apps/api/routes/config_routes.py`, `apps/worker/runtime.py`, `apps/worker/command_parser.py`, `apps/worker/command_handlers.py`, `packages/shared/function_registry.py`, `packages/pipelines/configured_csv_ingestion.py`, `packages/pipelines/promotion_registry.py`, `apps/web/frontend/app/control/catalog/page.js`, `apps/web/frontend/app/control/catalog/transformation-packages/route.js`, `apps/web/frontend/app/control/catalog/publication-definitions/route.js`, `apps/web/frontend/components/external-registry-panel.js`, `apps/web/frontend/components/function-catalog-panel.js`, `apps/web/frontend/components/transformation-catalog-panel.js`, `apps/web/frontend/lib/config-spec.js`, `apps/web/frontend/lib/backend.ts` | `tests/test_api_app.py`, `tests/test_api_main.py`, `tests/test_worker_cli.py`, `tests/test_configured_csv_ingestion.py`, `tests/test_control_plane_worker_cli.py`, `tests/test_web_auth.py` |
| APP-14 | `apps/api/routes/ha_routes.py`, `packages/pipelines/ha_action_proposals.py`, `packages/platform/auth/permission_registry.py`, `packages/platform/auth/scope_authorization.py` | `tests/test_api_app.py`, `tests/test_api_auth.py`, `tests/test_auth_permission_registry.py`, `tests/test_ha_action_proposals.py`, `tests/test_ha_api.py`, `tests/test_ha_action_dispatcher.py` |
| APP-15 | `apps/api/app.py`, `apps/api/response_models.py`, `apps/api/routes/assistant_routes.py`, `packages/platform/auth/scope_authorization.py` | `tests/test_api_app.py`, `tests/test_api_auth.py`, `tests/test_auth_permission_registry.py` |
| APP-16 | `apps/web/frontend/ui-contracts/default-shell/intent.md`, `apps/web/frontend/ui-contracts/default-shell/baseline.tokens.json`, `apps/web/frontend/ui-contracts/default-shell/ui-contract.yaml`, `apps/web/frontend/ui-contracts/retro-shell/intent.md`, `apps/web/frontend/ui-contracts/retro-shell/baseline.tokens.json`, `apps/web/frontend/ui-contracts/retro-shell/ui-contract.yaml`, `apps/web/frontend/scripts/build-ui-tokens.mjs`, `apps/web/frontend/app/generated/ui-tokens.css`, `apps/web/frontend/.storybook/main.ts`, `apps/web/frontend/.storybook/preview.js`, `apps/web/frontend/stories/app-shell.stories.jsx`, `apps/web/frontend/stories/retro-shell.stories.jsx`, `apps/web/frontend/stories/sparkline-chart.stories.jsx`, `apps/web/frontend/stories/mock-status-card.stories.jsx`, `apps/web/frontend/playwright.config.js`, `apps/web/frontend/playwright/storybook-ui.spec.js` | `tests/test_web_ui_contract_tooling.py` |
| APP-17 | `packages/domains/homelab/pipelines/ha_policy.py`, future policy registry store, future policy definition routes | future policy registry/API/e2e tests |
