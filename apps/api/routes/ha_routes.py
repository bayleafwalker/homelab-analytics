"""HA integration API routes — entity state ingest and query.

  POST /api/ha/ingest                        → batch ingest HA state objects
  GET  /api/ha/entities                      → current state per entity (all or filtered)
  GET  /api/ha/entities/{entity_id}/history  → historian log for one entity
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from packages.pipelines.transformation_service import TransformationService


class HaStateObject(BaseModel):
    entity_id: str
    state: str
    attributes: dict[str, Any] | None = None
    last_changed: str | None = None
    last_updated: str | None = None


class HaIngestRequest(BaseModel):
    states: list[HaStateObject]
    run_id: str | None = None
    source_system: str | None = None


def register_ha_routes(
    app: FastAPI,
    *,
    transformation_service: TransformationService | None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    def _svc() -> TransformationService:
        if transformation_service is not None:
            return transformation_service
        raise HTTPException(
            status_code=503,
            detail="HA service requires a transformation service.",
        )

    @app.post("/api/ha/ingest")
    async def ingest_ha_states(body: HaIngestRequest) -> dict[str, Any]:
        svc = _svc()
        states = [s.model_dump() for s in body.states]
        count = svc.ingest_ha_states(
            states,
            run_id=body.run_id,
            source_system=body.source_system or "home_assistant",
        )
        return {"ingested": count, "run_id": body.run_id}

    @app.get("/api/ha/entities")
    async def get_ha_entities(
        entity_class: str | None = Query(default=None),
    ) -> dict[str, Any]:
        svc = _svc()
        rows = svc.get_ha_entities()
        if entity_class:
            rows = [r for r in rows if r.get("entity_class") == entity_class]
        return {"rows": to_jsonable(rows)}

    @app.get("/api/ha/entities/{entity_id}/history")
    async def get_ha_entity_history(
        entity_id: str,
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        svc = _svc()
        rows = svc.get_ha_entity_history(entity_id, limit=limit)
        return {"rows": to_jsonable(rows), "limit": limit}
