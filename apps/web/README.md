# Web App

User-facing UI for dashboards, ingestion operations, mapping configuration, and administration.

Current foundation:

- Next.js frontend source lives in `frontend/`
- the frontend consumes the API only and proxies local-login, OIDC login/callback, logout, and control-plane admin forms to the API auth endpoints
- the current UI surface now includes dashboard, reports, filterable run history, run detail with lineage/publication drill-down plus retry actions, operator-facing manual uploads with inline failure detail, auth/security admin, source catalog edit/deactivate/archive/delete flows, dataset-contract and mapping version management with diff views, mapping preview, execution-control schedule/queue/archive actions, dispatch drill-down, and operational freshness summaries
- `python -m apps.web.main` is now only a thin launcher for the built Next standalone server
- runtime auth mode is passed through as `HOMELAB_ANALYTICS_AUTH_MODE`, so the login page can render either bootstrap local credentials or the OIDC sign-in entrypoint without adding product logic to the Python launcher
- local launcher usage requires `frontend/.next/standalone/server.js`, typically produced by `docker build -f infra/docker/web.Dockerfile ...` or a local `npm run build` inside `frontend/`
