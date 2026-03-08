# Helm Chart

Primary Helm chart for deploying the API, web, and worker workloads for the current bootstrap slice.

Current foundation:

- API `Deployment` and `Service`
- web `Deployment` and `Service`
- worker `Deployment` using the watched-folder polling loop
- shared `ConfigMap`, `ServiceAccount`, and PVC-backed `/data` volume
