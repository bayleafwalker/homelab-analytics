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

Resolution rules (shared with the HA approval routes):

- only ``pending`` proposals can be resolved; a second resolution is ``409``
- machine principals (service tokens, machine JWTs) may draft but never
  resolve a proposal (``403``) — approval is a human decision
- approve/dismiss accept an optional ``{"reason": ...}`` body; the resolver
  and reason are recorded on the proposal and in its append-only history
"""
from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from packages.platform.action_proposals import (
    ADAPTER_HOME_ASSISTANT,
    ADAPTER_PLATFORM,
    MACHINE_AUTH_PROVIDERS,
    ActionProposal,
    ActionProposalRegistry,
    ProposalProvenance,
    ProposalTransitionError,
)

MAX_RESOLUTION_REASON_LENGTH = 500


class ProposalProvenanceModel(BaseModel):
    publication_keys: list[str] = Field(default_factory=list)
    confidence_verdict_at_draft: str | None = None
    freshness_state_at_draft: str | None = None
    assessed_at: str | None = None


class ProposalHistoryEventModel(BaseModel):
    kind: Literal["drafted", "refreshed", "approved", "dismissed"]
    at: str
    actor: str | None = None
    reason: str | None = None


class ProposalResolutionModel(BaseModel):
    reason: str | None = Field(default=None, max_length=MAX_RESOLUTION_REASON_LENGTH)


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
    resolved_by: str | None = None
    resolution_reason: str | None = None
    history: list[ProposalHistoryEventModel] = Field(default_factory=list)


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


def resolver_identity(request: Request) -> str | None:
    """Identity recorded as the resolver of a proposal.

    Raises ``403`` for machine principals: agents and service tokens may
    draft proposals but must never approve or dismiss them, including their
    own. When auth is disabled there is no principal and the resolution is
    recorded without an actor.
    """
    principal = cast(Any, getattr(request.state, "principal", None))
    if principal is None:
        return None
    if getattr(principal, "auth_provider", None) in MACHINE_AUTH_PROVIDERS:
        raise HTTPException(
            status_code=403,
            detail=(
                "Machine principals cannot approve or dismiss proposals; "
                "an operator must resolve them from the control surface."
            ),
        )
    return cast(str | None, getattr(principal, "username", None))


def resolve_proposal(
    registry: ActionProposalRegistry,
    action_id: str,
    resolution: Literal["approved", "dismissed"],
    *,
    resolved_by: str | None,
    reason: str | None,
) -> ActionProposal:
    """Apply a resolution, mapping registry errors onto HTTP errors."""
    try:
        if resolution == "approved":
            return registry.approve(action_id, resolved_by=resolved_by, reason=reason)
        return registry.dismiss(action_id, resolved_by=resolved_by, reason=reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown approval action.") from exc
    except ProposalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def require_pending_proposal(
    registry: ActionProposalRegistry, action_id: str
) -> ActionProposal:
    proposal = registry.get(action_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Unknown approval action.")
    if proposal.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=str(ProposalTransitionError(action_id, proposal.status)),
        )
    return proposal


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
    async def approve_action_proposal(
        action_id: str,
        request: Request,
        body: ProposalResolutionModel | None = None,
    ) -> ActionProposalModel:
        resolved_by = resolver_identity(request)
        proposal = require_pending_proposal(action_proposal_registry, action_id)
        await _release_through_adapter(proposal, "approved")
        proposal = resolve_proposal(
            action_proposal_registry,
            action_id,
            "approved",
            resolved_by=resolved_by,
            reason=body.reason if body is not None else None,
        )
        return ActionProposalModel.model_validate(proposal.to_dict())

    @app.post(
        "/api/actions/proposals/{action_id}/dismiss",
        response_model=ActionProposalModel,
    )
    async def dismiss_action_proposal(
        action_id: str,
        request: Request,
        body: ProposalResolutionModel | None = None,
    ) -> ActionProposalModel:
        resolved_by = resolver_identity(request)
        proposal = require_pending_proposal(action_proposal_registry, action_id)
        await _release_through_adapter(proposal, "dismissed")
        proposal = resolve_proposal(
            action_proposal_registry,
            action_id,
            "dismissed",
            resolved_by=resolved_by,
            reason=body.reason if body is not None else None,
        )
        return ActionProposalModel.model_validate(proposal.to_dict())
