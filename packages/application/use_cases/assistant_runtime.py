"""AssistantRuntime boundary (Kotona brief, Stage B2) — design prototype.

The household assistant targets this narrow internal contract, never a
provider or harness API directly:

- ``start(context, policy, tools) -> Session``
- ``continue_session(session, user_input) -> Iterator[AssistantEvent]``
  (``continue`` is a Python keyword)
- ``cancel(session) -> None``
- ``export_evidence(session) -> EvidenceSet``

The boundary is where tool permissions, redaction, provenance, cost
accounting, and evidence capture live:

- **Tool permissions** — a runtime only reaches tools through a
  :class:`ToolBroker`, which enforces the :class:`AssistantPolicy` grants.
  Draft tools (``propose_*``) are refused unless the policy allows drafts, and
  even then they only enter the approval queue.
- **Provenance and honesty** — every tool call and every cited publication's
  trust guidance is recorded; :class:`EvidenceSet` flags answers that rest on
  publications whose guidance forbids stating figures as current.
- **Cost accounting** — sessions carry a tool-call budget; provider runtimes
  add token/cost counters to the same :class:`SessionUsage`.

Gate: no runtime is constructed unless configuration enables it.
``HOMELAB_ANALYTICS_ASSISTANT_RUNTIME`` defaults to ``disabled``;
``deterministic`` selects the fake runtime below (no LLM, no network). The
``opencode`` value is reserved for the first provider adapter and is refused
here twice over: it additionally requires
``HOMELAB_ANALYTICS_ASSISTANT_PROVIDER_CALLS_ALLOWED=true``, and no provider
adapter ships in this tree yet, so it raises :class:`AssistantRuntimeUnavailable`.

Vuoro alignment: a session maps onto a vuoro run registration
(``register_run``: harness_id, harness_build, model_id, recipe_id) and its
evidence onto ``append_evidence``. :meth:`Session.vuoro_run_registration`
renders that shape for documentation and future wiring; nothing here sends it.
"""
from __future__ import annotations

import hashlib
import itertools
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

RuntimeName = Literal["disabled", "deterministic", "opencode"]
SessionStatus = Literal["active", "completed", "cancelled", "failed"]
EventKind = Literal["message", "tool_call", "tool_result", "refusal", "error", "done"]

READ_TOOLS: tuple[str, ...] = (
    "list_publications",
    "get_publication_summary",
    "get_publication_lineage",
    "get_proposal",
)
DRAFT_TOOLS: tuple[str, ...] = ("propose_scenario", "propose_policy", "propose_action")

ASSISTANT_RUNTIME_ENV = "HOMELAB_ANALYTICS_ASSISTANT_RUNTIME"
ASSISTANT_PROVIDER_CALLS_ENV = "HOMELAB_ANALYTICS_ASSISTANT_PROVIDER_CALLS_ALLOWED"

UNTRUSTED_GUIDANCE = frozenset({"do_not_state_as_current", "trust_unknown"})


class AssistantRuntimeDisabled(RuntimeError):
    """The assistant runtime is disabled by configuration (the default)."""


