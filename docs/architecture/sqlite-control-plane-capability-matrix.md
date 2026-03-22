# SQLite Control-Plane Capability Matrix

This matrix defines what the repository guarantees for the retained SQLite path
compared with the canonical Postgres control-plane path.

## Scope

- Postgres remains the canonical operational control-plane target.
- SQLite remains a local bootstrap and developer convenience fallback.
- DuckDB is intentionally excluded here because it is a warehouse/reporting-store concern, not a control-plane engine.

## Capability Matrix

| Capability | Postgres | SQLite |
|---|---|---|
| Control-plane schema evolution | **Guaranteed** via `migrations/postgres` | **Best-effort** compatibility bootstrap |
| Run metadata schema evolution | **Guaranteed** via `migrations/postgres_run_metadata` | Local bootstrap compatibility path |
| Source/contract/asset catalog CRUD | **Guaranteed** | Supported for local/dev flows |
| Scheduling, dispatch, and worker heartbeat | **Guaranteed** | Supported for local/dev flows |
| Auth and service-token control-plane state | **Guaranteed** | Supported for local/dev and smoke tests |
| Source lineage and publication audit state | **Guaranteed** | Supported for local/dev flows |
| snapshot export/import portability | **Guaranteed portability utility** | **Guaranteed portability utility** |
| New control-plane feature parity timing | Postgres-first by default | No immediate parity commitment |

## Contract Notes

- If a new control-plane feature lands Postgres-first, SQLite may lag until a local-dev use case justifies support.
- Snapshot export/import is the migration and portability aid across backends; it is not a promise of full schema equivalence.
- Shared deployments and production-like paths should use Postgres for control-plane and published reporting concerns.
