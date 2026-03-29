# Configuration Reference

This document lists all environment variables used by the homelab-analytics platform across API, worker, and web workloads.

Operational support model:

- Postgres is the canonical shared-deployment database for control-plane state, landing metadata, and published reporting.
- SQLite is retained only for local bootstrap and smoke-test convenience.
- DuckDB remains the worker/local-development warehouse engine.

## Blessed deployment profiles

These profiles are the supported startup stories the rest of the docs should point to.

| Profile | Storage posture | Identity posture | Startup story |
|---|---|---|---|
| Local demo/dev | SQLite control plane, DuckDB warehouse, filesystem landing | `disabled` by default; no shared identity required | Generate or seed `infra/examples/demo-data`, then launch the local app/worker entrypoints for disposable demos and fixture validation |
| Single-user homelab | Postgres control plane/reporting, DuckDB warehouse, S3 or MinIO landing | `local_single_user` with `HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED=true` and a session secret | `docker compose -f infra/examples/compose.yaml up` or the equivalent single-node bootstrap path with the local auth example env file |
| Shared OIDC deployment | Postgres control plane/reporting, DuckDB warehouse, S3 landing | `oidc` with external identity provider secrets and no local bootstrap admin by default | Helm chart or cluster deployment using the OIDC ingress example values and secret-backed runtime config |

### Profile playbooks

Use the profile that matches the operator posture you want to support. The freshness workflow, import actions, and admin surfaces should stay aligned with these stories.

#### Local demo/dev

- Prefer SQLite for control-plane bootstrap, DuckDB for the warehouse, and filesystem landing storage.
- Keep identity disabled unless a specific doc or test needs to exercise auth behavior.
- Seed the demo bundle, use disposable fixture sources, and treat freshness state as a validation aid rather than an operational obligation.
- This is the fastest path for local development, docs checks, and UI smoke tests.

#### Single-user homelab

- Prefer Postgres for control-plane and published-reporting state, DuckDB for the warehouse, and S3 or MinIO for landed payloads.
- Use `local_single_user` plus break-glass and a session secret as the default operator posture.
- Use manual exports, watched folders, and freshness badges to drive the next action when a source goes stale.
- This is the profile for a real operator on one machine or one household deployment.

#### Shared OIDC deployment

- Prefer Postgres for control-plane and published-reporting state, DuckDB for the warehouse, and S3 for landed payloads.
- Use `oidc` with secret-backed provider configuration and no local bootstrap admin by default.
- Keep the same freshness model and remediation actions, but enter the admin and upload flows through shared identity.
- This is the profile for shared deployments where multiple operators need the same governed workflow.

---

## Data and storage

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_DATA_DIR` | `.local/homelab-analytics` | Local data directory for SQLite bootstrap state, DuckDB warehouse files, and landed payloads |
| `HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH` | `<data_dir>/config.db` | SQLite local control-plane database path override for bootstrap/dev fallback |
| `HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH` | `<data_dir>/analytics/warehouse.duckdb` | DuckDB warehouse path override for worker and local analytical runs |

## Backend selection

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND` | `sqlite` | Canonical backend selector for control-plane configuration, auth/control metadata, and run-metadata state. `postgres` is the canonical shared-deployment target; `sqlite` is retained for local bootstrap fallback only. |
| `HOMELAB_ANALYTICS_REPORTING_BACKEND` | `duckdb` | Reporting read path selector. `duckdb` keeps worker/local warehouse reads available; `postgres` selects published reporting relations for shared app-facing reads. |
| `HOMELAB_ANALYTICS_BLOB_BACKEND` | `filesystem` | Landed payload storage: `filesystem` or `s3` |

Deprecated backend aliases remain supported for compatibility: `HOMELAB_ANALYTICS_CONFIG_BACKEND` and `HOMELAB_ANALYTICS_METADATA_BACKEND`.

When `HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND=sqlite`, the runtime uses one SQLite file (`HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH`, default `<data_dir>/config.db`) for both control-plane state and run metadata.

Schema-evolution contract:

