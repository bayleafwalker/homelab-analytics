# Web App

User-facing UI for dashboards, ingestion operations, mapping configuration, and administration.

Current foundation:

- Next.js frontend source lives in `frontend/`
- the frontend consumes the API only and proxies local-login, OIDC login/callback, logout, and control-plane admin forms to the API auth endpoints
- `frontend/lib/backend.ts` is the shared backend transport boundary for server-rendered reads and auth-aware proxy route helpers; new API-consuming read helpers should be added there rather than via page-local backend fetches
- `frontend/lib/renderer-discovery.ts` joins `/contracts/publications` and `/contracts/ui-descriptors` into the current web renderer view model, so report and homelab discovery surfaces do not maintain a second publication registry in page code
- read helpers in `frontend/lib/backend.ts` are typed from the committed generated OpenAPI artifacts under `frontend/generated/`, so backend contract drift should fail in frontend typecheck before it becomes a runtime mismatch
- publication discovery and renderer metadata are generated into `frontend/generated/publication-contracts.ts`, including column-level semantic fields such as `semantic_role`, `unit`, `grain`, and `aggregation`
- `make contract-export-check` now verifies that the committed JSON exports under `frontend/generated/` still match a fresh backend export before frontend codegen/typecheck runs
- the current UI surface now includes dashboard, reports, filterable run history, run detail with lineage/publication drill-down plus retry actions, operator-facing manual uploads with inline failure detail, auth/security admin for local users, auth audit, and service tokens, source catalog edit/deactivate/archive/delete flows, dataset-contract and mapping version management with diff views, mapping preview, external registry source create/sync/activate flows with custom-function discovery, transformation-package and publication-definition create/edit/archive flows with discovered handler/publication key browsing, execution-control schedule/queue/archive actions, dispatch drill-down, operational freshness summaries, and service-token expiry/usage summaries
- `python -m apps.web.main` is now only a thin launcher for the built Next standalone server
- runtime auth mode is passed through as `HOMELAB_ANALYTICS_AUTH_MODE`, so the login page can render either explicit local break-glass credentials or the OIDC sign-in entrypoint without adding product logic to the Python launcher
- local launcher usage requires `frontend/.next/standalone/server.js`, typically produced by `docker build -f infra/docker/web.Dockerfile ...` or a local `npm run build` inside `frontend/`
