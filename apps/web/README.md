# Web App

User-facing UI for dashboards, ingestion operations, mapping configuration, and administration.

Current foundation:

- Next.js frontend source lives in `frontend/`
- the frontend consumes the API only and proxies bootstrap login/logout to the API auth endpoints
- `python -m apps.web.main` is now only a thin launcher for the built Next standalone server
- local launcher usage requires `frontend/.next/standalone/server.js`, typically produced by `docker build -f infra/docker/web.Dockerfile ...` or a local `npm run build` inside `frontend/`
