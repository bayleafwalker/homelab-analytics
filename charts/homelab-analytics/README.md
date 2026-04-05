# Helm Chart

Primary Helm chart for deploying the API, web, and worker workloads for the current bootstrap slice.

Current foundation:

- API `Deployment` and `Service`
- web `Deployment` and `Service`
- worker `Deployment` using the continuous schedule-dispatch watcher
- shared `ConfigMap`, `ServiceAccount`, and PVC-backed `/data` volume
- optional web `Ingress` with TLS support
- optional `PrometheusRule` rendering for runtime alerts
- per-workload `secretEnvFrom` values so runtime credentials can be referenced by Secret name instead of rendered inline
- `values.runtime-secrets-example.yaml` shows the intended workload split: API database/blob/OIDC secrets for API, OIDC secrets only for web, and worker database/blob/landing/transformation secrets for the worker
- `values.oidc-ingress-example.yaml` shows the intended shared-deployment path with OIDC, Postgres control-plane/reporting backends, ingress, TLS, and alert rules
