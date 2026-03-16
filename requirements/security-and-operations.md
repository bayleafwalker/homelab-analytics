# Security and Operations Requirements

## Overview

The platform must handle sensitive financial and personal data securely, deploy reliably on Kubernetes, and be packageable for public release. This covers authentication, secret management, observability, deployment, and release engineering.

---

## Requirements

### SEC-01: Local username/password authentication

**Description:** The platform supports local username/password authentication as the bootstrap mechanism.

**Rationale:** A standalone auth option is required before OIDC infrastructure is available, and as a break-glass fallback.

**Phase:** 4
**Status:** implemented (local-user storage exists in both SQLite and Postgres control-plane backends; API exposes `/auth/login`, `/auth/logout`, `/auth/me`, and admin user-management endpoints with signed session cookies, CSRF protection, and login lockout; auth events are recorded in control-plane audit data; API/web startup now fail fast on incomplete local-auth configuration; the Next.js web shell authenticates through the API; worker CLI can still create/reset/list local users; and bootstrap local-admin creation is now explicitly gated behind `HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN` so local auth remains a deliberate break-glass path)

**Acceptance criteria:**
- Username/password login endpoint issues a signed session cookie or JWT.
- Web UI login page authenticates against the local store.
- At least one admin user can be created during initial setup.
- Passwords are stored hashed (bcrypt or argon2).
- Cookie-authenticated state-changing routes enforce CSRF protection.
- Repeated failed logins trigger a lockout policy with audit visibility.
- Tests verify login, session, and rejection flows.

**Dependencies:** none

---

### SEC-02: OIDC authentication

**Description:** The platform supports OIDC authentication for production deployments, integrating with Authentik, Keycloak, or Dex.

**Rationale:** OIDC provides centralized identity management for multi-service homelab environments.

**Phase:** 4
**Status:** implemented (OIDC settings are now supported through environment variables and Secret-backed runtime config; API/web startup fail fast when OIDC settings are incomplete; the API performs discovery, code exchange, signed callback/session handling, and JWT validation against issuer JWKS; the Next.js web shell proxies OIDC login and callback through the API while keeping the browser-facing auth surface on the web origin; protected API endpoints accept validated OIDC bearer JWTs; and the Helm shared-deployment defaults now assume OIDC rather than local auth)

**Acceptance criteria:**
- OIDC configuration via environment variables or Kubernetes Secret: issuer URL, client ID, client secret, redirect URI.
- Web UI redirects to OIDC provider for login and handles the callback.
- API validates OIDC-issued JWTs on protected endpoints.
- Tests verify token validation against a mock OIDC issuer.

**Dependencies:** SEC-01

---

### SEC-03: Service tokens

**Description:** API tokens for automation consumers (Home Assistant, cron jobs). Tokens are scoped and revocable.

**Rationale:** Automation systems need persistent credentials that do not require interactive login.

**Phase:** 4
**Status:** implemented (service tokens now live in the control plane for both SQLite and Postgres backends with hashed-secret storage, optional expiry, revocation, and last-used metadata; the API authenticates opaque `hst_...` bearer tokens before OIDC JWT validation, enforces route-to-scope checks, records failed-token attempts in auth audit history, exposes admin create/list/revoke endpoints, and exports service-token state gauges through `/metrics`; the Next.js admin page can mint copy-once tokens, show last-used and expiry warnings, and revoke them; and the worker CLI supports create/list/revoke plus snapshot import/export parity)

**Acceptance criteria:**
- Admin can create a named service token with an optional expiry and scope.
- API authenticates requests bearing a valid service token.
- Tokens can be revoked by admin.
- Tests verify token creation, usage, and revocation.

**Dependencies:** SEC-01

---

### SEC-04: Role separation

**Description:** At minimum three roles: read-only dashboard access, ingestion/configuration management, and administrative access.

**Rationale:** Not all household members or automation systems should have full configuration access.

**Phase:** 4
**Status:** implemented (local auth, OIDC, and service tokens now all enforce the shared `reader`, `operator`, and `admin` separation across API and Next.js web routes; cookie-backed identities are role-gated directly, while service tokens layer explicit scopes such as `reports:read`, `runs:read`, `ingest:write`, and `admin:write` on top of the same route model)

**Acceptance criteria:**
- Read-only role can view dashboards and reports but cannot ingest or configure.
- Operator role can trigger ingestion and manage sources.
- Admin role has full access including user and token management.
- Role enforcement is tested across API and web endpoints.

**Dependencies:** SEC-01

---

### SEC-05: Cluster-native secret management

**Description:** All sensitive credentials — provider API keys, database passwords, OIDC client secrets, sync credentials — are managed through cluster-native mechanisms (External Secrets Operator or SOPS-encrypted Secrets). Never stored in checked-in values files.