- Postgres is the canonical control-plane schema target and owns tracked operational migrations in `migrations/postgres`.
- Postgres run-metadata tables use a dedicated migration track in `migrations/postgres_run_metadata`.
- SQLite remains a local/bootstrap fallback path and is not a long-term feature-parity guarantee for control-plane schema evolution.
- DuckDB schema lifecycle remains separate for worker/reporting-store concerns.

## Postgres

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_POSTGRES_DSN` | — | Shared Postgres DSN for the canonical operational database |
| `HOMELAB_ANALYTICS_CONTROL_PLANE_DSN` | falls back to shared DSN | Canonical Postgres DSN override for control-plane configuration, auth/control metadata, and ingestion run metadata |
| `HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN` | falls back to shared DSN | Per-concern override for published reporting reads and refreshes |
| `HOMELAB_ANALYTICS_CONTROL_SCHEMA` | `control` | Postgres schema for control-plane, landing metadata, auth, scheduling, lineage, and run state |
| `HOMELAB_ANALYTICS_REPORTING_SCHEMA` | `reporting` | Postgres schema for published reporting relations |

Deprecated DSN aliases remain supported for compatibility: `HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN` and `HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN`.

Deprecation rollout:
- Runtime now emits `DeprecationWarning` when any legacy alias above is set to a non-empty value.
- Legacy alias removal is planned no earlier than `v0.2.0`.

## S3 / MinIO

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_S3_ENDPOINT_URL` | — | S3-compatible endpoint URL |
| `HOMELAB_ANALYTICS_S3_BUCKET` | — | Landing payload bucket |
| `HOMELAB_ANALYTICS_S3_REGION` | — | S3 region |
| `HOMELAB_ANALYTICS_S3_ACCESS_KEY_ID` | — | S3 access key |
| `HOMELAB_ANALYTICS_S3_SECRET_ACCESS_KEY` | — | S3 secret key |
| `HOMELAB_ANALYTICS_S3_PREFIX` | — | Key prefix within the bucket |

## API

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_API_HOST` | `0.0.0.0` | API listen address |
| `HOMELAB_ANALYTICS_API_PORT` | `8080` | API listen port |
| `HOMELAB_ANALYTICS_API_BASE_URL` | `http://127.0.0.1:<api_port>` | Backend API origin used by the Next.js web workload |

## Worker

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_WORKER_ID` | `<hostname>-<pid>` | Stable worker identifier for queue claims and heartbeat records |
| `HOMELAB_ANALYTICS_DISPATCH_LEASE_SECONDS` | `300` | Running-dispatch claim window for stale-dispatch detection |

## Authentication

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_IDENTITY_MODE` | `disabled` | Canonical identity mode selector: `disabled`, `local`, `local_single_user`, `oidc`, `proxy`. |
| `HOMELAB_ANALYTICS_AUTH_MODE` | `disabled` | Legacy compatibility fallback only when `HOMELAB_ANALYTICS_IDENTITY_MODE` is unset. Supports `disabled`, `local`, `local_single_user`, `oidc`, `proxy`. |
| `HOMELAB_ANALYTICS_AUTH_MODE_LEGACY_STRICT` | `false` | Feature-flagged startup guard. When `true`, startup fails if non-disabled legacy `HOMELAB_ANALYTICS_AUTH_MODE` fallback is used without explicit `HOMELAB_ANALYTICS_IDENTITY_MODE`. |
| `HOMELAB_ANALYTICS_SESSION_SECRET` | — | Signed app-session and OIDC state-cookie secret (required when auth is `local`, `local_single_user`, or `oidc`) |
| `HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED` | `false` | Required when identity mode is `local_single_user`; enables temporary emergency local access for the single-user homelab profile. |
| `HOMELAB_ANALYTICS_BREAK_GLASS_INTERNAL_ONLY` | `true` | When enabled, local break-glass requests are restricted to internal/allowed addresses. |
| `HOMELAB_ANALYTICS_BREAK_GLASS_TTL_MINUTES` | `30` | Lifetime for break-glass activation windows and local break-glass session cookies. |
| `HOMELAB_ANALYTICS_BREAK_GLASS_ALLOWED_CIDRS` | — | Optional CIDR allowlist for break-glass requests (comma-separated). |
| `HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN` | `false` | Must be `true` before local bootstrap credentials are honored |
| `HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_USERNAME` | — | First local admin username (only when local auth mode is enabled and bootstrap is enabled; intended as single-user/break-glass path) |
| `HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_PASSWORD` | — | First local admin password (only when local auth mode is enabled and bootstrap is enabled; intended as single-user/break-glass path) |
| `HOMELAB_ANALYTICS_AUTH_FAILURE_WINDOW_SECONDS` | — | Local-auth login lockout: failure window |
| `HOMELAB_ANALYTICS_AUTH_FAILURE_THRESHOLD` | — | Local-auth login lockout: failure count threshold |
| `HOMELAB_ANALYTICS_AUTH_LOCKOUT_SECONDS` | — | Local-auth login lockout: lockout duration |
| `HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN` | `false` | Temporary dev-only bypass for unauthenticated admin routes (not for shared deployments) |

