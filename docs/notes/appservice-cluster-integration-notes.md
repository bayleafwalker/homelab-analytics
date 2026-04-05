# Appservice Cluster Integration Notes

## Target placement

When this application is ready for deployment, add it to the `appservice` cluster repo as:

- category: `apps`
- service name: `homelab-analytics`
- namespace: `analytics`
- route: `analytics.${DOMAIN_0}` on the internal Gateway

Expected cluster path:

```text
clusters/main/kubernetes/apps/homelab-analytics/
├── ks.yaml
└── app/
    ├── kustomization.yaml
    ├── namespace.yaml
    ├── helm-release.yaml
    ├── gateway-api-routes.yaml
    ├── pvc.yaml
    ├── secret or external secret manifest
    ├── networkpolicy.yaml
    └── gatus-external.yaml
```

## Cluster assumptions

- Flux manages manifests from `clusters/main/kubernetes`
- Gateway API is the preferred HTTP exposure model
- Authentik should protect the UI initially
- simple local username/password auth can exist as a bootstrap fallback before OIDC is enabled
- CloudNativePG is already present for Postgres-backed apps
- Longhorn-backed PVCs are available for local cache or workspace data
- External Secrets Operator or SOPS-managed Secrets should provide provider credentials and OIDC secrets
- Loki, Prometheus, and `gatus` can be used for logging, metrics, and uptime checks

## Recommended service shape

Deploy one Helm chart containing:

- `api`
- `worker`
- `web`
- optional `scheduler`
- optional `redis`

Keep ingress disabled in chart values unless there is a strong reason to manage Gateway API resources in-chart.

## Persistence guidance

Use three tiers:

1. blob/object store for raw files and immutable snapshots
2. DuckDB or SQLite on PVC for local staging and analytic working sets
3. CNPG/Postgres for metadata, schedules, auth-related state, and curated published data

Landing validation results should be stored in Postgres even when payloads themselves live in blob storage.

## First cluster rollout

Start with:

- one `web` replica
- one `api` replica
- one `worker` replica
- CNPG enabled
- SOPS-managed blob credentials
- internal-only Gateway route

Defer:

- public webhooks
- multi-tenant RBAC
- notebook runtime
- GPU workloads
- more complex queueing

## Follow-up hardening

- Authentik OIDC or forward auth
- `gatus` availability check
- Prometheus metrics
- CNPG backup and restore drill
- optional VolSync for any expensive-to-rebuild workspace PVCs
