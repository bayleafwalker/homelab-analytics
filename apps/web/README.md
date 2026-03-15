# Web App

User-facing UI for dashboards, ingestion operations, mapping configuration, and administration.

Current foundation:

- Next.js frontend source lives in `frontend/`
- the frontend consumes the API only and proxies bootstrap login/logout plus control-plane admin forms to the API auth endpoints
- the current UI surface now includes dashboard, reports, filterable run history, run detail with lineage/publication drill-down, operator-facing manual uploads with inline failure detail, auth/security admin, source catalog edit/deactivate/archive/delete flows, dataset-contract and mapping version management, mapping preview, and execution-control schedule/queue/archive actions
- `python -m apps.web.main` is now only a thin launcher for the built Next standalone server
- local launcher usage requires `frontend/.next/standalone/server.js`, typically produced by `docker build -f infra/docker/web.Dockerfile ...` or a local `npm run build` inside `frontend/`
