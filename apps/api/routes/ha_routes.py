"""HA integration API routes — entity state ingest, query, and bridge status.

  POST /api/ha/ingest                        → batch ingest HA state objects
  GET  /api/ha/entities                      → current state per entity (all or filtered)
  GET  /api/ha/entities/{entity_id}/history  → historian log for one entity
  GET  /api/ha/bridge/status                 → WebSocket bridge health (Phase 2)
  GET  /api/ha/mqtt/status                   → MQTT publisher health (Phase 3)
  GET  /api/ha/policies                      → evaluate and return policy verdicts (Phase 4)
  POST /api/ha/policies/evaluate             → force re-evaluate policies (Phase 4)
  GET  /api/ha/actions                       → recent outbound action dispatch log (Phase 5)
  GET  /api/ha/actions/status                → action dispatcher health (Phase 5)
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
    ha_bridge: Any | None = None,
    ha_mqtt_publisher: Any | None = None,
    ha_policy_evaluator: Any | None = None,
    ha_action_dispatcher: Any | None = None,
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

    @app.get("/api/ha/bridge/status")
    async def get_bridge_status() -> dict[str, Any]:
        if ha_bridge is None:
            return {"enabled": False, "connected": False, "last_sync_at": None, "reconnect_count": 0}
        return {"enabled": True, **ha_bridge.get_status()}

    @app.get("/api/ha/mqtt/status")
    async def get_mqtt_status() -> dict[str, Any]:
        if ha_mqtt_publisher is None:
            return {
                "enabled": False,
                "connected": False,
                "last_publish_at": None,
                "publish_count": 0,
                "entity_count": 0,
            }
        return {"enabled": True, **ha_mqtt_publisher.get_status()}

    @app.get("/api/ha/policies")
    async def get_policies() -> dict[str, Any]:
        if ha_policy_evaluator is None:
            return {"policies": []}
        results = ha_policy_evaluator.evaluate()
        return {"policies": [r.to_dict() for r in results]}

    @app.post("/api/ha/policies/evaluate")
    async def evaluate_policies() -> dict[str, Any]:
        if ha_policy_evaluator is None:
            return {"policies": []}
        results = ha_policy_evaluator.evaluate()
        return {"policies": [r.to_dict() for r in results]}

    @app.get("/api/ha/actions")
    async def get_actions(
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, Any]:
        if ha_action_dispatcher is None:
            return {"actions": []}
        return {"actions": ha_action_dispatcher.get_actions(limit=limit)}

    @app.get("/api/ha/actions/status")
    async def get_actions_status() -> dict[str, Any]:
        if ha_action_dispatcher is None:
            return {
                "enabled": False,
                "last_dispatch_at": None,
                "dispatch_count": 0,
                "error_count": 0,
                "action_log_size": 0,
                "tracked_policies": 0,
            }
        return ha_action_dispatcher.get_status()
