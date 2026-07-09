"""Backward-compatible aliases for the platform action proposal queue.

The approval-gated proposal model moved to
``packages.platform.action_proposals`` when the queue was generalized beyond
HA (Stage 10, agent surfaces). HA callers keep importing the original names
from here; new code should import the platform module directly.
"""
from __future__ import annotations

from packages.platform.action_proposals import (
    ADAPTER_HOME_ASSISTANT,
    ADAPTER_PLATFORM,
    ActionProposal,
    ActionProposalRegistry,
    ProposalProvenance,
    ProposalSourceKind,
    ProposalStatus,
)

ApprovalActionProposal = ActionProposal
ApprovalActionRegistry = ActionProposalRegistry

__all__ = [
    "ADAPTER_HOME_ASSISTANT",
    "ADAPTER_PLATFORM",
    "ActionProposal",
    "ActionProposalRegistry",
    "ApprovalActionProposal",
    "ApprovalActionRegistry",
    "ProposalProvenance",
    "ProposalSourceKind",
    "ProposalStatus",
]
