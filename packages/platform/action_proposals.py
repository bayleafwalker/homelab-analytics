"""Adapter-agnostic approval-gated action proposal queue.

Generalized from the HA-only approval queue (Stage 10, agent surfaces).
Any adapter, assistant, or agent submits proposals into this single queue;
approval and dismissal remain the only state transitions that release a
proposal, and execution stays owned by the adapter named on the proposal.

The ``adapter`` field names which adapter must actuate or release the action
once approved. Proposals with ``adapter="home_assistant"`` keep the existing
HA dispatcher release path; other adapters (including ``"platform"`` for
agent-drafted proposals with no external actuation) resolve in-registry only.

``origin`` semantics: ``policy_id``/``policy_name`` identify the proposing
origin — a policy for policy-gated actions, a tool or agent identity for
agent-drafted proposals. The field names are kept for wire compatibility with
the HA approval surface and the web shell.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

ProposalStatus = Literal["pending", "approved", "dismissed"]
ProposalSourceKind = Literal["policy", "assistant", "operator", "agent"]

ADAPTER_HOME_ASSISTANT = "home_assistant"
ADAPTER_PLATFORM = "platform"


@dataclass
class ProposalProvenance:
    """Confidence and freshness evidence captured at proposal draft time.

    Records which publications were consulted, and what trust state they were
    in when the proposal was created. Allows auditors to reconstruct the data
    quality at the moment the proposal was generated.
    """

    publication_keys: list[str] = field(default_factory=list)
    confidence_verdict_at_draft: str | None = None
    freshness_state_at_draft: str | None = None
    assessed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "publication_keys": list(self.publication_keys),
            "confidence_verdict_at_draft": self.confidence_verdict_at_draft,
            "freshness_state_at_draft": self.freshness_state_at_draft,
            "assessed_at": self.assessed_at,
        }


@dataclass
class ActionProposal:
    """A pending approval-gated action request."""

    action_id: str
    policy_id: str
    policy_name: str
    verdict: str
    value: str | None
    notification_id: str
    adapter: str = ADAPTER_HOME_ASSISTANT
    source_kind: ProposalSourceKind = "policy"
    source_key: str | None = None
    source_summary: str | None = None
    created_by: str | None = None
    status: ProposalStatus = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    approved_at: str | None = None
    dismissed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: ProposalProvenance | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "verdict": self.verdict,
            "value": self.value,
            "notification_id": self.notification_id,
            "adapter": self.adapter,
            "source_kind": self.source_kind,
            "source_key": self.source_key,
            "source_summary": self.source_summary,
            "created_by": self.created_by,
            "status": self.status,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "dismissed_at": self.dismissed_at,
            "metadata": dict(self.metadata),
            "provenance": self.provenance.to_dict() if self.provenance is not None else None,
        }


class ActionProposalRegistry:
    """Track pending approval-gated action proposals in memory."""

    def __init__(self) -> None:
        self._proposals: dict[str, ActionProposal] = {}

    def register(
        self,
        *,
        policy_id: str,
        policy_name: str,
        verdict: str,
        value: str | None,
        notification_id: str | None,
        adapter: str = ADAPTER_HOME_ASSISTANT,
        source_kind: ProposalSourceKind = "policy",
        source_key: str | None = None,
        source_summary: str | None = None,
        created_by: str | None = None,
        metadata: dict[str, Any] | None = None,
        action_id: str | None = None,
        provenance: ProposalProvenance | None = None,
    ) -> ActionProposal:
        resolved_action_id = action_id or f"approval_{uuid.uuid4().hex[:12]}"
        resolved_notification_id = notification_id or resolved_action_id
        proposal = ActionProposal(
            action_id=resolved_action_id,
            policy_id=policy_id,
            policy_name=policy_name,
            verdict=verdict,
            value=value,
            notification_id=resolved_notification_id,
            adapter=adapter,
            source_kind=source_kind,
            source_key=source_key,
            source_summary=source_summary,
            created_by=created_by,
            metadata=dict(metadata or {}),
            provenance=provenance,
        )
        self._proposals[resolved_action_id] = proposal
        return proposal

    def approve(self, action_id: str) -> ActionProposal:
        proposal = self._require(action_id)
        proposal.status = "approved"
        proposal.approved_at = datetime.now(UTC).isoformat()
        return proposal

    def dismiss(self, action_id: str) -> ActionProposal:
        proposal = self._require(action_id)
        proposal.status = "dismissed"
        proposal.dismissed_at = datetime.now(UTC).isoformat()
        return proposal

    def get(self, action_id: str) -> ActionProposal | None:
        return self._proposals.get(action_id)

    def list_pending(self) -> list[ActionProposal]:
        return [
            proposal
            for proposal in sorted(
                self._proposals.values(),
                key=lambda proposal: proposal.created_at,
                reverse=True,
            )
            if proposal.status == "pending"
        ]

    def list_all(self) -> list[ActionProposal]:
        return sorted(
            self._proposals.values(),
            key=lambda proposal: proposal.created_at,
            reverse=True,
        )

    def get_status(self) -> dict[str, Any]:
        return {
            "tracked": len(self._proposals),
            "pending": sum(1 for proposal in self._proposals.values() if proposal.status == "pending"),
            "approved": sum(1 for proposal in self._proposals.values() if proposal.status == "approved"),
            "dismissed": sum(1 for proposal in self._proposals.values() if proposal.status == "dismissed"),
        }

    def _require(self, action_id: str) -> ActionProposal:
        proposal = self._proposals.get(action_id)
        if proposal is None:
            raise KeyError(f"Unknown approval action: {action_id}")
        return proposal
