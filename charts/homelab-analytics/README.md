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

## Image pinning

`image.repository`/`image.tag` and `webImage.repository`/`webImage.tag` describe the
tag-based reference used for local and development renders. Cluster deployments
should instead set `image.digest` and `webImage.digest` to the `sha256:...` digest
published by `.github/workflows/publish-images.yaml`; when a digest is set it wins
over the tag, so a moved tag cannot silently change what runs.

## Data volume

The `/data` PVC is mounted into the API and worker workloads, which share the
landing/staging directory. The web workload is a standalone Next.js server that
does not read that directory, so `web.mountData` defaults to `false` and keeps the
web pod off the claim. Set it to `true` only if a deployment genuinely needs the
shared directory in the web pod — with a `ReadWriteOnce` claim that forces the web
pod onto the same node as the API and worker.