class AssistantRuntimeUnavailable(RuntimeError):
    """The configured runtime cannot be constructed in this deployment."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class AssistantContext:
    """Who is asking, about what, through which surface."""

    operator: str | None
    surface: str = "assistant"
    domain: str | None = None
    locale: str = "en"


@dataclass(frozen=True)
class AssistantPolicy:
    """Grants and limits enforced at the boundary, not inside a runtime."""

    tool_grants: tuple[str, ...] = READ_TOOLS
    allow_drafts: bool = False
    max_tool_calls: int = 8
    redact_sample_rows: bool = True

    def permits(self, tool_name: str) -> bool:
        if tool_name not in self.tool_grants:
            return False
        if tool_name in DRAFT_TOOLS and not self.allow_drafts:
            return False
        return True


@dataclass(frozen=True)
class ToolOutcome:
    tool_name: str
    is_error: bool
    payload: Mapping[str, Any]
    error_code: str | None = None


class ToolBroker(Protocol):
    """The only path from a runtime to platform tools."""

    def invoke(self, tool_name: str, arguments: Mapping[str, Any]) -> ToolOutcome:
        ...


@dataclass
class SessionUsage:
    tool_calls: int = 0
    refused_tool_calls: int = 0
    provider_input_tokens: int = 0
    provider_output_tokens: int = 0
    provider_cost_eur: str = "0"


@dataclass(frozen=True)
class AssistantEvent:
    sequence: int
    kind: EventKind
    at: str
    payload: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"sequence": self.sequence, "kind": self.kind, "at": self.at, "payload": dict(self.payload)}


@dataclass
class Session:
    session_id: str
    runtime: str
    runtime_build: str
    model_id: str
    recipe_id: str
    context: AssistantContext
    policy: AssistantPolicy
    started_at: str
    status: SessionStatus = "active"
    events: list[AssistantEvent] = field(default_factory=list)
    usage: SessionUsage = field(default_factory=SessionUsage)
    cited_publications: dict[str, str] = field(default_factory=dict)
    drafted_proposals: list[str] = field(default_factory=list)

    def vuoro_run_registration(self) -> dict[str, Any]:
        """The vuoro ``register_run`` input this session would map onto."""
        digest = hashlib.sha256(
            f"{self.recipe_id}:{','.join(sorted(self.policy.tool_grants))}".encode()
        ).hexdigest()
        return {
            "harness_id": f"hla-assistant/{self.runtime}",
            "harness_build": self.runtime_build,
            "model_id": self.model_id,
            "recipe_id": self.recipe_id,
            "observed_profile": {"instruction_digest": digest, "skill_digests": []},
            "idempotency_key": f"hla-session:{self.session_id}",
        }


@dataclass(frozen=True)
class EvidenceSet:
    """What an answer rested on, exported for audit and operator review."""

    session_id: str
    runtime: str
    status: SessionStatus
    tool_calls: tuple[Mapping[str, Any], ...]
    cited_publications: Mapping[str, str]
    untrusted_citations: tuple[str, ...]
    drafted_proposals: tuple[str, ...]
    answer: str | None
    usage: SessionUsage

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "runtime": self.runtime,
            "status": self.status,
            "tool_calls": [dict(call) for call in self.tool_calls],
            "cited_publications": dict(self.cited_publications),
            "untrusted_citations": list(self.untrusted_citations),
            "drafted_proposals": list(self.drafted_proposals),
            "answer": self.answer,
            "usage": vars(self.usage).copy(),
        }


class AssistantRuntime(Protocol):
    name: str

    def start(
        self, context: AssistantContext, policy: AssistantPolicy, tools: ToolBroker
    ) -> Session:
        ...

    def continue_session(self, session: Session, user_input: str) -> Iterator[AssistantEvent]:
        ...

    def cancel(self, session: Session) -> None:
        ...

    def export_evidence(self, session: Session) -> EvidenceSet:
        ...


class _SessionRecorder:
    """Boundary bookkeeping shared by runtimes: events, grants, budget."""

    def __init__(self, session: Session, tools: ToolBroker) -> None:
        self._session = session
        self._tools = tools
        self._sequence = itertools.count(len(session.events) + 1)

    def emit(self, kind: EventKind, **payload: Any) -> AssistantEvent:
        event = AssistantEvent(sequence=next(self._sequence), kind=kind, at=_now(), payload=payload)
        self._session.events.append(event)
        return event

    def call(self, tool_name: str, arguments: Mapping[str, Any]) -> tuple[ToolOutcome | None, list[AssistantEvent]]:
        session = self._session
        events: list[AssistantEvent] = []
        if not session.policy.permits(tool_name):
            session.usage.refused_tool_calls += 1
            events.append(self.emit("refusal", tool=tool_name, reason="tool not granted by assistant policy"))
            return None, events
        if session.usage.tool_calls >= session.policy.max_tool_calls:
            session.usage.refused_tool_calls += 1
            events.append(self.emit("refusal", tool=tool_name, reason="tool-call budget exhausted"))
            return None, events
        session.usage.tool_calls += 1
        events.append(self.emit("tool_call", tool=tool_name, arguments=dict(arguments)))
        outcome = self._tools.invoke(tool_name, arguments)
        events.append(
            self.emit(
                "tool_result",
                tool=tool_name,
                is_error=outcome.is_error,
                error_code=outcome.error_code,
            )
        )
        return outcome, events


_CAVEATS = {
    "state_as_current": "",
    "state_with_caveat": " (with a caveat: the data is degraded or due for refresh)",
    "do_not_state_as_current": " — but this data is stale or unreliable, so it should not be read as current",
    "trust_unknown": " — freshness is unknown, so it should not be read as current",
}


class DeterministicAssistantRuntime:
    """Fake runtime for tests and demos: no model, no network, same contract.

    For each input it searches the semantic index, reads the best match, and
    answers by naming the publication and quoting its trust guidance. It
    never states a figure, so it cannot overstate one. It exercises the full
    boundary (grants, budget, evidence) that a provider runtime must honour.
    """

    name = "deterministic"
    build = "hla-deterministic/1"

    def __init__(self) -> None:
        self._brokers: dict[str, ToolBroker] = {}

    def start(
        self, context: AssistantContext, policy: AssistantPolicy, tools: ToolBroker
    ) -> Session:
        session = Session(
            session_id=f"asst_{uuid.uuid4().hex[:12]}",
            runtime=self.name,
            runtime_build=self.build,
            model_id="none",
            recipe_id="hla-publication-lookup/1",
            context=context,
            policy=policy,
            started_at=_now(),
        )
        self._brokers[session.session_id] = tools
        return session

    def continue_session(self, session: Session, user_input: str) -> Iterator[AssistantEvent]:
        if session.status != "active":
            raise ValueError(f"Session {session.session_id} is {session.status}.")
        recorder = _SessionRecorder(session, self._brokers[session.session_id])
        yield recorder.emit("message", role="user", text=user_input)

        listing, events = recorder.call("list_publications", {"query": user_input, "limit": 3})
        yield from events
        publications = (
            list(listing.payload.get("publications", [])) if listing and not listing.is_error else []
        )
        if not publications:
            yield recorder.emit(
                "message",
                role="assistant",
                text="I could not find a publication that answers this, so I will not guess.",
            )
            yield recorder.emit("done")
            return

        chosen = _best_match(publications, user_input)
        key = str(chosen.get("publication_key"))
        summary, events = recorder.call("get_publication_summary", {"publication_key": key})
        yield from events
        trust: Mapping[str, Any] = {}
        name = str(chosen.get("display_name") or key)
        if summary is not None and not summary.is_error:
            trust = summary.payload.get("answer_guidance") or {}
        guidance = str(trust.get("guidance") or "trust_unknown")
        session.cited_publications[key] = guidance
        assessed = trust.get("assessed_at")
        text = f"The best source for this is “{name}” ({key}){_CAVEATS.get(guidance, _CAVEATS['trust_unknown'])}."
        if assessed:
            text += f" Last assessed {assessed}."
        yield recorder.emit("message", role="assistant", text=text, citations=[key])
        yield recorder.emit("done")

    def cancel(self, session: Session) -> None:
        if session.status == "active":
            session.status = "cancelled"
            self._brokers.pop(session.session_id, None)

    def export_evidence(self, session: Session) -> EvidenceSet:
        answers = [
            event.payload.get("text")
            for event in session.events
            if event.kind == "message" and event.payload.get("role") == "assistant"
        ]
        tool_calls = tuple(
            dict(event.payload) for event in session.events if event.kind in ("tool_call", "refusal")
        )
        return EvidenceSet(
            session_id=session.session_id,
            runtime=session.runtime,
            status=session.status,
            tool_calls=tool_calls,
            cited_publications=dict(session.cited_publications),
            untrusted_citations=tuple(
                key for key, guidance in session.cited_publications.items() if guidance in UNTRUSTED_GUIDANCE
            ),
            drafted_proposals=tuple(session.drafted_proposals),
            answer=str(answers[-1]) if answers else None,
            usage=session.usage,
        )


def _best_match(publications: list[Mapping[str, Any]], user_input: str) -> Mapping[str, Any]:
    """Exact key or display-name match first, else the index's top hit."""
    wanted = user_input.strip().lower().replace(" ", "_")
    for entry in publications:
        key = str(entry.get("publication_key") or "").lower()
        name = str(entry.get("display_name") or "").strip().lower().replace(" ", "_")
        if wanted in (key, name):
            return entry
    return publications[0]


