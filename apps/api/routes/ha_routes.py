"""HA integration API routes — entity state ingest, query, and bridge status.

  POST /api/ha/ingest                        → batch ingest HA state objects
  GET  /api/ha/entities                      → current state per entity (all or filtered)
  GET  /api/ha/entities/{entity_id}/history  → historian log for one entity
  GET  /api/ha/metrics/...                   → reporting-backed REST sensor metrics
  GET  /api/ha/bridge/status                 → WebSocket bridge health (Phase 2)
  GET  /api/ha/mqtt/status                   → MQTT publisher health (Phase 3)
  GET  /api/ha/policies                      → evaluate and return policy verdicts (Phase 4)
  POST /api/ha/policies/evaluate             → force re-evaluate policies (Phase 4)
  GET  /api/ha/actions                       → recent outbound action dispatch log (Phase 5)
  GET  /api/ha/actions/status                → action dispatcher health (Phase 5)
  GET  /api/ha/actions/proposals             → approval-gated action proposals (Phase 6)
  POST /api/ha/actions/proposals             → draft a pending approval proposal
  GET  /api/ha/actions/proposals/{id}         → one approval proposal
  POST /api/ha/actions/proposals/{id}/approve → approve a pending proposal
  POST /api/ha/actions/proposals/{id}/dismiss → dismiss a pending proposal
"""
from __future__ import annotations

from typing import Any, Callable, Literal, cast

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from apps.api.response_models import (
    HaActionsStatusModel,
    HaBridgeStatusModel,
    HaMqttStatusModel,
)
from packages.domains.homelab.pipelines.ha_action_proposals import ApprovalActionRegistry
from packages.pipelines.reporting_service import ReportingService, ScalarMetricSnapshot
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


class HaApprovalProposalModel(BaseModel):
    action_id: str
    policy_id: str
    policy_name: str
    verdict: str
    value: str | None = None
    notification_id: str
    source_kind: Literal["policy", "assistant", "operator"] = "policy"
    source_key: str | None = None
    source_summary: str | None = None
    created_by: str | None = None
    status: str
    created_at: str
    approved_at: str | None = None
    dismissed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HaApprovalProposalCreateModel(BaseModel):
    policy_id: str
    policy_name: str
    verdict: str
    value: str | None = None
    notification_id: str | None = None
    source_kind: Literal["policy", "assistant", "operator"] = "assistant"
    source_key: str | None = None
    source_summary: str | None = None
    created_by: str | None = None
    action_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HaApprovalProposalListModel(BaseModel):
    proposals: list[HaApprovalProposalModel]


class HaMetricValueModel(BaseModel):
    value: float | None
    unit: str