Legacy auth-mode migration policy:
- warning window: `v0.1.x` (fallback allowed but emits `DeprecationWarning`)
- error window: `v0.2.x` (enable `HOMELAB_ANALYTICS_AUTH_MODE_LEGACY_STRICT=true` during rollout to pre-flight this posture now)
- removal target: no earlier than `v0.3.0`
- observability: API metrics expose `auth_legacy_mode_fallback_startups_total`

### Trusted proxy mode

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS` | — | Required for `identity_mode=proxy`. Comma-separated source CIDRs whose forwarded identity headers are trusted. |
| `HOMELAB_ANALYTICS_PROXY_USERNAME_HEADER` | `x-forwarded-user` | Header name used for proxy-authenticated username. |
| `HOMELAB_ANALYTICS_PROXY_ROLE_HEADER` | `x-forwarded-role` | Header name used for proxy-authenticated role (`reader`, `operator`, `admin`). |
| `HOMELAB_ANALYTICS_PROXY_PERMISSIONS_HEADER` | — | Optional comma-separated permission header mapped into in-app authorization grants. |

The architecture direction is external identity by default and in-app authorization semantics. `local_single_user` is the blessed single-user homelab startup story: it requires `HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED=true`, applies TTL-bounded local sessions, enforces internal/CIDR source checks, and surfaces status on `/ready`.

Web workloads only propagate `HOMELAB_ANALYTICS_IDENTITY_MODE` into the Next.js runtime. Legacy `HOMELAB_ANALYTICS_AUTH_MODE` is stripped before launch so the frontend contract stays on the canonical identity-mode input.

## OIDC

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_OIDC_ISSUER_URL` | — | OIDC discovery issuer URL |
| `HOMELAB_ANALYTICS_OIDC_CLIENT_ID` | — | OIDC client ID |
| `HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET` | — | OIDC client secret |
| `HOMELAB_ANALYTICS_OIDC_REDIRECT_URI` | — | OIDC callback URI |
| `HOMELAB_ANALYTICS_OIDC_SCOPES` | `openid,profile,email` | Authorization-request scopes |
| `HOMELAB_ANALYTICS_OIDC_API_AUDIENCE` | OIDC client ID | Accepted bearer-token audience for direct API clients |
| `HOMELAB_ANALYTICS_OIDC_USERNAME_CLAIM` | — | Username claim for app principals |
| `HOMELAB_ANALYTICS_OIDC_GROUPS_CLAIM` | — | Group claim for role/permission mapping input |
| `HOMELAB_ANALYTICS_OIDC_PERMISSIONS_CLAIM` | — | Optional claim carrying extra app permission grants (comma-separated string or string list) |
| `HOMELAB_ANALYTICS_OIDC_PERMISSION_GROUP_MAPPINGS` | — | Optional group-to-permission mappings (`group=permission[,permission...];group2=permission`) |
| `HOMELAB_ANALYTICS_OIDC_READER_GROUPS` | — | OIDC groups mapped to `reader` role |
| `HOMELAB_ANALYTICS_OIDC_OPERATOR_GROUPS` | — | OIDC groups mapped to `operator` role |
| `HOMELAB_ANALYTICS_OIDC_ADMIN_GROUPS` | — | OIDC groups mapped to `admin` role |

