"""Adapter-agnostic action proposal queue routes.

Generalizes the HA approval queue (Stage 10, agent surfaces): adapters,
assistants, and agents submit action proposals into the single approval
queue that also gates HA policy actions. Approval and dismissal remain the
only state transitions that release a proposal. Proposals whose ``adapter``
is ``home_assistant`` still release their approval notification through the
HA action dispatcher; other adapters resolve in-registry only.

Routes:

- ``GET  /api/actions/proposals`` — list proposals (optionally by status)
- ``POST /api/actions/proposals`` — draft a proposal into the queue
- ``GET  /api/actions/proposals/{action_id}`` — fetch one proposal
- ``POST /api/actions/proposals/{action_id}/approve`` — approve
- ``POST /api/actions/proposals/{action_id}/dismiss`` — dismiss
"""
from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from packages.platform.action_proposals import (
    ADAPTER_HOME_ASSISTANT,
    ADAPTER_PLATFORM,
    ActionProposal,
    ActionProposalRegistry,
    ProposalProvenance,
)


class ProposalProvenanceModel(BaseModel):
    publication_keys: list[str] = Field(default_factory=list)
    confidence_verdict_at_draft: str | None = None
    freshness_state_at_draft: str | None = None
    assessed_at: str | None = None


class ActionProposalModel(BaseModel):
    action_id: str
    policy_id: str
    policy_name: str
    verdict: str
    value: str | None = None
    notification_id: str
    adapter: str = ADAPTER_HOME_ASSISTANT
    source_kind: Literal["policy", "assistant", "operator", "agent"] = "policy"
    source_key: str | None = None
    source_summary: str | None = None
    created_by: str | None = None
    status: str
    created_at: str
    approved_at: str | None = None
    dismissed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: ProposalProvenanceModel | None = None


class ActionProposalCreateModel(BaseModel):
    policy_id: str
    policy_name: str
    verdict: str
    value: str | None = None
    notification_id: str | None = None
    adapter: str = ADAPTER_PLATFORM
    source_kind: Literal["policy", "assistant", "operator", "agent"] = "agent"
    source_key: str | None = None
    source_summary: str | None = None
    created_by: str | None = None
    action_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: ProposalProvenanceModel | None = None


class ActionProposalListModel(BaseModel):
    proposals: list[ActionProposalModel]


def register_action_proposal_routes(
    app: FastAPI,
    *,
    action_proposal_registry: ActionProposalRegistry,
    ha_action_dispatcher: Any | None = None,
) -> None:
    """Register the adapter-agnostic proposal queue routes."""

    async def _release_through_adapter(
        proposal: ActionProposal,
        resolution: Literal["approved", "dismissed"],
    ) -> None:
        # Only HA-adapter proposals carry an HA approval notification that
        # must be released; other adapters resolve in-registry only.
        if proposal.adapter != ADAPTER_HOME_ASSISTANT or ha_action_dispatcher is None:
            return
        record = await ha_action_dispatcher.resolve_approval(proposal, resolution)
        if record.result == "failure":
            raise HTTPException(
                status_code=502,
                detail="Failed to release approval notification.",
            )

    @app.get("/api/actions/proposals", response_model=ActionProposalListModel)
    async def list_action_proposals(
        status: Literal["pending", "approved", "dismissed"] | None = None,
    ) -> ActionProposalListModel:
        proposals = action_proposal_registry.list_all()
        if status is not None:
            proposals = [proposal for proposal in proposals if proposal.status == status]
        return ActionProposalListModel(
            proposals=[
                ActionProposalModel.model_validate(proposal.to_dict())
                for proposal in proposals
            ]
        )

    @app.post("/api/actions/proposals", response_model=ActionProposalModel)
    async def create_action_proposal(
        body: ActionProposalCreateModel,
        request: Request,
    ) -> ActionProposalModel:
        principal = cast(Any, getattr(request.state, "principal", None))
        created_by = (
            getattr(principal, "username", None)
            or body.created_by
            or body.source_kind
        )
        provenance = None
        if body.provenance is not None:
            provenance = ProposalProvenance(
                publication_keys=list(body.provenance.publication_keys),
                confidence_verdict_at_draft=body.provenance.confidence_verdict_at_draft,
                freshness_state_at_draft=body.provenance.freshness_state_at_draft,
                assessed_at=body.provenance.assessed_at,
            )
        proposal = action_proposal_registry.register(
            policy_id=body.policy_id,
            policy_name=body.policy_name,
            verdict=body.verdict,
            value=body.value,
            notification_id=body.notification_id,
            adapter=body.adapter,
            source_kind=body.source_kind,
            source_key=body.source_key,
            source_summary=body.source_summary,
            created_by=created_by,
            metadata=dict(body.metadata),
            action_id=body.action_id,
            provenance=provenance,
        )
        return ActionProposalModel.model_validate(proposal.to_dict())

    def _require_proposal(action_id: str) -> ActionProposal:
        proposal = action_proposal_registry.get(action_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Unknown approval action.")
        return proposal

    @app.get(
        "/api/actions/proposals/{action_id}",
        response_model=ActionProposalModel,
    )
    async def get_action_proposal(action_id: str) -> ActionProposalModel:
        proposal = _require_proposal(action_id)
        return ActionProposalModel.model_validate(proposal.to_dict())

    @app.post(
        "/api/actions/proposals/{action_id}/approve",
        response_model=ActionProposalModel,
    )
    async def approve_action_proposal(action_id: str) -> ActionProposalModel:
        proposal = _require_proposal(action_id)
        await _release_through_adapter(proposal, "approved")
        proposal = action_proposal_registry.approve(action_id)
        return ActionProposalModel.model_validate(proposal.to_dict())

    @app.post(
        "/api/actions/proposals/{action_id}/dismiss",
        response_model=ActionProposalModel,
    )
    async def dismiss_action_proposal(action_id: str) -> ActionProposalModel:
        proposal = _require_proposal(action_id)
        await _release_through_adapter(proposal, "dismissed")
        proposal = action_proposal_registry.dismiss(action_id)
        return ActionProposalModel.model_validate(proposal.to_dict())