def register_ha_routes(
    app: FastAPI,
    *,
    transformation_service: TransformationService | None,
    reporting_service: ReportingService | None = None,
    ha_bridge: Any | None = None,
    ha_mqtt_publisher: Any | None = None,
    ha_policy_evaluator: Any | None = None,
    ha_action_dispatcher: Any | None = None,
    ha_action_proposal_registry: ApprovalActionRegistry | None = None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    def _reporting() -> ReportingService:
        if reporting_service is not None:
            return reporting_service
        if transformation_service is not None:
            return ReportingService(transformation_service)
        raise HTTPException(
            status_code=503,
            detail="HA metrics require a reporting service.",
        )

    def _metric_response(snapshot: ScalarMetricSnapshot | dict[str, Any]) -> HaMetricValueModel:
        if isinstance(snapshot, dict):
            value = snapshot.get("value")
            unit = str(snapshot.get("unit") or "")
        else:
            value = snapshot.value
            unit = snapshot.unit
        numeric_value = None if value is None else float(value)
        return HaMetricValueModel(value=numeric_value, unit=unit)

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

    @app.get(
        "/api/ha/metrics/current-month/net-cashflow",
        response_model=HaMetricValueModel,
    )
    async def get_current_month_net_cashflow() -> HaMetricValueModel:
        return _metric_response(_reporting().get_current_month_net_cashflow())

    @app.get(
        "/api/ha/metrics/current-month/electricity-cost",
        response_model=HaMetricValueModel,
    )
    async def get_current_month_electricity_cost() -> HaMetricValueModel:
        return _metric_response(_reporting().get_current_month_electricity_cost())

    @app.get(
        "/api/ha/metrics/next-loan-payment",
        response_model=HaMetricValueModel,
    )
    async def get_next_loan_payment_amount() -> HaMetricValueModel:
        return _metric_response(_reporting().get_next_loan_payment_amount())

    @app.get("/api/ha/bridge/status", response_model=HaBridgeStatusModel)
    async def get_bridge_status() -> HaBridgeStatusModel:
        if ha_bridge is None:
            return HaBridgeStatusModel(
                enabled=False,
                connected=False,
                last_sync_at=None,
                reconnect_count=0,
            )
        return HaBridgeStatusModel(enabled=True, **ha_bridge.get_status())

    @app.get("/api/ha/mqtt/status", response_model=HaMqttStatusModel)
    async def get_mqtt_status() -> HaMqttStatusModel:
        if ha_mqtt_publisher is None:
            return HaMqttStatusModel(
                enabled=False,
                connected=False,
                last_publish_at=None,
                publish_count=0,
                entity_count=0,
                static_entity_count=0,
                contract_entity_count=0,
                publication_keys=[],
            )
        return HaMqttStatusModel(enabled=True, **ha_mqtt_publisher.get_status())

    @app.get("/api/ha/policies")
    async def get_policies() -> dict[str, Any]:
        if ha_policy_evaluator is None:
            return {"policies": []}
        results = ha_policy_evaluator.evaluate()
        return {"policies": [r.to_dict() for r in results]}

    @app.get("/api/ha/policies/{policy_id}")
    async def get_policy_by_id(policy_id: str) -> dict[str, Any]:
        if ha_policy_evaluator is None:
            raise HTTPException(status_code=404, detail="Policy evaluator unavailable.")
        results = ha_policy_evaluator.evaluate()
        match = next((r for r in results if r.id == policy_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail="Policy not found.")
        return match.to_dict()

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

    @app.get("/api/ha/actions/status", response_model=HaActionsStatusModel)
    async def get_actions_status() -> HaActionsStatusModel:
        if ha_action_dispatcher is None:
            return HaActionsStatusModel(
                enabled=False,
                connected=False,
                last_dispatch_at=None,
                dispatch_count=0,
                error_count=0,
                action_log_size=0,
                tracked_policies=0,
            )
        return HaActionsStatusModel(enabled=True, **ha_action_dispatcher.get_status())

    def _proposal_registry() -> ApprovalActionRegistry:
        if ha_action_proposal_registry is None:
            raise HTTPException(
                status_code=503,
                detail="HA approval proposal registry is unavailable.",
            )
        return ha_action_proposal_registry

    @app.get("/api/ha/actions/proposals", response_model=HaApprovalProposalListModel)
    async def get_action_proposals() -> HaApprovalProposalListModel:
        registry = _proposal_registry()
        return HaApprovalProposalListModel(
            proposals=[
                HaApprovalProposalModel.model_validate(proposal.to_dict())
                for proposal in registry.list_all()
            ]
        )

    @app.post("/api/ha/actions/proposals", response_model=HaApprovalProposalModel)
    async def create_action_proposal(
        body: HaApprovalProposalCreateModel,
        request: Request,
    ) -> HaApprovalProposalModel:
        registry = _proposal_registry()
        principal = cast(Any, getattr(request.state, "principal", None))
        created_by = (
            getattr(principal, "username", None)
            or body.created_by
            or body.source_kind
        )
        proposal = registry.register(
            policy_id=body.policy_id,
            policy_name=body.policy_name,
            verdict=body.verdict,
            value=body.value,
            notification_id=body.notification_id,
            source_kind=body.source_kind,
            source_key=body.source_key,
            source_summary=body.source_summary,
            created_by=created_by,
            metadata=dict(body.metadata),
            action_id=body.action_id,
        )
        return HaApprovalProposalModel.model_validate(proposal.to_dict())

    @app.get("/api/ha/actions/proposals/{action_id}", response_model=HaApprovalProposalModel)
    async def get_action_proposal(action_id: str) -> HaApprovalProposalModel:
        registry = _proposal_registry()
        proposal = registry.get(action_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Unknown approval action.")
        return HaApprovalProposalModel.model_validate(proposal.to_dict())

    @app.post("/api/ha/actions/proposals/{action_id}/approve", response_model=HaApprovalProposalModel)
    async def approve_action_proposal(action_id: str) -> HaApprovalProposalModel:
        registry = _proposal_registry()
        proposal = registry.get(action_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Unknown approval action.")
        if ha_action_dispatcher is not None:
            record = await ha_action_dispatcher.resolve_approval(proposal, "approved")
            if record.result == "failure":
                raise HTTPException(status_code=502, detail="Failed to release approval notification.")
        try:
            proposal = registry.approve(action_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return HaApprovalProposalModel.model_validate(proposal.to_dict())

    @app.post("/api/ha/actions/proposals/{action_id}/dismiss", response_model=HaApprovalProposalModel)
    async def dismiss_action_proposal(action_id: str) -> HaApprovalProposalModel:
        registry = _proposal_registry()
        proposal = registry.get(action_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Unknown approval action.")
        if ha_action_dispatcher is not None:
            record = await ha_action_dispatcher.resolve_approval(proposal, "dismissed")
            if record.result == "failure":
                raise HTTPException(status_code=502, detail="Failed to release approval notification.")
        try:
            proposal = registry.dismiss(action_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return HaApprovalProposalModel.model_validate(proposal.to_dict())