**Rationale:** Secrets in version control are a security risk. Cluster-native management integrates with GitOps workflows.

**Phase:** 1 (infrastructure pattern), 4 (full implementation)
**Status:** in-progress (architecture and runtime patterns are in place: HTTP ingestion definitions persist secret references instead of raw credential values, runtime secret resolution is supported via environment-backed providers, the Helm chart supports per-workload Secret references with tests that block inline credential rendering, example Secret manifests now exist for bootstrap single-DSN database access, workload-scoped API and worker database access, bootstrap-local-auth, blob, OIDC, and provider credentials, and the repo includes example ExternalSecret and SOPS-managed Secret manifests; cluster wiring is still pending)

**Acceptance criteria:**
- Helm chart values reference Kubernetes Secrets by name, never inline credential values.
- Application configuration stores secret references, not resolved secret values.
- Documentation describes External Secrets Operator and SOPS-based Secret creation.
- At least one example Secret manifest exists for each credential class: bootstrap database, workload-scoped database, bootstrap local auth, blob storage, OIDC, provider API.
- Tests verify that no template output contains hardcoded credentials.

**Dependencies:** none

---

### SEC-06: Credential isolation

**Description:** Credentials are isolated by concern: provider API (per-source), sync (per-source), database (per-workload, least-privilege), OIDC (API/web only).

**Rationale:** Least-privilege credential scoping limits blast radius of credential compromise.

**Phase:** 4
**Status:** implemented (runtime workloads are split by role, deployment surfaces are distinct, secret references remain runtime-resolved, the settings/runtime layer now supports purpose-specific Postgres DSNs with shared-DSN fallback, web remains API-backed without direct database credentials, and the Helm examples now show API and worker database Secrets separated by workload alongside distinct OIDC and blob-storage Secrets)

**Acceptance criteria:**
- Worker pods receive only worker-scoped database credentials plus landing/transformation/blob credentials.
- API pods receive only API-scoped database credentials plus auth/session/blob credentials.
- Web pods receive only auth/session configuration and API origin settings.
- Helm values support separate Secret references per workload.

**Dependencies:** SEC-05

---

### OPS-01: Docker images

**Description:** Docker images published for API, worker, and web workloads, with workload-appropriate runtimes.

**Rationale:** Container images are the deployment unit for Kubernetes and Compose.

**Phase:** 0
**Status:** implemented (API and worker ship from the shared Python image, while web now ships from a dedicated Next.js/Node image with a standalone build)

**Acceptance criteria:**
- `docker build -f infra/docker/Dockerfile` produces a working API/worker image.
- `docker build -f infra/docker/web.Dockerfile` produces a working web image.
- API and worker run from the shared Python image via CMD or entrypoint override.
- Web runs from a dedicated Node/Next standalone image.

**Dependencies:** none

---

### OPS-02: Docker Compose development

**Description:** Compose configuration for local development without Kubernetes.

**Rationale:** Developers and early testers need a low-friction local environment.

**Phase:** 0
**Status:** implemented (Compose now boots API, web, Postgres, and MinIO by default, with the worker available via profile and now defaulting to the continuous schedule-dispatch watcher over the shared data volume; that watcher now renews active dispatch leases, recovers expired stale dispatches, and writes heartbeat state that the API exports as operational metrics; API and worker now use the purpose-specific Postgres DSN environment variables while local Compose still points them at the same bootstrap role; and the workloads use Postgres for control-plane state and published reporting plus MinIO for landing storage)

**Acceptance criteria:**
- `docker compose up` starts API, web, and worker.
- Compose includes Postgres and MinIO for Phase 1+ development.
- Compose works without Kubernetes.

**Dependencies:** OPS-01

---

### OPS-03: Helm chart

**Description:** Single Helm chart deploys API, web, and worker workloads with configurable values for Postgres, S3, ingress, and auth.

**Rationale:** Helm is the standard Kubernetes packaging format and the planned release vehicle.

**Phase:** 0–1
**Status:** implemented (the chart now covers API, web, and worker workloads, PVC, configmap, service account, parsed manifest contract tests, per-workload Secret-reference wiring, optional web ingress with TLS support, optional PrometheusRule rendering for operational alerts, and the worker deployment now defaults to the continuous schedule-dispatch watcher with lease-renewal and stale-dispatch recovery behavior in the runtime)

**Acceptance criteria:**
- `helm lint` and `helm template` pass.
- Chart renders Deployment, Service, ConfigMap, PVC, and ServiceAccount resources.
- Values support: image tag, replica count, resource limits, Postgres connection, S3 endpoint, ingress toggle, and alert-rule toggle.
- Tests verify rendered resource names and structure.

**Dependencies:** none

---

### OPS-04: Public release readiness

