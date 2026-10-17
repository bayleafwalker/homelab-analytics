# Examples

Environment examples, sample values, and demo fixtures belong here.

Current foundation:

- `compose.yaml` for the blessed single-user homelab startup story: API, web, and optional worker containers against a shared local volume, backed by Postgres + MinIO and `secrets/auth-local.env.example`
- `make compose-smoke` for an ephemeral startup check of the example stack; it layers `compose-smoke.override.yaml` to pin a MinIO mirror by digest, while the default `compose.yaml` remains unchanged
- API and worker reuse the shared `homelab-analytics:latest` image; web builds from the dedicated `homelab-analytics-web:latest` Next.js image
- API and web define explicit container healthchecks against `/ready` so Compose and external tooling can observe the startup contract directly
- API, web, and worker depend on Postgres health and MinIO startup explicitly; that release-ops contract is pinned by the fast test suite
- third-party runtime images are pinned to explicit tags, including MinIO, so the example stack does not drift with upstream `latest`
- `secrets/auth-local.env.example` provides example explicit local break-glass auth values for the Compose stack
- `secrets/*.example.yaml` provides example Kubernetes Secret manifests for bootstrap single-DSN database access, workload-scoped API/worker database access, bootstrap local auth, blob storage, OIDC session/provider credentials, and provider API credentials
- `charts/homelab-analytics/values.oidc-ingress-example.yaml` is the blessed shared OIDC startup story; it pairs with the OIDC Secret example and the API/worker/database Secret split
- `secrets/postgres-external-secret.example.yaml` shows the External Secrets Operator path for the bootstrap single-DSN database credential
- `secrets/provider-api-secret.sops.example.yaml` shows the SOPS-encrypted Secret path for Git-managed provider credentials
- `demo-data/` contains the committed synthetic demo bundle plus `manifest.json`

The smoke-only MinIO image is an independently operated ECR mirror of the
`RELEASE.2025-09-07T16-13-09Z` upstream release. Its publisher states that the
copy is unmodified and offers no support; the embedded image labels identify
the release, but do not establish independent provenance or signature
verification. This digest is limited to the ephemeral smoke stack and is not a
production image recommendation. The default compose file keeps its separate
upstream image reference; as checked on 2026-10-17, anonymous manifest lookup
for that Quay reference failed. This smoke override does not repair or qualify
the default compose startup path.

Demo-data notes:

- `demo-data/sources/` contains Finnish-shaped public mock exports for finance sources
- `demo-data/canonical/` contains the current supported seed CSVs used by `seed-demo-data`
- `.samples/` stays local-only and is not part of the public bundle

Useful commands:

```bash
make demo-generate
make demo-seed
docker compose -f infra/examples/compose.yaml --profile worker run --rm \
  -v "$(pwd)/infra/examples/demo-data:/demo-data:ro" \
  worker seed-demo-data --input-dir /demo-data
```
