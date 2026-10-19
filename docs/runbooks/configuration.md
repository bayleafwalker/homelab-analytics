# Configuration Reference

This document lists all environment variables used by the homelab-analytics platform across API, worker, and web workloads.

Operational support model:

- Postgres is the canonical shared-deployment database for control-plane state, landing metadata, and published reporting.
- SQLite is retained only for local bootstrap and smoke-test convenience.
- DuckDB remains the worker/local-development warehouse engine.

The supported path is the three blessed deployment profiles above. Everything below is either a canonical default for those profiles or an explicit override / compatibility surface for advanced operators.

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

- Use SQLite for local bootstrap convenience only; for shared deployments, Postgres is the canonical control-plane backend. DuckDB serves the warehouse and filesystem serves landing storage.
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

## Supported defaults: data and storage

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_DATA_DIR` | `.local/homelab-analytics` | Local data directory for SQLite bootstrap state, DuckDB warehouse files, and landed payloads |
| `HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH` | `<data_dir>/config.db` | SQLite local control-plane database path override for bootstrap/dev fallback |
| `HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH` | `<data_dir>/analytics/warehouse.duckdb` | DuckDB warehouse path override for worker and local analytical runs |
| `HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE` | `UTC` | IANA timezone name (for example `Europe/Helsinki`) of the household clock. See [Household timezone](#household-timezone). Helm: `household.timezone` |

### Household timezone

Storage stays UTC. Reports that talk about hours of the day or calendar dates are read on the household clock:

- **Spend heatmap** (`GET /reports/spend-heatmap`): the mart `mart_spend_by_weekday_hour` keeps UTC booking dates and UTC hours. Each timed row is converted when the report is read, so its weekday, hour and date follow the zone's offset on that day, including DST. The window and `as_of` are local dates. Date-only bookings keep their booking date. On a spring-forward day the skipped local hour is empty. On a fall-back day both UTC hours that read as the repeated local hour go into it. In zones with a fractional offset (`Asia/Kolkata`, +05:30), a UTC hour is placed in the local hour it starts in, because the mart is hour-grained.
- **Wallboard power** (`GET /api/wallboard/power`): each bucket starts when the household clock reads HH:00 and lasts one real hour. `hour_start` and `hour_end` carry the local offset. Across DST, the skipped hour has no bucket and the repeated hour has two buckets, which are told apart by their offsets. No energy is lost or counted twice.
- **Morning brief** (`GET /api/briefing`): `as_of` is the household date when the brief is generated, and source landing and next-expected dates are household dates. `generated_at` stays an aware UTC timestamp.

Each of these responses carries a `timezone` field naming the zone it used. The API, web and worker processes refuse to start when the value is not a loadable IANA name. The zone database comes from the host's `/usr/share/zoneinfo`, or from the `tzdata` Python package on slim images that do not have one.

## Supported defaults: backend selection

> **Operator note — set this before you start using the platform for real:**
> The default `HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND=sqlite` is intentional for local demo and smoke-test convenience only. For the single-user homelab and shared OIDC profiles, set `HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND=postgres` and provide `HOMELAB_ANALYTICS_POSTGRES_DSN` (or `HOMELAB_ANALYTICS_CONTROL_PLANE_DSN`). Leaving SQLite in place after the demo stage is a support trap: SQLite has no schema evolution guarantee for future migrations and the runtime will warn if a Postgres DSN is present but the backend is still SQLite.

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND` | `sqlite` (demo/dev only) | Control-plane backend for configuration, auth/control metadata, and run-metadata state. `postgres` is the canonical target for all ongoing operator deployments. `sqlite` is retained only for local bootstrap and smoke tests — it is not a feature-parity guarantee for future schema evolution. |
| `HOMELAB_ANALYTICS_REPORTING_BACKEND` | `duckdb` | Reporting read path selector. `duckdb` keeps worker/local warehouse reads available; `postgres` selects published reporting relations for shared app-facing reads. |
| `HOMELAB_ANALYTICS_REPORTING_SNAPSHOT_RETENTION_MONTHS` | `24` | As-of history: reference months of dated snapshots kept per current-only publication (overview, attention items, recent changes, affordability ratios, recurring baseline, subscription summary). Minimum 1. Snapshots are written at publication refresh to the warehouse and, with the Postgres reporting backend, to the published store. Helm: `reporting.snapshotRetentionMonths`. |
| `HOMELAB_ANALYTICS_BLOB_BACKEND` | `filesystem` | Landed payload storage: `filesystem` or `s3` |