**Description:** Repository is structured and documented for public release via GitHub or Forgejo. Helm charts are publishable as chart packages.

**Rationale:** The stated end goal is a generalizable product available for community use.

**Phase:** 4
**Status:** not-started

**Acceptance criteria:**
- README is sufficient for a new user to understand, install, and configure the platform.
- Helm chart is publishable via `helm package` and a chart repository.
- Docker images are publishable to GHCR or a similar registry.
- LICENSE file exists.
- CONTRIBUTING guide exists.

**Dependencies:** OPS-01, OPS-03

---

### OPS-05: CI/CD pipeline

**Description:** Automated test, build, and publish pipeline using GitHub Actions.

**Rationale:** Automated quality gates prevent regressions and enable reliable releases.

**Phase:** 4
**Status:** in-progress (blocking verify-fast CI, Docker build smoke, and advisory dependency audit are implemented; publish-on-tag release steps and README badges are still pending)

**Acceptance criteria:**
- Push to main runs `pytest` and `helm lint`.
- Tag push builds and pushes Docker images.
- Tag push packages and publishes Helm chart.
- Pipeline status badge in README.

**Dependencies:** OPS-01, OPS-03

---

### OPS-06: Prometheus metrics exposure

**Description:** Workloads expose Prometheus-compatible metrics: ingestion run counts, validation failure rates, processing duration, queue depth.

**Rationale:** Metrics enable operational monitoring and alerting through existing cluster Prometheus.

**Phase:** 4
**Status:** implemented (API and web workloads expose `/metrics`, runtime code now emits Prometheus-compatible ingestion counters, failure counters, cumulative duration, queue-depth gauges, worker heartbeat/stale-dispatch gauges, auth-failure counters, and service-token lifecycle gauges, and the chart can now render example PrometheusRule alerts against those signals)

**Acceptance criteria:**
- `/metrics` endpoint returns Prometheus text format.
- At least: `ingestion_runs_total`, `ingestion_failures_total`, `ingestion_duration_seconds`, `worker_queue_depth`.
- Metrics are scrapeable by Prometheus via ServiceMonitor or annotation.

**Dependencies:** none

---

### OPS-07: Structured logging

**Description:** All workloads use structured JSON logging for integration with Loki or similar log aggregation.

**Rationale:** Structured logs enable efficient searching, filtering, and correlation in centralized log systems.

**Phase:** 2
**Status:** implemented (API, web, and worker workloads now use structured JSON logging, including request/command context fields instead of ad hoc startup prints)

**Acceptance criteria:**
- Log entries are JSON objects with: timestamp, level, logger, message, and structured context fields.
- Ingestion logs include run_id and dataset.
- API logs include request method, path, status code, and duration.
- No unstructured print statements remain in production code paths.

**Dependencies:** none

---

### OPS-08: Technology stack migration

**Description:** Replace stdlib scaffolding with production dependencies: FastAPI (API), Polars + DuckDB + PyArrow (transform), Postgres (metadata/reporting), React/Next.js (web).

**Rationale:** The current zero-dependency implementation was deliberate for bootstrap. Production use requires real frameworks and engines.

**Phase:** 1–2
**Status:** implemented (FastAPI, DuckDB, Polars/PyArrow, boto3-backed S3 storage, psycopg-backed Postgres metadata/control-plane state, Postgres-backed published-reporting reads/publication, and the Next.js web workload are now in the runtime path)

**Acceptance criteria:**
- FastAPI replaces `wsgiref`-based WSGI app.
- Polars replaces stdlib `csv` for data manipulation.
- DuckDB replaces in-memory computation for analytical queries.
- Postgres adapter passes all existing metadata store tests.
- `pyproject.toml` declares production dependencies.
- Existing tests continue to pass after migration.

**Dependencies:** PLT-14

---

### OPS-09: Backup and restore runbooks

**Description:** Shared deployments document repeatable backup and restore flows for Postgres state, landed object storage, and local warehouse artifacts that still matter operationally.

**Rationale:** Production posture requires recovery steps that can be executed before and after incidents, not just working runtime code.

**Phase:** 4
**Status:** in-progress (operator-facing runbooks now exist for deployment operations plus backup/restore, including Postgres schema dump/restore guidance, control-plane snapshot export/import guidance, S3 mirror examples, DuckDB artifact handling, and post-restore validation steps; automated CronJob packaging and cluster backup wiring are still pending)

**Acceptance criteria:**
- Documentation covers Postgres backup and restore for `control` and `reporting` schemas.
- Documentation covers landed object-storage backup and restore.
- Documentation covers when DuckDB artifacts still need backup or can be rebuilt.
- Post-restore verification steps include readiness, worker visibility, and control-plane validation.

**Dependencies:** OPS-02, OPS-03

---

## Traceability

