"""Record household decisions and follow-ups against exact published evidence.

Rules enforced here (independent of transport):

- The decision key must be declared and the outcome must be one of its
  options; an explicit non-decision is an outcome, not an absence.
- The subject is the current reporting-layer row for the period. When the
  caller states which row it reviewed (``subject_row_ref``) and the
  publication has since changed, the request is refused as stale.
- Evidence the publication marks as insufficient (any reason code, or an
  ``insufficient_evidence`` verdict) must be explicitly acknowledged.
- The actor comes from the auth layer; with identity disabled the record says
  so (``actor_authenticated = false``) rather than inventing a decision-maker.
- Recording a decision authorizes nothing: it holds no device or tariff action.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from packages.platform.decision_definitions import (
    DecisionDefinition,
    DecisionSubjectEvidence,
)
from packages.storage.decision_ledger import (
    FOLLOW_UP_EVIDENCE_EFFECTS,
    REALIZED_VALUE_STATUSES,
    DecisionActor,
    DecisionFollowUpCreate,
    DecisionFollowUpRecord,
    DecisionLedgerStore,
    DecisionRecord,
    DecisionRecordCreate,
)


class DecisionValidationError(ValueError):
    pass


class DecisionSubjectConflictError(ValueError):
    pass


@dataclass(frozen=True)
class DecisionRequest:
    decision_key: str
    subject_period: str
    outcome: str
    rationale: str
    evidence_gaps_acknowledged: tuple[str, ...] = ()
    uncertainty: str | None = None
    subject_row_ref: str | None = None
    follow_up_due_on: date | None = None


@dataclass(frozen=True)
class FollowUpRequest:
    observed_at: datetime
    realized_result: str
    evidence_effect: str
    observation_period: str | None = None
    realized_value_eur: Decimal | None = None
    realized_value_status: str | None = None
    notes: str | None = None


def actor_from_principal(principal: object | None) -> DecisionActor:
    if principal is None:
        return DecisionActor(
            actor="unauthenticated",
            actor_role=None,
            actor_auth_provider="disabled",
            actor_authenticated=False,
        )
    role = getattr(principal, "role", None)
    return DecisionActor(
        actor=str(getattr(principal, "username", None) or getattr(principal, "user_id", "unknown")),
        actor_role=str(getattr(role, "value", role)) if role is not None else None,
        actor_auth_provider=str(getattr(principal, "auth_provider", None) or "unknown"),
        actor_authenticated=True,
    )


def record_decision(
    store: DecisionLedgerStore,
    *,
    definition_lookup: Callable[[str], DecisionDefinition | None],
    subject_reader: Callable[[str, str], DecisionSubjectEvidence | None],
    request: DecisionRequest,
    actor: DecisionActor,
    now: datetime | None = None,
) -> DecisionRecord:
    created_at = now or datetime.now(UTC)
    definition = definition_lookup(request.decision_key)
    if definition is None:
        raise LookupError(f"Unknown decision: {request.decision_key}")
    option = definition.outcome_option(request.outcome)
    if option is None:
        allowed = ", ".join(o.key for o in definition.outcome_options)
        raise DecisionValidationError(f"Unknown outcome {request.outcome!r}; allowed: {allowed}")
    if not request.rationale.strip():
        raise DecisionValidationError("A rationale is required.")
    subject = subject_reader(request.decision_key, request.subject_period)
    if subject is None:
        raise LookupError(
            f"No published {definition.subject_publication_key} row for {request.subject_period}"
        )
    if request.subject_row_ref is not None and request.subject_row_ref != subject.row_ref:
        raise DecisionSubjectConflictError(
            "The publication changed since it was reviewed "
            f"(reviewed {request.subject_row_ref}, current {subject.row_ref}); re-review it."
        )
    gaps = tuple(gap.strip() for gap in request.evidence_gaps_acknowledged if gap.strip())
    if (subject.reason_codes or subject.verdict == "insufficient_evidence") and not gaps:
        raise DecisionValidationError(
            "The evidence is insufficient "
            f"({', '.join(subject.reason_codes) or subject.verdict}); "
            "acknowledge the evidence gaps to record a decision or non-decision."
        )
    due = request.follow_up_due_on or (
        created_at.date() + timedelta(days=definition.follow_up_default_days)
    )
    if due <= created_at.date():
        raise DecisionValidationError("follow_up_due_on must be after the decision date.")
    return store.create_decision_record(
        DecisionRecordCreate(
            decision_id=f"dec_{uuid.uuid4().hex}",
            decision_key=definition.decision_key,
            decision_version=definition.version,
            subject_publication_key=subject.publication_key,
            subject_schema_version=subject.schema_version,
            subject_period=subject.period,
            subject_row_ref=subject.row_ref,
            subject_verdict=subject.verdict,
            lineage_reference=_json(subject.lineage_reference),
            evidence_snapshot=_json(subject.snapshot),
            outcome=option.key,
            is_non_decision=option.is_non_decision,
            rationale=request.rationale.strip(),
            evidence_gaps_acknowledged=_json(list(gaps)),
            uncertainty=(request.uncertainty or "").strip() or None,
            actor=actor,
            follow_up_due_on=due,
            created_at=created_at,
        )
    )


def record_follow_up(
    store: DecisionLedgerStore,
    *,
    decision_id: str,
    request: FollowUpRequest,
    actor: DecisionActor,
    now: datetime | None = None,
) -> DecisionFollowUpRecord:
    created_at = now or datetime.now(UTC)
    decision = store.get_decision_record(decision_id)
    if request.evidence_effect not in FOLLOW_UP_EVIDENCE_EFFECTS:
        allowed = ", ".join(sorted(FOLLOW_UP_EVIDENCE_EFFECTS))
        raise DecisionValidationError(f"Unknown evidence_effect; allowed: {allowed}")
    if request.evidence_effect == "preserved_non_decision" and not decision.is_non_decision:
        raise DecisionValidationError(
            "preserved_non_decision applies only to an explicit non-decision."
        )
    if request.observed_at.tzinfo is None:
        raise DecisionValidationError("observed_at must include a timezone offset.")
    if request.observed_at.astimezone(UTC) < decision.created_at.astimezone(UTC):
        raise DecisionValidationError("A follow-up cannot be observed before the decision.")
    if request.observed_at.astimezone(UTC) > created_at.astimezone(UTC):
        raise DecisionValidationError("observed_at cannot be in the future.")
    if not request.realized_result.strip():
        raise DecisionValidationError("realized_result is required.")
    if request.realized_value_eur is not None:
        if request.realized_value_status not in REALIZED_VALUE_STATUSES:
            raise DecisionValidationError(
                "A realized value needs realized_value_status of observed or user_entered."
            )
    elif request.realized_value_status is not None:
        raise DecisionValidationError("realized_value_status requires realized_value_eur.")
    return store.add_decision_follow_up(
        DecisionFollowUpCreate(
            follow_up_id=f"fup_{uuid.uuid4().hex}",
            decision_id=decision.decision_id,
            observed_at=request.observed_at,
            observation_period=request.observation_period,
            realized_result=request.realized_result.strip(),
            realized_value_eur=request.realized_value_eur,
            realized_value_status=request.realized_value_status,
            evidence_effect=request.evidence_effect,
            notes=(request.notes or "").strip() or None,
            actor=actor,
            created_at=created_at,
        )
    )


def serialize_follow_up(follow_up: DecisionFollowUpRecord) -> dict[str, Any]:
    return {
        "follow_up_id": follow_up.follow_up_id,
        "decision_id": follow_up.decision_id,
        "observed_at": follow_up.observed_at.isoformat(),
        "observation_period": follow_up.observation_period,
        "realized_result": follow_up.realized_result,
        "realized_value_eur": (
            str(follow_up.realized_value_eur)
            if follow_up.realized_value_eur is not None
            else None
        ),
        "realized_value_status": follow_up.realized_value_status,
        "evidence_effect": follow_up.evidence_effect,
        "notes": follow_up.notes,
        "actor": _serialize_actor(follow_up.actor),
        "created_at": follow_up.created_at.isoformat(),
    }


def serialize_decision(
    record: DecisionRecord,
    follow_ups: list[DecisionFollowUpRecord],
    *,
    include_snapshot: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision_id": record.decision_id,
        "decision_key": record.decision_key,
        "decision_version": record.decision_version,
        "subject": {
            "publication_key": record.subject_publication_key,
            "schema_version": record.subject_schema_version,
            "period": record.subject_period,
            "row_ref": record.subject_row_ref,
            "verdict": record.subject_verdict,
        },
        "lineage_reference": json.loads(record.lineage_reference),
        "outcome": record.outcome,
        "is_non_decision": record.is_non_decision,
        "rationale": record.rationale,
        "evidence_gaps_acknowledged": json.loads(record.evidence_gaps_acknowledged),
        "uncertainty": record.uncertainty,
        "actor": _serialize_actor(record.actor),
        "follow_up_due_on": record.follow_up_due_on.isoformat(),
        "created_at": record.created_at.isoformat(),
        "status": "followed_up" if follow_ups else "awaiting_follow_up",
        "actuation_authorized": False,
        "follow_ups": [serialize_follow_up(item) for item in follow_ups],
    }
    if include_snapshot:
        payload["evidence_snapshot"] = json.loads(record.evidence_snapshot)
    return payload


def _serialize_actor(actor: DecisionActor) -> dict[str, Any]:
    return {
        "actor": actor.actor,
        "role": actor.actor_role,
        "auth_provider": actor.actor_auth_provider,
        "authenticated": actor.actor_authenticated,
    }


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
