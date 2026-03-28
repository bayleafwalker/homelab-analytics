"""Approval-gated HA action proposal registry.

This module keeps a small in-memory record of approval-gated action proposals
produced from policy results. It is intentionally lightweight: the real Phase 6
execution path still needs a platform action API and HA service integration.
For now, the registry gives the dispatcher a concrete proposal object to track
when a policy result requires approval before actuation.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

ProposalStatus = Literal["pending", "approved", "dismissed"]


@dataclass
class ApprovalActionProposal:
    """A pending approval-gated action request."""

    action_id: str
    policy_id: str
    policy_name: str
    verdict: str
    value: str | None
    notification_id: str
    status: ProposalStatus = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    approved_at: str | None = None
    dismissed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "verdict": self.verdict,
            "value": self.value,
            "notification_id": self.notification_id,
            "status": self.status,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "dismissed_at": self.dismissed_at,
            "metadata": dict(self.metadata),
        }


class ApprovalActionRegistry:
    """Track pending approval-gated action proposals in memory."""

    def __init__(self) -> None:
        self._proposals: dict[str, ApprovalActionProposal] = {}

    def register(
        self,
        *,
        policy_id: str,
        policy_name: str,
        verdict: str,
        value: str | None,
        notification_id: str,
        metadata: dict[str, Any] | None = None,
        action_id: str | None = None,
    ) -> ApprovalActionProposal:
        resolved_action_id = action_id or f"approval_{uuid.uuid4().hex[:12]}"
        proposal = ApprovalActionProposal(
            action_id=resolved_action_id,
            policy_id=policy_id,
            policy_name=policy_name,
            verdict=verdict,
            value=value,
            notification_id=notification_id,
            metadata=dict(metadata or {}),
        )
        self._proposals[resolved_action_id] = proposal
        return proposal

    def approve(self, action_id: str) -> ApprovalActionProposal:
        proposal = self._require(action_id)
        proposal.status = "approved"
        proposal.approved_at = datetime.now(UTC).isoformat()
        return proposal

    def dismiss(self, action_id: str) -> ApprovalActionProposal:
        proposal = self._require(action_id)
        proposal.status = "dismissed"
        proposal.dismissed_at = datetime.now(UTC).isoformat()
        return proposal

    def get(self, action_id: str) -> ApprovalActionProposal | None:
        return self._proposals.get(action_id)

    def list_pending(self) -> list[ApprovalActionProposal]:
        return [
            proposal
            for proposal in sorted(
                self._proposals.values(),
                key=lambda proposal: proposal.created_at,
                reverse=True,
            )
            if proposal.status == "pending"
        ]

    def list_all(self) -> list[ApprovalActionProposal]:
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

    def _require(self, action_id: str) -> ApprovalActionProposal:
        proposal = self._proposals.get(action_id)
        if proposal is None:
            raise KeyError(f"Unknown approval action: {action_id}")
        return proposal