Deprecated backend aliases remain supported for compatibility: `HOMELAB_ANALYTICS_CONFIG_BACKEND` and `HOMELAB_ANALYTICS_METADATA_BACKEND`.

When `HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND=sqlite`, the runtime uses one SQLite file (`HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH`, default `<data_dir>/config.db`) for both control-plane state and run metadata. This is the correct posture for local demo runs and CI smoke tests; it is not appropriate for ongoing homelab operation.

Schema-evolution contract:

- Postgres is the canonical control-plane schema target and owns tracked operational migrations in `migrations/postgres`.
- Postgres run-metadata tables use a dedicated migration track in `migrations/postgres_run_metadata`.
- SQLite remains a local/bootstrap fallback path and is not a long-term feature-parity guarantee for control-plane schema evolution.
- DuckDB schema lifecycle remains separate for worker/reporting-store concerns.

## Supported defaults: postgres

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

## Supported defaults: api

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_API_HOST` | `0.0.0.0` | API listen address |
| `HOMELAB_ANALYTICS_API_PORT` | `8080` | API listen port |
| `HOMELAB_ANALYTICS_API_BASE_URL` | `http://127.0.0.1:<api_port>` | Backend API origin used by the Next.js web workload |
| `HOMELAB_ANALYTICS_API_WAREHOUSE_IDLE_SECONDS` | `5` | Close the API's DuckDB warehouse handle after this many idle seconds when no request is in flight (handles are also released at request end) |
| `HOMELAB_ANALYTICS_WAREHOUSE_LOCK_RETRY_ATTEMPTS` | `4` | API warehouse opens retried on a cross-process lock conflict before answering 503 |
| `HOMELAB_ANALYTICS_WAREHOUSE_LOCK_RETRY_BACKOFF_SECONDS` | `0.1` | First retry delay (doubles per attempt) |
| `HOMELAB_ANALYTICS_METRICS_TOKEN` | unset | When set, API and worker `/metrics` require `Authorization: Metrics <token>`; unset keeps them network-internal and unauthenticated. See [slo.md](slo.md) |

## Supported defaults: worker

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_WORKER_ID` | `<hostname>-<pid>` | Stable worker identifier for queue claims and heartbeat records |
| `HOMELAB_ANALYTICS_DISPATCH_LEASE_SECONDS` | `300` | Running-dispatch claim window for stale-dispatch detection |
| `HOMELAB_ANALYTICS_WORKER_METRICS_PORT` | `0` (off) | Port for the worker process `GET /metrics` endpoint (loop heartbeat, dispatch outcomes, refresh durations) |
| `HOMELAB_ANALYTICS_WORKER_METRICS_HOST` | `0.0.0.0` | Listen address for the worker metrics endpoint |
| `HOMELAB_ANALYTICS_BACKUP_INTERVAL_SECONDS` | `0` (off) | Worker-loop scheduled backup interval; `86400` = daily. See [backup-and-restore.md](backup-and-restore.md#scheduled-backups-running-worker) |
| `HOMELAB_ANALYTICS_BACKUP_RETENTION_COUNT` | `7` | Verified bundles kept under the backup directory (minimum 1) |
| `HOMELAB_ANALYTICS_BACKUP_DIR` | `<data_dir>/backups` | Scheduled-backup root; must not be inside the landing root |
| `HOMELAB_ANALYTICS_BATTERY_PLAN_PROFILE` | unset | Path to a JSON profile (`entity_map`, `household_timezone`, optional `decision_months`, `freshness_limit_minutes`) for the read-only Kotiakku battery-plan outcome; unset publishes an `insufficient_evidence` row with remediation. Used by `refresh-battery-plan-outcome` |

## Supported defaults: authentication

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

### Power-user override: trusted proxy mode

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS` | — | Required for `identity_mode=proxy`. Comma-separated source CIDRs whose forwarded identity, address, and scheme headers are trusted. |
| `HOMELAB_ANALYTICS_PROXY_USERNAME_HEADER` | `x-forwarded-user` | Header name used for proxy-authenticated username. |
| `HOMELAB_ANALYTICS_PROXY_ROLE_HEADER` | `x-forwarded-role` | Header name used for proxy-authenticated role (`reader`, `operator`, `admin`). |
| `HOMELAB_ANALYTICS_PROXY_PERMISSIONS_HEADER` | — | Optional comma-separated permission header mapped into in-app authorization grants. |

