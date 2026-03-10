# Examples

Environment examples, sample values, and demo fixtures belong here.

Current foundation:

- `compose.yaml` for running API, web, and optional worker containers against a shared local volume
- `make compose-smoke` for a full local startup check of the example stack
- API, web, and worker now reuse the shared `homelab-analytics:latest` image during smoke runs instead of rebuilding separate images
- API and web define explicit container healthchecks against `/health` so Compose and external tooling can observe readiness directly
- API, web, and worker depend on Postgres health and MinIO startup explicitly; that release-ops contract is pinned by the fast test suite
