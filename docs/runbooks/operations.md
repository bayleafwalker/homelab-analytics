# Operations Runbook

## Deployment shape

The current shared-deployment path is:

- API and worker on the shared Python image
- web on the dedicated Next.js image
- OIDC as the default interactive auth mode
- Postgres for control-plane, metadata, and published reporting state
- S3-compatible object storage for landed payloads

Use `charts/homelab-analytics/values.oidc-ingress-example.yaml` as the starting point for shared environments. It enables:

- `HOMELAB_ANALYTICS_CONFIG_BACKEND=postgres`
- `HOMELAB_ANALYTICS_METADATA_BACKEND=postgres`
- `HOMELAB_ANALYTICS_REPORTING_BACKEND=postgres`
- web ingress with TLS
- `PrometheusRule` rendering for runtime alerts

Required Secret classes for that path:

- `homelab-analytics-api-database`
- `homelab-analytics-worker-database`
- `homelab-analytics-blob-storage`
- `homelab-analytics-auth-oidc`

The web workload is API-backed and should not receive direct database credentials.

## OIDC ingress rollout

1. Create workload Secrets from the examples under `infra/examples/secrets/`.
2. Set the OIDC callback URL to `https://<public-host>/auth/callback`.
3. Render and review:

```bash
helm template homelab-analytics charts/homelab-analytics \
  -f charts/homelab-analytics/values.oidc-ingress-example.yaml
```

4. Deploy or upgrade:

```bash
helm upgrade --install homelab-analytics charts/homelab-analytics \
  -f charts/homelab-analytics/values.oidc-ingress-example.yaml
```

5. Verify:

- `kubectl get ingress,deployment,pods`
- `curl -fsS https://<public-host>/ready`
- `curl -fsS https://<public-host>/api/health` only if ingress also routes API separately outside this chart

## Readiness and health

- `/health` is liveness only.
- `/ready` is the deployment readiness contract for API and web.
- Startup fails fast when `local` or `oidc` auth settings are incomplete.

Initial checks:

```bash
kubectl rollout status deploy/<release>-homelab-analytics-api
kubectl rollout status deploy/<release>-homelab-analytics-web
kubectl logs deploy/<release>-homelab-analytics-api --tail=200
kubectl logs deploy/<release>-homelab-analytics-worker --tail=200
```

If `/ready` fails:

- confirm the expected Secret names are mounted through `secretEnvFrom`
- confirm OIDC issuer, client, redirect URI, and session secret values
- confirm the API/worker Postgres DSNs point at reachable roles and schemas
- confirm blob-storage settings include bucket and credentials when `blob_backend=s3`

## Alert signals

The chart can now render `PrometheusRule` alerts for:

- unavailable API deployment replicas
- unavailable web deployment replicas
- `worker_stale_dispatches`
- `worker_oldest_heartbeat_age_seconds`
- `worker_failed_dispatch_ratio`
- `increase(auth_failures_total[5m])`
- `auth_service_tokens_expiring_7d`

Recommended operator response:

- API/web unavailable:
  inspect `kubectl describe deploy`, `kubectl describe pod`, and `/ready` logs first
- stale dispatches:
  inspect `/control/execution` in the web UI or `python -m apps.worker.main list-schedule-dispatches`
- old worker heartbeat:
  inspect `python -m apps.worker.main list-worker-heartbeats` and worker pod logs
- high auth failures:
  inspect `/control/auth-audit`, reverse-proxy logs, and recent OIDC/provider changes
- expiring service tokens:
  rotate through the `/control` admin page before the seven-day window closes

## Worker recovery steps

When queue execution is degraded:

```bash
python -m apps.worker.main list-worker-heartbeats
python -m apps.worker.main list-schedule-dispatches
python -m apps.worker.main recover-stale-schedule-dispatches
```

The recovery command is safe for expired running claims only. Do not run it as a substitute for normal queue processing.