The architecture direction is external identity by default and in-app authorization semantics. `local_single_user` is the blessed single-user homelab startup story: it requires `HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED=true`, applies TTL-bounded local sessions, enforces internal/CIDR source checks, and surfaces status on `/ready`.

The API only honors `x-forwarded-for` and `x-forwarded-proto` when the immediate TCP peer is in `HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS`. Direct clients cannot use those headers to impersonate an internal source or force secure-cookie behavior.

Web workloads only propagate `HOMELAB_ANALYTICS_IDENTITY_MODE` into the Next.js runtime. Legacy `HOMELAB_ANALYTICS_AUTH_MODE` is stripped before launch so the frontend contract stays on the canonical identity-mode input.

### Compatibility overrides

The following settings are escape hatches or compatibility shims, not required for the blessed deployment profiles.

`packages.shared.auth` is a frozen compatibility shim for legacy consumers and
tests. New runtime code should import `packages.platform.auth.*` and
`packages.shared.auth_modes` directly.

Legacy auth-mode migration policy:
- warning window: `v0.1.x` (fallback allowed but emits `DeprecationWarning`)
- error window: `v0.2.x` (enable `HOMELAB_ANALYTICS_AUTH_MODE_LEGACY_STRICT=true` during rollout to pre-flight this posture now)
- removal target: no earlier than `v0.3.0`
- observability: API metrics expose `auth_legacy_mode_fallback_startups_total`

## Supported defaults: oidc

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_OIDC_ISSUER_URL` | — | OIDC issuer URL, matching the IdP's advertised `issuer` (trailing slash ignored when comparing). Authentik: `https://<authentik>/application/o/<slug>/` |
| `HOMELAB_ANALYTICS_OIDC_DISCOVERY_URL` | `<issuer>/.well-known/openid-configuration` | Optional discovery-document override |
| `HOMELAB_ANALYTICS_OIDC_CLIENT_ID` | — | OIDC client ID |
| `HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET` | — | OIDC client secret (literal). Set this or `_CLIENT_SECRET_REF`, not both |
| `HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET_REF` | — | `<secret_name>/<secret_key>` resolved through the SecretResolver, i.e. the env var `HOMELAB_ANALYTICS_SECRET__<SECRET_NAME>__<SECRET_KEY>` (upper-cased, non-alphanumerics → `_`) |
| `HOMELAB_ANALYTICS_OIDC_REDIRECT_URI` | — | OIDC callback URI (`https://<host>/auth/callback`) |
| `HOMELAB_ANALYTICS_OIDC_JWKS_CACHE_SECONDS` | `3600` | How long discovery metadata and the JWKS stay cached. An unknown `kid` forces one early JWKS refetch (at most every 10 s) so key rotation does not lock users out |
| `HOMELAB_ANALYTICS_OIDC_CLOCK_SKEW_SECONDS` | `60` | Leeway for `exp` / `iat` / `nbf` checks |
| `HOMELAB_ANALYTICS_OIDC_POST_LOGOUT_REDIRECT_URI` | — | Optional `post_logout_redirect_uri` for RP-initiated logout. Logout of an OIDC session returns the IdP's `end_session_endpoint` (with `client_id`) and the web app redirects there; with no advertised endpoint, or discovery failing, logout is local only. Must be registered with the IdP |
| `HOMELAB_ANALYTICS_OIDC_SCOPES` | `openid,profile,email` | Authorization-request scopes |
| `HOMELAB_ANALYTICS_OIDC_API_AUDIENCE` | OIDC client ID | Accepted bearer-token audience for direct API clients |
| `HOMELAB_ANALYTICS_OIDC_USERNAME_CLAIM` | `preferred_username` | Username claim for app principals. It is what proposal history and the decision ledger record as the actor |
| `HOMELAB_ANALYTICS_OIDC_GROUPS_CLAIM` | `groups` | Group claim for role/permission mapping input |
| `HOMELAB_ANALYTICS_OIDC_PERMISSIONS_CLAIM` | — | Optional claim carrying extra app permission grants (comma-separated string or string list) |
| `HOMELAB_ANALYTICS_OIDC_PERMISSION_GROUP_MAPPINGS` | — | Optional group-to-permission mappings (`group=permission[,permission...];group2=permission`) |
| `HOMELAB_ANALYTICS_OIDC_READER_GROUPS` | — | OIDC groups mapped to `reader` role |
| `HOMELAB_ANALYTICS_OIDC_OPERATOR_GROUPS` | — | OIDC groups mapped to `operator` role |
| `HOMELAB_ANALYTICS_OIDC_ADMIN_GROUPS` | — | OIDC groups mapped to `admin` role |

