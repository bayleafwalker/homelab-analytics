# Helm Chart

Primary Helm chart for deploying the API, web, and worker workloads for the current bootstrap slice.

Current foundation:

- API `Deployment` and `Service`
- web `Deployment` and `Service`
- worker `Deployment` using the watched-folder polling loop
- shared `ConfigMap`, `ServiceAccount`, and PVC-backed `/data` volume
- per-workload `secretEnvFrom` values so runtime credentials can be referenced by Secret name instead of rendered inline
- `values.runtime-secrets-example.yaml` shows the intended workload split: reporting/bootstrap-auth secrets for API and web, landing/transformation/bootstrap-auth secrets for worker