OIDC and trusted-proxy permission grants support canonical static permissions (for example `ingest.write`, `runs.read`) plus asset-scoped grants: `reports.read.publication.<publication_key>`, `runs.read.run.<run_id>`, `runs.retry.run.<run_id>`, `control.source_lineage.read.run.<run_id>`, and `control.publication_audit.read.publication.<publication_key>`. Wildcards are supported as `reports.read.publication.*`, `runs.read.run.*`, `runs.retry.run.*`, `control.source_lineage.read.run.*`, `control.publication_audit.read.publication.*`, and prefix wildcards such as `reports.read.publication.finance.*`.

## Machine JWT federation (optional)

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_MACHINE_JWT_ENABLED` | `false` | Enables optional upstream machine JWT bearer authentication in addition to service tokens. |
| `HOMELAB_ANALYTICS_MACHINE_JWT_ISSUER_URL` | — | Required when machine JWT is enabled. Expected token issuer (`iss`) and discovery base URL. |
| `HOMELAB_ANALYTICS_MACHINE_JWT_JWKS_URL` | — | Optional JWKS override. If unset, runtime attempts issuer discovery (`/.well-known/openid-configuration`) for `jwks_uri`. |
| `HOMELAB_ANALYTICS_MACHINE_JWT_AUDIENCE` | — | Required when machine JWT is enabled. Expected JWT audience (`aud`). |
| `HOMELAB_ANALYTICS_MACHINE_JWT_USERNAME_CLAIM` | `sub` | Claim used for principal username. |
| `HOMELAB_ANALYTICS_MACHINE_JWT_ROLE_CLAIM` | `role` | Optional claim for role ceiling (`reader`, `operator`, `admin`). |
| `HOMELAB_ANALYTICS_MACHINE_JWT_DEFAULT_ROLE` | `reader` | Role used when role claim is absent. |
| `HOMELAB_ANALYTICS_MACHINE_JWT_PERMISSIONS_CLAIM` | — | Optional claim with direct permission grants (string list or comma-separated string). |
| `HOMELAB_ANALYTICS_MACHINE_JWT_SCOPES_CLAIM` | `scope` | Optional claim with service-token-compatible scopes (`reports:read`, `runs:read`, `ingest:write`, `admin:write`). |

Machine JWT tokens are evaluated by the existing in-app authorization kernel. Scope grants are enforced with the same policy semantics as service tokens for equivalent role/scope combinations. API metrics expose `auth_machine_jwt_authenticated_requests_total` and `auth_machine_jwt_failed_requests_total`, and auth-audit captures `machine_jwt_auth_succeeded`/`machine_jwt_auth_failed` events.

## Extensions

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_EXTENSION_PATHS` | — | Custom import roots for external extension repositories or mounted code paths |
| `HOMELAB_ANALYTICS_EXTENSION_MODULES` | — | Python modules to import and register into the layer extension registry |

## Secrets

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_SECRET__<SECRET_NAME>__<SECRET_KEY>` | — | Runtime values for secret references used by HTTP ingestion definitions |

---

## Kubernetes secret examples

The repository includes example Secret manifests under `infra/examples/secrets/` for the current credential classes: bootstrap single-DSN database access, workload-scoped API and worker database access, bootstrap local auth, blob storage, OIDC, and provider API access.

It also includes an External Secrets Operator example for the bootstrap Postgres DSN and a SOPS-style encrypted Secret example for provider credentials. These are placeholders meant to show intended cluster-managed patterns, not to be applied unchanged.

See `charts/homelab-analytics/values.runtime-secrets-example.yaml` for the intended Secret isolation split between API, web, and worker workloads.