def resolve_runtime_name(env: Mapping[str, str]) -> RuntimeName:
    raw = (env.get(ASSISTANT_RUNTIME_ENV) or "disabled").strip().lower()
    if raw not in ("disabled", "deterministic", "opencode"):
        raise ValueError(
            f"{ASSISTANT_RUNTIME_ENV} must be disabled, deterministic, or opencode; got {raw!r}."
        )
    return raw  # type: ignore[return-value]


def build_assistant_runtime(env: Mapping[str, str]) -> AssistantRuntime:
    """Construct the configured runtime, or refuse. Disabled by default."""
    name = resolve_runtime_name(env)
    if name == "disabled":
        raise AssistantRuntimeDisabled(
            f"The assistant runtime is disabled. Set {ASSISTANT_RUNTIME_ENV}=deterministic "
            "for the offline fake runtime."
        )
    if name == "deterministic":
        return DeterministicAssistantRuntime()
    provider_calls = (env.get(ASSISTANT_PROVIDER_CALLS_ENV) or "").strip().lower() == "true"
    if not provider_calls:
        raise AssistantRuntimeDisabled(
            f"The opencode runtime makes LLM provider calls and requires "
            f"{ASSISTANT_PROVIDER_CALLS_ENV}=true in addition to {ASSISTANT_RUNTIME_ENV}=opencode."
        )
    raise AssistantRuntimeUnavailable(
        "No OpenCode runtime adapter ships in this build; the AssistantRuntime "
        "boundary is a design prototype (Kotona brief Stage B2)."
    )
