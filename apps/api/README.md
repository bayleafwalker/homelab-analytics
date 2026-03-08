# API App

Control-plane API for sources, contracts, runs, publications, and consumer-facing reporting endpoints.

Current foundation:

- FastAPI app with `health`, `runs`, config, ingestion, and reporting endpoints
- runnable server entrypoint in `python -m apps.api.main`
- OpenAPI docs available at `/docs`
- multipart upload supported on `POST /ingest`
- typed request models back the config/admin JSON routes for clearer OpenAPI schemas
- transformation packages and publication definitions are configurable API resources, not hard-coded runtime switches
- HTTP ingestion definitions store secret references instead of raw header values
- successful manual and configured built-in ingests can auto-promote into DuckDB-backed marts when a transformation service is wired in
- reporting endpoints now include current dimensions, subscription summary, current contract prices, and current electricity prices
