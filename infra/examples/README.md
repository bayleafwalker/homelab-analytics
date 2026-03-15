# Examples

Environment examples, sample values, and demo fixtures belong here.

Current foundation:

- `compose.yaml` for running API, web, and optional worker containers against a shared local volume
- `make compose-smoke` for a full local startup check of the example stack
- API and worker reuse the shared `homelab-analytics:latest` image; web builds from the dedicated `homelab-analytics-web:latest` Next.js image
- API and web define explicit container healthchecks against `/health` so Compose and external tooling can observe readiness directly
- API, web, and worker depend on Postgres health and MinIO startup explicitly; that release-ops contract is pinned by the fast test suite
- third-party runtime images are pinned to explicit tags, including MinIO, so the example stack does not drift with upstream `latest`
- `secrets/auth-local.env.example` provides example explicit local break-glass auth values for the Compose stack
- `secrets/*.example.yaml` provides example Kubernetes Secret manifests for database, bootstrap local auth, blob storage, OIDC session/provider credentials, and provider API credentials
- `secrets/postgres-external-secret.example.yaml` shows the External Secrets Operator path for cluster-managed database credentials
- `secrets/provider-api-secret.sops.example.yaml` shows the SOPS-encrypted Secret path for Git-managed provider credentials
