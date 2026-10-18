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
- ``GET  /api/actions/proposals/{action_id}/review`` — operator review model:
  effect, diff-style change preview, cited evidence with trust at draft vs
  now, and caveats

Drafts that cite ``provenance.publication_keys`` without trust fields get the
worst-case trust of those publications stamped server-side, so the proposer
cannot omit (or overstate) what its evidence looked like at draft time.

Resolution rules (shared with the HA approval routes):

- only ``pending`` proposals can be resolved; a second resolution is ``409``
- machine principals (service tokens, machine JWTs) may draft but never
  resolve a proposal (``403``) — approval is a human decision
- approve/dismiss accept an optional ``{"reason": ...}`` body; the resolver,
  how they authenticated, and the reason are recorded on the proposal and in
  its append-only history
- a draft's ``idempotency_key`` replays return the proposal it created; a key
  owned by another drafter, or an ``action_id`` naming a resolved proposal,
  is a ``409`` (drafting can never reopen an operator's decision)

The queue is persisted in the control plane (``action_proposals`` and the
append-only ``action_proposal_events``), so it survives API restarts.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from packages.application.use_cases.agent_proposal_review import (
    build_proposal_review,
    stamp_provenance_trust,
)
from packages.application.use_cases.agent_trust import ConfidenceLookup
from packages.platform.action_proposals import (
    ADAPTER_HOME_ASSISTANT,
    ADAPTER_PLATFORM,
    MACHINE_AUTH_PROVIDERS,
    ActionProposal,
    ActionProposalRegistry,
    ProposalConflictError,
    ProposalProvenance,
    ProposalTransitionError,
)

MAX_RESOLUTION_REASON_LENGTH = 500
# Matches the vuoro invocation envelope's idempotency-key pattern.
IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{8,128}$"


class ProposalProvenanceInputModel(BaseModel):
    publication_keys: list[str] = Field(default_factory=list)
    confidence_verdict_at_draft: str | None = None
    freshness_state_at_draft: str | None = None
    assessed_at: str | None = None


class ProposalProvenanceModel(ProposalProvenanceInputModel):
    trust_source: Literal["server_stamped", "proposer_supplied"] | None = None


class ProposalHistoryEventModel(BaseModel):
    kind: Literal["drafted", "refreshed", "reopened", "approved", "dismissed"]
    at: str
    actor: str | None = None
    reason: str | None = None
    actor_auth_provider: str | None = None


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
    idempotency_key: str | None = None
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
    idempotency_key: str | None = Field(default=None, pattern=IDEMPOTENCY_KEY_PATTERN)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: ProposalProvenanceInputModel | None = None


class ActionProposalListModel(BaseModel):
    proposals: list[ActionProposalModel]


class ProposalEffectModel(BaseModel):
    adapter: str
    kind: Literal["in_registry_only", "release_ha_approval", "adapter_release"]
    summary: str
    external_effect: bool


class ProposalChangeRowModel(BaseModel):
    field: str
    label: str
    before: str | None = None
    after: str | None = None
    changes: bool


class ProposalTrustAtDraftModel(BaseModel):
    confidence_verdict: str | None = None
    freshness_state: str | None = None
    assessed_at: str | None = None


class PublicationTrustModel(BaseModel):
    publication_key: str
    confidence_verdict: str | None = None
    freshness_state: str | None = None
    completeness_pct: int | None = None
    validation_state: str | None = None
    completeness_state: str | None = None
    assessed_at: str | None = None
    guidance: Literal[
        "state_as_current",
        "state_with_caveat",
        "do_not_state_as_current",
        "trust_unknown",
    ]
    guidance_detail: str


class ProposalEvidenceModel(BaseModel):
    publication_key: str
    display_name: str | None = None
    known: bool
    at_draft: ProposalTrustAtDraftModel
    now: PublicationTrustModel | None = None
    contract_path: str | None = None
    lineage_path: str | None = None


class ProposalReviewTrustModel(BaseModel):
    guidance: Literal[
        "state_as_current",
        "state_with_caveat",
        "do_not_state_as_current",
        "trust_unknown",
    ]
    guidance_detail: str
    caveats: list[str] = Field(default_factory=list)


class ActionProposalReviewModel(BaseModel):
    schema_version: str
    proposal: ActionProposalModel
    effect: ProposalEffectModel
    change_preview: list[ProposalChangeRowModel]
    evidence: list[ProposalEvidenceModel]
    trust: ProposalReviewTrustModel


@dataclass(frozen=True)
class ProposalActor:
    """Who is acting on the queue, as the auth layer authenticated them."""

    name: str | None
    auth_provider: str | None


def request_actor(request: Request) -> ProposalActor:
    principal = cast(Any, getattr(request.state, "principal", None))
    if principal is None:
        return ProposalActor(name=None, auth_provider=None)
    return ProposalActor(
        name=cast(str | None, getattr(principal, "username", None)),
        auth_provider=cast(str | None, getattr(principal, "auth_provider", None)),
    )


def resolver_identity(request: Request) -> ProposalActor:
    """Identity recorded as the resolver of a proposal.

    Raises ``403`` for machine principals: agents and service tokens may
    draft proposals but must never approve or dismiss them, including their
    own. When auth is disabled there is no principal and the resolution is
    recorded without an actor.
    """
    actor = request_actor(request)
    if actor.auth_provider in MACHINE_AUTH_PROVIDERS:
        raise HTTPException(
            status_code=403,
            detail=(
                "Machine principals cannot approve or dismiss proposals; "
                "an operator must resolve them from the control surface."
            ),
        )
    return actor


def resolve_proposal(
    registry: ActionProposalRegistry,
    action_id: str,
    resolution: Literal["approved", "dismissed"],
    *,
    resolver: ProposalActor,
    reason: str | None,
) -> ActionProposal:
    """Apply a resolution, mapping registry errors onto HTTP errors."""
    try:
        if resolution == "approved":
            return registry.approve(
                action_id,
                resolved_by=resolver.name,
                reason=reason,
                actor_auth_provider=resolver.auth_provider,
            )
        return registry.dismiss(
            action_id,
            resolved_by=resolver.name,
            reason=reason,
            actor_auth_provider=resolver.auth_provider,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown approval action.") from exc
    except ProposalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def register_draft(registry: ActionProposalRegistry, **kwargs: Any) -> ActionProposal:
    """Draft through the API: never reopens a resolved proposal (``409``)."""
    try:
        return registry.register(**kwargs, reopen_resolved=False)
    except (ProposalConflictError, ProposalTransitionError) as exc:
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
    publication_names: Mapping[str, str] | None = None,
    confidence_lookup: ConfidenceLookup | None = None,
) -> None:
    """Register the adapter-agnostic proposal queue routes."""
    known_publication_names: Mapping[str, str] = publication_names or {}

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
        source_kind: Literal["policy", "assistant", "operator", "agent"] | None = None,
    ) -> ActionProposalListModel:
        proposals = action_proposal_registry.list_all()
        if status is not None:
            proposals = [proposal for proposal in proposals if proposal.status == status]
        if source_kind is not None:
            proposals = [
                proposal for proposal in proposals if proposal.source_kind == source_kind
            ]
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
        actor = request_actor(request)
        created_by = actor.name or body.created_by or body.source_kind
        provenance = None
        if body.provenance is not None:
            publication_keys = list(body.provenance.publication_keys)
            if publication_keys and confidence_lookup is not None:
                # The platform, not the proposer, records what the cited
                # evidence looked like at draft time.
                stamped = stamp_provenance_trust(publication_keys, confidence_lookup)
                provenance = ProposalProvenance(
                    publication_keys=publication_keys,
                    confidence_verdict_at_draft=stamped["confidence_verdict_at_draft"],
                    freshness_state_at_draft=stamped["freshness_state_at_draft"],
                    assessed_at=stamped["assessed_at"],
                    trust_source="server_stamped",
                )
            else:
                provenance = ProposalProvenance(
                    publication_keys=publication_keys,
                    confidence_verdict_at_draft=body.provenance.confidence_verdict_at_draft,
                    freshness_state_at_draft=body.provenance.freshness_state_at_draft,
                    assessed_at=body.provenance.assessed_at,
                    trust_source="proposer_supplied",
                )
        proposal = register_draft(
            action_proposal_registry,
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
            idempotency_key=body.idempotency_key,
            actor_auth_provider=actor.auth_provider,
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

    @app.get(
        "/api/actions/proposals/{action_id}/review",
        response_model=ActionProposalReviewModel,
    )
    async def review_action_proposal(action_id: str) -> ActionProposalReviewModel:
        proposal = _require_proposal(action_id)
        return ActionProposalReviewModel.model_validate(
            build_proposal_review(
                proposal,
                publication_names=known_publication_names,
                confidence_lookup=confidence_lookup,
            )
        )

    @app.post(
        "/api/actions/proposals/{action_id}/approve",
        response_model=ActionProposalModel,
    )
    async def approve_action_proposal(
        action_id: str,
        request: Request,
        body: ProposalResolutionModel | None = None,
    ) -> ActionProposalModel:
        resolver = resolver_identity(request)
        proposal = require_pending_proposal(action_proposal_registry, action_id)
        await _release_through_adapter(proposal, "approved")
        proposal = resolve_proposal(
            action_proposal_registry,
            action_id,
            "approved",
            resolver=resolver,
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
        resolver = resolver_identity(request)
        proposal = require_pending_proposal(action_proposal_registry, action_id)
        await _release_through_adapter(proposal, "dismissed")
        proposal = resolve_proposal(
            action_proposal_registry,
            action_id,
            "dismissed",
            resolver=resolver,
            reason=body.reason if body is not None else None,
        )
        return ActionProposalModel.model_validate(proposal.to_dict())