How the `oidc` mode behaves:

- **Flow.** Authorization code with PKCE (S256). `state`, `nonce` and the PKCE verifier travel in the signed, HttpOnly `homelab_analytics_oidc_state` cookie, which lives 10 minutes. Login fails at the start if the IdP advertises `code_challenge_methods_supported` without `S256`.
- **Token endpoint auth.** `client_secret_post` is the default. `client_secret_basic` is used when the IdP advertises only that method.
- **ID token validation.**
  - The signature is checked against the IdP's JWKS, using only asymmetric algorithms (RS/PS/ES*, EdDSA). HMAC (`HS*`) and `none` are refused, and an IdP that advertises only HMAC fails with an explicit error.
  - `iss` must equal the advertised issuer exactly.
  - `aud` must include the client ID (or `HOMELAB_ANALYTICS_OIDC_API_AUDIENCE` for bearer tokens).
  - `exp`, `iat` and `sub` are required. `nonce` must match the login state. When an ID token has several audiences, `azp` must be the client ID.
- **Roles.** The first matching group wins, in the order admin, operator, reader. When role groups are configured, a user in none of them is refused (`/login?error=oidc-unmapped`) unless a permissions claim or a group-to-permission mapping grants them something.
- **Session.** A successful callback issues the app's own signed session cookie (`homelab_analytics_session`, plus the CSRF cookie). Downstream authorization sees `auth_provider="oidc"` and the mapped role. Service tokens keep working in `oidc` mode.
- **Recorded identity.** Proposal drafts and resolutions record the principal's username plus `actor_auth_provider="oidc"` in their history. Decision-ledger records store `actor`, `actor_role`, `actor_auth_provider="oidc"` and `actor_authenticated=true`.
- **Web.** The web container also needs `HOMELAB_ANALYTICS_IDENTITY_MODE=oidc` so `/login` offers the single sign-on button.

Operator enablement against Authentik: `docs/runbooks/oidc-authentik-enablement.md`.

OIDC and trusted-proxy permission grants support canonical static permissions (for example `ingest.write`, `runs.read`) plus asset-scoped grants: `reports.read.publication.<publication_key>`, `runs.read.run.<run_id>`, `runs.retry.run.<run_id>`, `control.source_lineage.read.run.<run_id>`, and `control.publication_audit.read.publication.<publication_key>`. Wildcards are supported as `reports.read.publication.*`, `runs.read.run.*`, `runs.retry.run.*`, `control.source_lineage.read.run.*`, `control.publication_audit.read.publication.*`, and prefix wildcards such as `reports.read.publication.finance.*`.

### Power-user override: machine jwt federation

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
| `HOMELAB_ANALYTICS_MACHINE_JWT_SCOPES_CLAIM` | `scope` | Optional claim with service-token-compatible scopes (`reports:read`, `runs:read`, `ingest:write`, `ha-bridge:ingest`, `admin:write`, `proposals:draft`, `policies:draft`). |

Machine JWT tokens are evaluated by the existing in-app authorization kernel. Scope grants are enforced with the same policy semantics as service tokens for equivalent role/scope combinations. API metrics expose `auth_machine_jwt_authenticated_requests_total` and `auth_machine_jwt_failed_requests_total`, and auth-audit captures `machine_jwt_auth_succeeded`/`machine_jwt_auth_failed` events.

### Agent service-token scopes

A service token's effective permissions are its role's permissions intersected with its scopes' permissions, so the role is a ceiling and the scopes are the grant. For an MCP agent, mint a token with only what it needs:

