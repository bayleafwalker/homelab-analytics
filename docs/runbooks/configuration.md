# Configuration Reference

This document lists all environment variables used by the homelab-analytics platform across API, worker, and web workloads.

Operational support model:

- Postgres is the canonical shared-deployment database for control-plane state, landing metadata, and published reporting.
- SQLite is retained only for local bootstrap and smoke-test convenience.
- DuckDB remains the worker/local-development warehouse engine.

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
| `HOMELAB_ANALYTICS_AUTH_MODE` | `disabled` | Legacy compatibility auth mode input. Supports `disabled`, `local`, `local_single_user`, `oidc`, `proxy`. Prefer `HOMELAB_ANALYTICS_IDENTITY_MODE` for new deployments. |
| `HOMELAB_ANALYTICS_IDENTITY_MODE` | falls back to `HOMELAB_ANALYTICS_AUTH_MODE` | Canonical identity mode selector: `disabled`, `local`, `local_single_user`, `oidc`, `proxy`. |
| `HOMELAB_ANALYTICS_SESSION_SECRET` | — | Signed app-session and OIDC state-cookie secret (required when auth is `local` or `oidc`) |
| `HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED` | `false` | Required when identity mode is `local_single_user`; enables temporary emergency local access. |
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

### Trusted proxy mode

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS` | — | Required for `identity_mode=proxy`. Comma-separated source CIDRs whose forwarded identity headers are trusted. |
| `HOMELAB_ANALYTICS_PROXY_USERNAME_HEADER` | `x-forwarded-user` | Header name used for proxy-authenticated username. |
| `HOMELAB_ANALYTICS_PROXY_ROLE_HEADER` | `x-forwarded-role` | Header name used for proxy-authenticated role (`reader`, `operator`, `admin`). |
| `HOMELAB_ANALYTICS_PROXY_PERMISSIONS_HEADER` | — | Optional comma-separated permission header mapped into in-app authorization grants. |

The architecture direction is external identity by default and in-app authorization semantics. `local_single_user` is a break-glass mode: it requires `HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED=true`, applies TTL-bounded local sessions, enforces internal/CIDR source checks, and surfaces status on `/ready`.

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
