"""Adapter-agnostic approval-gated action proposal queue.

Generalized from the HA-only approval queue (Stage 10, agent surfaces).
Any adapter, assistant, or agent submits proposals into this single queue;
approval and dismissal remain the only state transitions that release a
proposal, and execution stays owned by the adapter named on the proposal.

Lifecycle: ``pending`` is the only non-terminal state. ``approve`` and
``dismiss`` move a pending proposal to ``approved`` / ``dismissed``; a second
resolution raises :class:`ProposalTransitionError` instead of silently
flipping a decision the operator already made. Every transition appends a
:class:`ProposalHistoryEvent` (drafted, refreshed, reopened, approved,
dismissed) so the audit trail survives re-evaluation refreshes.

Persistence: the registry owns the lifecycle rules and delegates storage to an
:class:`ActionProposalStore`. The control-plane repositories (SQLite and
Postgres) implement the store, so the queue and its append-only history
survive API restarts; :class:`InMemoryActionProposalStore` remains for tests
and for runtimes without a control plane. Every state change is a
compare-and-set on the proposal's current status, so two resolvers racing on
one proposal (two tabs, two API replicas) yield one resolution and one ``409``.

Idempotency: a draft may carry an ``idempotency_key`` (unique across the
queue). Replaying a key returns the proposal it created — refreshed while it
is still pending, untouched once resolved — and never reopens a decision. A
key reused by a different drafter is a conflict.

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

import copy
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

ProposalStatus = Literal["pending", "approved", "dismissed"]
ProposalSourceKind = Literal["policy", "assistant", "operator", "agent"]

ProposalHistoryEventKind = Literal[
    "drafted", "refreshed", "reopened", "approved", "dismissed"
]
ProvenanceTrustSource = Literal["server_stamped", "proposer_supplied"]

ADAPTER_HOME_ASSISTANT = "home_assistant"
ADAPTER_PLATFORM = "platform"

# Principals that authenticate as a machine rather than a person. They may
# draft proposals but never resolve them: approval is a human decision.
MACHINE_AUTH_PROVIDERS = frozenset({"service_token", "machine_jwt"})


class ProposalConflictError(ValueError):
    """Raised when a draft collides with a proposal it may not reuse.

    Examples: an idempotency key already used by another drafter, or a store
    insert that loses a uniqueness race on the action id.
    """


class ProposalTransitionError(ValueError):
    """Raised when a resolution is requested for a non-pending proposal."""

    def __init__(self, action_id: str, status: str) -> None:
        super().__init__(
            f"Proposal {action_id} is already {status}; only pending proposals "
            "can be approved or dismissed."
        )
        self.action_id = action_id
        self.status = status


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ProposalHistoryEvent:
    """One append-only lifecycle event on a proposal."""

    kind: ProposalHistoryEventKind
    at: str
    actor: str | None = None
    reason: str | None = None
    # How the actor authenticated (``local``, ``oidc``, ``proxy``,
    # ``service_token``, ``machine_jwt``). ``None`` when auth is disabled or
    # the actor is an in-process component such as the HA dispatcher.
    actor_auth_provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "at": self.at,
            "actor": self.actor,
            "reason": self.reason,
            "actor_auth_provider": self.actor_auth_provider,
        }


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
    # ``server_stamped`` when the platform looked the trust state up itself at
    # draft time; ``proposer_supplied`` when it had no confidence lookup and
    # kept what the drafter claimed. Reviewers weigh the two differently.
    trust_source: ProvenanceTrustSource | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "publication_keys": list(self.publication_keys),
            "confidence_verdict_at_draft": self.confidence_verdict_at_draft,
            "freshness_state_at_draft": self.freshness_state_at_draft,
            "assessed_at": self.assessed_at,
            "trust_source": self.trust_source,
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
    created_at: str = field(default_factory=_now_iso)
    approved_at: str | None = None
    dismissed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: ProposalProvenance | None = None
    resolved_by: str | None = None
    resolution_reason: str | None = None
    idempotency_key: str | None = None
    history: list[ProposalHistoryEvent] = field(default_factory=list)

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
            "resolved_by": self.resolved_by,
            "resolution_reason": self.resolution_reason,
            "idempotency_key": self.idempotency_key,
            "history": [event.to_dict() for event in self.history],
        }


@runtime_checkable
class ActionProposalStore(Protocol):
    """Persistence port for the proposal queue.

    Implementations return detached copies; state changes go through
    :meth:`insert_action_proposal` and :meth:`update_action_proposal` only.
    History events are append-only: no method edits or deletes one.
    """

    def get_action_proposal(self, action_id: str) -> ActionProposal | None: ...

    def find_action_proposal_by_idempotency_key(
        self, idempotency_key: str
    ) -> ActionProposal | None: ...

    def list_action_proposals(self) -> list[ActionProposal]: ...

    def insert_action_proposal(self, proposal: ActionProposal) -> None:
        """Insert a new proposal and every event in its ``history``.

        Raises :class:`ProposalConflictError` when the action id or the
        idempotency key already exists.
        """
        ...

    def update_action_proposal(
        self,
        proposal: ActionProposal,
        *,
        expected_status: ProposalStatus,
        event: ProposalHistoryEvent | None,
    ) -> bool:
        """Compare-and-set the proposal's mutable fields and append ``event``.

        Applies only while the stored status equals ``expected_status``;
        returns ``False`` (writing nothing) otherwise, or when the proposal
        does not exist. ``action_id`` and ``idempotency_key`` never change.
        """
        ...


def build_action_proposal_registry(store_candidate: object | None) -> ActionProposalRegistry:
    """Registry backed by ``store_candidate`` when it implements the store port.

    The control-plane repositories implement :class:`ActionProposalStore`, so
    the deployed API persists the queue. Anything else (no control plane, a
    test double) falls back to the in-memory store.
    """
    if isinstance(store_candidate, ActionProposalStore):
        return ActionProposalRegistry(store=store_candidate)
    return ActionProposalRegistry()


def sort_proposals(proposals: list[ActionProposal]) -> list[ActionProposal]:
    """Newest first; ties broken by action id so every backend agrees."""
    return sorted(
        sorted(proposals, key=lambda proposal: proposal.action_id),
        key=lambda proposal: proposal.created_at,
        reverse=True,
    )


class InMemoryActionProposalStore:
    """Process-local store for tests and runtimes without a control plane."""

    durable = False

    def __init__(self) -> None:
        self._proposals: dict[str, ActionProposal] = {}
        self._lock = threading.Lock()

    def get_action_proposal(self, action_id: str) -> ActionProposal | None:
        with self._lock:
            proposal = self._proposals.get(action_id)
            return copy.deepcopy(proposal) if proposal is not None else None

    def find_action_proposal_by_idempotency_key(
        self, idempotency_key: str
    ) -> ActionProposal | None:
        with self._lock:
            for proposal in self._proposals.values():
                if proposal.idempotency_key == idempotency_key:
                    return copy.deepcopy(proposal)
        return None

    def list_action_proposals(self) -> list[ActionProposal]:
        with self._lock:
            proposals = [copy.deepcopy(proposal) for proposal in self._proposals.values()]
        return sort_proposals(proposals)

    def insert_action_proposal(self, proposal: ActionProposal) -> None:
        with self._lock:
            if proposal.action_id in self._proposals:
                raise ProposalConflictError(f"Proposal {proposal.action_id} already exists.")
            if proposal.idempotency_key is not None and any(
                existing.idempotency_key == proposal.idempotency_key
                for existing in self._proposals.values()
            ):
                raise ProposalConflictError(
                    f"Idempotency key {proposal.idempotency_key} is already in use."
                )
            self._proposals[proposal.action_id] = copy.deepcopy(proposal)

    def update_action_proposal(
        self,
        proposal: ActionProposal,
        *,
        expected_status: ProposalStatus,
        event: ProposalHistoryEvent | None,
    ) -> bool:
        with self._lock:
            stored = self._proposals.get(proposal.action_id)
            if stored is None or stored.status != expected_status:
                return False
            updated = copy.deepcopy(proposal)
            updated.idempotency_key = stored.idempotency_key
            updated.history = list(stored.history)
            if event is not None:
                updated.history.append(event)
            self._proposals[proposal.action_id] = updated
            return True


def _clean_reason(reason: str | None) -> str | None:
    return reason.strip() if reason and reason.strip() else None


class ActionProposalRegistry:
    """Lifecycle rules for the approval-gated proposal queue.

    State lives in the injected :class:`ActionProposalStore`; without one the
    registry keeps an in-memory store (tests, runtimes with no control plane).
    """

    def __init__(self, store: ActionProposalStore | None = None) -> None:
        self._store: ActionProposalStore = (
            store if store is not None else InMemoryActionProposalStore()
        )

    @property
    def durable(self) -> bool:
        """Whether proposals survive a process restart."""
        return bool(getattr(self._store, "durable", True))

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
        idempotency_key: str | None = None,
        actor_auth_provider: str | None = None,
        reopen_resolved: bool = False,
    ) -> ActionProposal:
        """Draft a proposal, or refresh the pending one it names.

        - An ``idempotency_key`` replay returns the proposal that key created
          (refreshed while pending, unchanged once resolved). A key owned by
          another drafter raises :class:`ProposalConflictError`.
        - Re-registering a pending ``action_id`` refreshes its observed state
          but keeps its identity and ``created_at``, so evaluation cycles
          cannot stack duplicate proposals.
        - Re-registering a resolved ``action_id`` raises
          :class:`ProposalTransitionError` unless ``reopen_resolved`` is set.
          Only in-process adapters that legitimately re-raise the same gate
          (the HA dispatcher) pass it; the API never does, so no caller can
          flip an operator's decision back to pending.
        """
        if idempotency_key is not None:
            replayed = self._store.find_action_proposal_by_idempotency_key(idempotency_key)
            if replayed is not None:
                return self._replay_idempotent(
                    replayed,
                    created_by=created_by,
                    verdict=verdict,
                    value=value,
                    metadata=metadata,
                    actor_auth_provider=actor_auth_provider,
                )
        resolved_action_id = action_id or (
            f"agent_{idempotency_key}"
            if idempotency_key is not None
            else f"approval_{uuid.uuid4().hex[:12]}"
        )
        existing = self._store.get_action_proposal(resolved_action_id)
        if existing is not None:
            if existing.idempotency_key != idempotency_key and (
                existing.idempotency_key is not None or idempotency_key is not None
            ):
                raise ProposalConflictError(
                    f"Proposal {resolved_action_id} exists under a different idempotency key."
                )
            if existing.status == "pending":
                return self._refresh(
                    existing,
                    verdict=verdict,
                    value=value,
                    metadata=metadata,
                    actor=created_by,
                    actor_auth_provider=actor_auth_provider,
                )
            if not reopen_resolved:
                raise ProposalTransitionError(resolved_action_id, existing.status)
            return self._reopen(
                existing,
                ActionProposal(
                    action_id=resolved_action_id,
                    policy_id=policy_id,
                    policy_name=policy_name,
                    verdict=verdict,
                    value=value,
                    notification_id=notification_id or resolved_action_id,
                    adapter=adapter,
                    source_kind=source_kind,
                    source_key=source_key,
                    source_summary=source_summary,
                    created_by=created_by,
                    metadata=dict(metadata or {}),
                    provenance=provenance,
                    idempotency_key=existing.idempotency_key,
                ),
                actor_auth_provider=actor_auth_provider,
            )

        proposal = ActionProposal(
            action_id=resolved_action_id,
            policy_id=policy_id,
            policy_name=policy_name,
            verdict=verdict,
            value=value,
            notification_id=notification_id or resolved_action_id,
            adapter=adapter,
            source_kind=source_kind,
            source_key=source_key,
            source_summary=source_summary,
            created_by=created_by,
            metadata=dict(metadata or {}),
            provenance=provenance,
            idempotency_key=idempotency_key,
        )
        proposal.history.append(
            ProposalHistoryEvent(
                kind="drafted",
                at=proposal.created_at,
                actor=created_by,
                actor_auth_provider=actor_auth_provider,
            )
        )
        try:
            self._store.insert_action_proposal(proposal)
        except ProposalConflictError:
            # Lost an insert race to a concurrent draft. For an idempotent
            # replay the winner's proposal is the answer; otherwise re-raise.
            if idempotency_key is None:
                raise
            winner = self._store.find_action_proposal_by_idempotency_key(idempotency_key)
            if winner is None:
                raise
            return self._replay_idempotent(
                winner,
                created_by=created_by,
                verdict=verdict,
                value=value,
                metadata=metadata,
                actor_auth_provider=actor_auth_provider,
            )
        return self._require(resolved_action_id)

    def _replay_idempotent(
        self,
        existing: ActionProposal,
        *,
        created_by: str | None,
        verdict: str,
        value: str | None,
        metadata: dict[str, Any] | None,
        actor_auth_provider: str | None,
    ) -> ActionProposal:
        if existing.created_by != created_by:
            raise ProposalConflictError(
                f"Idempotency key {existing.idempotency_key} belongs to another drafter."
            )
        if existing.status != "pending":
            return existing
        return self._refresh(
            existing,
            verdict=verdict,
            value=value,
            metadata=metadata,
            actor=created_by,
            actor_auth_provider=actor_auth_provider,
        )

    def _refresh(
        self,
        existing: ActionProposal,
        *,
        verdict: str,
        value: str | None,
        metadata: dict[str, Any] | None,
        actor: str | None,
        actor_auth_provider: str | None,
    ) -> ActionProposal:
        changed = existing.verdict != verdict or existing.value != value
        updated = copy.deepcopy(existing)
        updated.verdict = verdict
        updated.value = value
        updated.metadata = dict(metadata or {})
        event = (
            ProposalHistoryEvent(
                kind="refreshed",
                at=_now_iso(),
                actor=actor,
                actor_auth_provider=actor_auth_provider,
            )
            if changed
            else None
        )
        # A False result means it was resolved between our read and write;
        # either way the stored proposal is the answer.
        self._store.update_action_proposal(updated, expected_status="pending", event=event)
        return self._require(existing.action_id)

    def _reopen(
        self,
        existing: ActionProposal,
        reopened: ActionProposal,
        *,
        actor_auth_provider: str | None,
    ) -> ActionProposal:
        event = ProposalHistoryEvent(
            kind="reopened",
            at=reopened.created_at,
            actor=reopened.created_by,
            reason=f"Re-raised after it was {existing.status}.",
            actor_auth_provider=actor_auth_provider,
        )
        if not self._store.update_action_proposal(
            reopened, expected_status=existing.status, event=event
        ):
            current = self._require(existing.action_id)
            if current.status != "pending":
                raise ProposalTransitionError(existing.action_id, current.status)
        return self._require(existing.action_id)

    def approve(
        self,
        action_id: str,
        *,
        resolved_by: str | None = None,
        reason: str | None = None,
        actor_auth_provider: str | None = None,
    ) -> ActionProposal:
        return self._resolve(action_id, "approved", resolved_by, reason, actor_auth_provider)

    def dismiss(
        self,
        action_id: str,
        *,
        resolved_by: str | None = None,
        reason: str | None = None,
        actor_auth_provider: str | None = None,
    ) -> ActionProposal:
        return self._resolve(action_id, "dismissed", resolved_by, reason, actor_auth_provider)

    def _resolve(
        self,
        action_id: str,
        kind: Literal["approved", "dismissed"],
        resolved_by: str | None,
        reason: str | None,
        actor_auth_provider: str | None,
    ) -> ActionProposal:
        proposal = self._require_pending(action_id)
        at = _now_iso()
        cleaned_reason = _clean_reason(reason)
        proposal.status = kind
        if kind == "approved":
            proposal.approved_at = at
        else:
            proposal.dismissed_at = at
        proposal.resolved_by = resolved_by
        proposal.resolution_reason = cleaned_reason
        event = ProposalHistoryEvent(
            kind=kind,
            at=at,
            actor=resolved_by,
            reason=cleaned_reason,
            actor_auth_provider=actor_auth_provider,
        )
        if not self._store.update_action_proposal(
            proposal, expected_status="pending", event=event
        ):
            raise ProposalTransitionError(action_id, self._require(action_id).status)
        return self._require(action_id)

    def get(self, action_id: str) -> ActionProposal | None:
        return self._store.get_action_proposal(action_id)

    def list_pending(self) -> list[ActionProposal]:
        return [proposal for proposal in self.list_all() if proposal.status == "pending"]

    def list_all(self) -> list[ActionProposal]:
        return self._store.list_action_proposals()

    def get_status(self) -> dict[str, Any]:
        proposals = self.list_all()
        return {
            "tracked": len(proposals),
            "pending": sum(1 for proposal in proposals if proposal.status == "pending"),
            "approved": sum(1 for proposal in proposals if proposal.status == "approved"),
            "dismissed": sum(1 for proposal in proposals if proposal.status == "dismissed"),
        }

    def _require_pending(self, action_id: str) -> ActionProposal:
        proposal = self._require(action_id)
        if proposal.status != "pending":
            raise ProposalTransitionError(action_id, proposal.status)
        return proposal

    def _require(self, action_id: str) -> ActionProposal:
        proposal = self._store.get_action_proposal(action_id)
        if proposal is None:
            raise KeyError(f"Unknown approval action: {action_id}")
        return proposal
