# Configuration Reference

This document lists all environment variables used by the homelab-analytics platform across API, worker, and web workloads.

---

## Data and storage

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_DATA_DIR` | `.local/homelab-analytics` | Local data directory for config databases, DuckDB warehouse, and landing payloads |
| `HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH` | `<data_dir>/config.db` | SQLite ingestion-config database path override |
| `HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH` | `<data_dir>/analytics/warehouse.duckdb` | DuckDB warehouse path override |

## Backend selection

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_CONFIG_BACKEND` | `sqlite` | Control-plane backend: `sqlite` or `postgres` |
| `HOMELAB_ANALYTICS_METADATA_BACKEND` | `sqlite` | Ingestion run metadata backend: `sqlite` or `postgres` |
| `HOMELAB_ANALYTICS_REPORTING_BACKEND` | `duckdb` | Published reporting reads: `duckdb` or `postgres` |
| `HOMELAB_ANALYTICS_BLOB_BACKEND` | `filesystem` | Landed payload storage: `filesystem` or `s3` |

## Postgres

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_POSTGRES_DSN` | — | Shared Postgres DSN for control-plane, metadata, and reporting |
| `HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN` | falls back to shared DSN | Per-concern override for control-plane and metadata |
| `HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN` | falls back to shared DSN | Per-concern override for ingestion run metadata |
| `HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN` | falls back to shared DSN | Per-concern override for published reporting reads |
| `HOMELAB_ANALYTICS_CONTROL_SCHEMA` | `control` | Postgres schema for control-plane and metadata state |
| `HOMELAB_ANALYTICS_REPORTING_SCHEMA` | `reporting` | Postgres schema for published reporting relations |

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
| `HOMELAB_ANALYTICS_AUTH_MODE` | `disabled` | Authentication mode (current runtime): `disabled`, `local` (or `local_single_user` alias), or `oidc`; `proxy` is reserved and currently rejected at startup |
| `HOMELAB_ANALYTICS_SESSION_SECRET` | — | Signed app-session and OIDC state-cookie secret (required when auth is `local` or `oidc`) |
| `HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN` | `false` | Must be `true` before local bootstrap credentials are honored |
| `HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_USERNAME` | — | First local admin username (only when `auth_mode=local` and bootstrap enabled; intended as single-user/break-glass path) |
| `HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_PASSWORD` | — | First local admin password (only when `auth_mode=local` and bootstrap enabled; intended as single-user/break-glass path) |
| `HOMELAB_ANALYTICS_AUTH_FAILURE_WINDOW_SECONDS` | — | Local-auth login lockout: failure window |
| `HOMELAB_ANALYTICS_AUTH_FAILURE_THRESHOLD` | — | Local-auth login lockout: failure count threshold |
| `HOMELAB_ANALYTICS_AUTH_LOCKOUT_SECONDS` | — | Local-auth login lockout: lockout duration |
| `HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN` | `false` | Temporary dev-only bypass for unauthenticated admin routes (not for shared deployments) |

The architecture direction is external identity by default and in-app authorization semantics. Current runtime auth mode values remain supported during migration, with `local` treated as compatibility for a narrower `local_single_user` posture.

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