| Scope | Grants | Minimum token role | Reaches |
|---|---|---|---|
| `reports:read` | `reports.read` | `reader` | semantic index, publications, `GET /api/actions/proposals*` |
| `proposals:draft` | `control.action_proposals.draft` | `operator` | `POST /api/actions/proposals`, `POST /api/ha/actions/proposals` |
| `policies:draft` | `control.policy.draft` | `admin` | `POST /control/policies` only. The draft is stored disabled with `source_kind=agent` |
| `admin:write` | admin config writes, plus everything `proposals:draft` grants | `admin` | `admin:write` satisfies a route that requires `proposals:draft`, but never one that requires `policies:draft` |

No scope lets a token approve, dismiss, enable, edit or delete anything that an agent drafted:

- `POST .../approve` and `POST .../dismiss` need `control.action_proposals.write`. Operators and admins hold it. Every machine principal (`service_token`, `machine_jwt`) gets `403` at the route, whatever scope it carries.
- Resolving a proposal that is already resolved returns `409`.
- Enabling, editing or deleting a policy needs `control.policy.write`, which no scope grants.

Example token for the MCP server: role `operator`, scopes `reports:read,proposals:draft`. Add `policies:draft` with role `admin` only if the agent should draft policies.

### Power-user override: agent surfaces

The MCP tool surface (`python -m apps.agent.mcp_server`) and the operator agent inbox (`/control/agents`) need no configuration. These switches gate the optional agent-facing pieces; every one is off by default. See `docs/plans/2026-10-agentic-ux-and-vuoro-alignment.md`.

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_AGENT_MANIFEST_ENABLED` | `false` | Serve the vuoro-aligned agent capability manifest at `GET /api/agent/manifest` (`404` while disabled). |
| `HOMELAB_ANALYTICS_AGENT_MANIFEST_REPO_ID` | `homelab-analytics` | Repository id the manifest declares (vuoro `repo_id` pattern). |
| `HOMELAB_ANALYTICS_AGENT_AUTHORITY_REPO_UUID` | — | Locally minted authority repo UUID to echo in the manifest. Always reported as `self-asserted` until a vuoro authority issues and validates it. |
| `HOMELAB_ANALYTICS_ASSISTANT_RUNTIME` | `disabled` | AssistantRuntime selector (Stage B2 prototype): `disabled`, `deterministic` (offline fake runtime, no model), or `opencode` (reserved; refused in this build). |
| `HOMELAB_ANALYTICS_ASSISTANT_PROVIDER_CALLS_ALLOWED` | `false` | Second gate required before any runtime that calls an LLM provider may be constructed. |

### Power-user override: extensions

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_EXTENSION_PATHS` | — | Custom import roots for external extension repositories or mounted code paths |
| `HOMELAB_ANALYTICS_EXTENSION_MODULES` | — | Python modules to import and register into the layer extension registry |

### Secret references

| Variable | Default | Description |
|---|---|---|
| `HOMELAB_ANALYTICS_SECRET__<SECRET_NAME>__<SECRET_KEY>` | — | Runtime values for secret references used by HTTP ingestion definitions |

---

### Registry visibility

`GET /control/registry/summary` returns a read-only snapshot of the extension registry state. It is accessible without unsafe-admin credentials and is intended for operator dashboards and health checks.

Response fields: `sources` (configured registry sources and their enabled status), `active_revision` (the currently activated revision id and ref, or `null`), `discovered_handlers` (promotion handler keys loaded at runtime), `publication_keys` (relation names from reporting extensions), `function_keys` (registered function keys), and `loaded_extension_count`.

---

## Kubernetes secret examples

The repository includes example Secret manifests under `infra/examples/secrets/` for the current credential classes: bootstrap single-DSN database access, workload-scoped API and worker database access, bootstrap local auth, blob storage, OIDC, and provider API access.

It also includes an External Secrets Operator example for the bootstrap Postgres DSN and a SOPS-style encrypted Secret example for provider credentials. These are placeholders meant to show intended cluster-managed patterns, not to be applied unchanged.

See `charts/homelab-analytics/values.runtime-secrets-example.yaml` for the intended Secret isolation split between API, web, and worker workloads.