| Requirement | Implementation module | Test file |
|---|---|---|
| SEC-01 | `packages/shared/auth.py`, `packages/storage/auth_store.py`, `packages/storage/ingestion_config.py`, `packages/storage/postgres_ingestion_config.py`, `packages/storage/sqlite_auth_control_plane.py`, `packages/storage/postgres_auth_control_plane.py`, `apps/api/app.py`, `apps/api/routes/auth_routes.py`, `apps/web/app.py`, `apps/worker/main.py` | `tests/test_api_auth.py`, `tests/test_web_auth.py`, `tests/test_worker_auth_cli.py`, `tests/test_sqlite_auth_store_contract.py`, `tests/test_postgres_auth_store_integration.py` |
| SEC-02 | `packages/shared/auth.py`, `packages/shared/settings.py`, `apps/api/app.py`, `apps/api/routes/auth_routes.py`, `apps/api/main.py`, `apps/web/app.py`, `apps/web/frontend/app/auth/login/route.js`, `apps/web/frontend/app/auth/callback/route.js` | `tests/test_api_oidc.py`, `tests/test_web_auth.py`, `tests/test_settings.py` |
| SEC-03 | `packages/shared/auth.py`, `packages/storage/auth_store.py`, `packages/storage/control_plane.py`, `packages/storage/ingestion_config.py`, `packages/storage/postgres_ingestion_config.py`, `packages/storage/sqlite_auth_control_plane.py`, `packages/storage/postgres_auth_control_plane.py`, `apps/api/app.py`, `apps/api/routes/auth_routes.py`, `apps/web/frontend/app/control/page.js`, `apps/web/frontend/components/service-token-panel.js`, `apps/worker/main.py` | `tests/test_api_auth.py`, `tests/test_api_oidc.py`, `tests/test_worker_auth_cli.py`, `tests/test_control_plane_store_contract.py`, `tests/test_postgres_ingestion_config_integration.py`, `tests/test_web_auth.py` |
| SEC-04 | `packages/shared/auth.py`, `apps/api/app.py`, `apps/api/routes/auth_routes.py`, `apps/api/routes/control_routes.py`, `apps/api/routes/ingest_routes.py`, `apps/api/routes/run_routes.py`, `apps/web/app.py`, `apps/web/frontend/app/control/page.js` | `tests/test_api_auth.py`, `tests/test_api_oidc.py`, `tests/test_web_auth.py`, `tests/test_architecture_contract.py` |
| SEC-05 | `packages/shared/secrets.py`, `packages/storage/ingestion_catalog.py`, `packages/storage/ingestion_config.py`, `packages/pipelines/configured_ingestion_definition.py`, `charts/homelab-analytics/` | `tests/test_ingestion_config_repository.py`, `tests/test_configured_ingestion_definition.py`, `tests/test_helm_chart.py` |
| SEC-06 | `apps/api/main.py`, `apps/web/main.py`, `apps/worker/main.py`, `charts/homelab-analytics/` | `tests/test_helm_chart.py`, `tests/test_project_metadata.py` |
| OPS-01 | `infra/docker/Dockerfile` | `tests/test_project_metadata.py` |
| OPS-02 | `infra/examples/compose.yaml` | `tests/test_project_metadata.py` |
| OPS-03 | `charts/homelab-analytics/` | `tests/test_helm_chart.py` |
| OPS-04 | — | — |
| OPS-05 | `.github/workflows/verify.yaml`, `Makefile` | `tests/test_verification_tooling.py` |
| OPS-06 | `apps/api/app.py`, `apps/api/routes/auth_routes.py`, `apps/api/routes/control_routes.py`, `apps/web/app.py`, `apps/worker/main.py`, `packages/shared/metrics.py` | `tests/test_control_plane_api_app.py`, `tests/test_control_plane_worker_cli.py`, `tests/test_web_app.py` |
| OPS-07 | `packages/shared/logging.py`, `apps/api/main.py`, `apps/web/main.py`, `apps/worker/main.py` | `tests/test_logging.py` |
| OPS-08 | `pyproject.toml`, `apps/api/app.py`, `packages/storage/duckdb_store.py`, `packages/storage/postgres_reporting.py`, `packages/storage/postgres_run_metadata.py`, `packages/storage/s3_blob.py`, `packages/pipelines/transformation_service.py`, `packages/pipelines/reporting_service.py` | `tests/test_project_metadata.py`, `tests/test_blob_store.py`, `tests/test_postgres_reporting_integration.py`, `tests/test_postgres_run_metadata_integration.py`, `tests/test_api_app.py`, `tests/test_reporting_api_app.py`, `tests/test_transformation_service.py` |
| OPS-09 | `docs/runbooks/operations.md`, `docs/runbooks/backup-and-restore.md` | `tests/test_repository_contract.py`, `tests/test_project_metadata.py` |
