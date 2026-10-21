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

Commitment lifecycle (HLA-K01): every record opens a commitment whose terms
are pinned from the definition version at record time.

- The authenticated actor must satisfy the definition's owner (role, and
  principal when one is declared). Without identity the commitment records
  ``owner_verified = false``.
- The observation window and first review date derive from the definition;
  an explicit follow-up date may not fall before the window closes.
- Stop conditions met by the outcome or the evidence are flagged; only the
  owner stops a commitment (``stop_commitment``), and may reopen it.
- State is derived, never stored: ``stopped`` > ``review_required``
  (evidence superseded since the last review) > ``review_due`` (next review
  date reached) > ``active``. Stopped commitments drop out of the review
  queue; their history stays readable.

Attribution review (HLA-K03): a follow-up keeps the measured result apart
from an estimated baseline. The estimate is either a value pinned in the
commitment baseline (``baseline_value_key``) or an explicit value with its
basis; the follow-up also carries the attribution hypothesis, confounders,
uncertainty and the evidence known to be missing. Nothing here claims
causation: the measured-minus-estimate difference is reported only when both
sides exist, and every unrecorded part is listed rather than assumed. The
operator's attention time on the review is captured when entered and stays
unknown (``None``) otherwise, never zero.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from packages.platform.auth.contracts import UserRole
from packages.platform.auth.role_hierarchy import has_required_role
from packages.platform.decision_definitions import (
    DecisionDefinition,
    DecisionSubjectEvidence,
    DecisionSuccessMeasure,
)
from packages.storage.decision_ledger import (
    FOLLOW_UP_EVIDENCE_EFFECTS,
    REALIZED_VALUE_STATUSES,
    DecisionActor,
    DecisionCommitment,
    DecisionFollowUpCreate,
    DecisionFollowUpRecord,
    DecisionLedgerStore,
    DecisionLifecycleEvent,
    DecisionLifecycleEventCreate,
    DecisionRecord,
    DecisionRecordCreate,
)

LIFECYCLE_STATES = ("active", "review_due", "review_required", "stopped")
REVIEW_QUEUE_STATES = frozenset({"review_due", "review_required"})
# Records made before commitment terms existed (definition 1.0.0) have only a
# follow-up date; after a follow-up their next review uses this cadence.
LEGACY_REVIEW_CADENCE_DAYS = 30


class DecisionValidationError(ValueError):
    pass


class DecisionSubjectConflictError(ValueError):
    pass


class DecisionAuthorizationError(PermissionError):
    pass


class DecisionStateConflictError(ValueError):
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
    decided_at: datetime | None = None
    retrospective_basis: str | None = None


@dataclass(frozen=True)
class FollowUpRequest:
    observed_at: datetime
    realized_result: str
    evidence_effect: str
    observation_period: str | None = None
    realized_value_eur: Decimal | None = None
    realized_value_status: str | None = None
    notes: str | None = None
    baseline_value_key: str | None = None
    estimated_baseline_eur: Decimal | None = None
    estimated_baseline_basis: str | None = None
    attribution_hypothesis: str | None = None
    confounders: tuple[str, ...] = ()
    attribution_uncertainty: str | None = None
    missing_evidence: tuple[str, ...] = ()
    attention_minutes: int | None = None


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


def check_owner(
    *, owner_role: str, owner_principal: str | None, actor: DecisionActor
) -> bool:
    """Return whether the actor is a verified owner; raise if it is not one.

    An unauthenticated actor (identity disabled) is recorded as unverified
    rather than refused, so the ledger works on a single-user install without
    pretending an authenticated household decision-maker acted.
    """
    if not actor.actor_authenticated:
        return False
    try:
        actor_role = UserRole(actor.actor_role or "")
        required = UserRole(owner_role)
    except ValueError as exc:
        raise DecisionAuthorizationError(
            f"Actor role {actor.actor_role!r} cannot own this commitment."
        ) from exc
    if not has_required_role(actor_role, required):
        raise DecisionAuthorizationError(
            f"Only the {owner_role} role may own this commitment."
        )
    if owner_principal is not None and actor.actor != owner_principal:
        raise DecisionAuthorizationError(
            f"This commitment is owned by {owner_principal}; {actor.actor} cannot act on it."
        )
    return True


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
    owner_verified = check_owner(
        owner_role=definition.owner.role,
        owner_principal=definition.owner.principal,
        actor=actor,
    )
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
    decided_at, retrospective_basis = _decision_time(request, created_at)
    decided_on = (decided_at or created_at).date()
    window_start, window_end = definition.observation_window.window_for(decided_on)
    due = request.follow_up_due_on or definition.observation_window.review_due_on(decided_on)
    if due <= decided_on:
        raise DecisionValidationError("follow_up_due_on must be after the decision date.")
    if due < window_end:
        raise DecisionValidationError(
            "follow_up_due_on falls before the observation window closes "
            f"({window_end.isoformat()}); the realized result cannot be reviewed yet."
        )
    stop_conditions_met = [
        condition.key
        for condition in definition.stop_conditions
        if condition.met_by(outcome=option.key, reason_codes=subject.reason_codes)
    ]
    decision_id = f"dec_{uuid.uuid4().hex}"
    terms = definition.to_dict()
    commitment = DecisionCommitment(
        decision_id=decision_id,
        purpose=definition.purpose,
        owner_role=definition.owner.role,
        owner_principal=definition.owner.principal,
        owner_verified=owner_verified,
        baseline=_json(
            {
                "description": definition.baseline.description,
                "values": {
                    key: subject.baseline.get(
                        key, {"value": None, "status": None, "unit": None, "is_missing": True}
                    )
                    for key in definition.baseline.value_keys
                },
            }
        ),
        success_measure=_json(terms["success_measure"]),
        observation_window_start=window_start,
        observation_window_end=window_end,
        next_review_due_on=due,
        review_cadence_days=definition.observation_window.review_cadence_days,
        review_triggers=_json(terms["review_triggers"]),
        stop_conditions=_json(terms["stop_conditions"]),
        stop_conditions_met=_json(stop_conditions_met),
        evidence_fingerprint=subject.evidence_fingerprint,
        evidence_components=_json(subject.evidence_components),
        created_at=created_at,
    )
    lineage = dict(subject.lineage_reference)
    lineage["evidence_fingerprint"] = subject.evidence_fingerprint
    return store.create_decision_record(
        DecisionRecordCreate(
            decision_id=decision_id,
            decision_key=definition.decision_key,
            decision_version=definition.version,
            subject_publication_key=subject.publication_key,
            subject_schema_version=subject.schema_version,
            subject_period=subject.period,
            subject_row_ref=subject.row_ref,
            subject_verdict=subject.verdict,
            lineage_reference=_json(lineage),
            evidence_snapshot=_json(subject.snapshot),
            outcome=option.key,
            is_non_decision=option.is_non_decision,
            rationale=request.rationale.strip(),
            evidence_gaps_acknowledged=_json(list(gaps)),
            uncertainty=(request.uncertainty or "").strip() or None,
            actor=actor,
            follow_up_due_on=due,
            commitment=commitment,
            created_at=created_at,
            decided_at=decided_at,
            retrospective_basis=retrospective_basis,
        )
    )


def _decision_time(
    request: DecisionRequest, created_at: datetime
) -> tuple[datetime | None, str | None]:
    """Retrospective entry: an earlier decision time needs the record that shows it."""
    basis = (request.retrospective_basis or "").strip() or None
    if request.decided_at is None:
        if basis is not None:
            raise DecisionValidationError("retrospective_basis requires decided_at.")
        return None, None
    if request.decided_at.tzinfo is None:
        raise DecisionValidationError("decided_at must include a timezone offset.")
    if request.decided_at.astimezone(UTC) > created_at.astimezone(UTC):
        raise DecisionValidationError("decided_at cannot be in the future.")
    if basis is None:
        raise DecisionValidationError(
            "A retrospective decision needs retrospective_basis: what shows it was decided then."
        )
    return request.decided_at, basis


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
    if request.observed_at.astimezone(UTC) < decision.effective_decided_at.astimezone(UTC):
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
    estimate, basis = _estimated_baseline(decision, request)
    if request.attention_minutes is not None and request.attention_minutes < 0:
        raise DecisionValidationError("attention_minutes cannot be negative.")
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
            estimated_baseline_eur=estimate,
            estimated_baseline_basis=basis,
            attribution_hypothesis=_optional_text(request.attribution_hypothesis),
            confounders=_json(_text_list(request.confounders)),
            attribution_uncertainty=_optional_text(request.attribution_uncertainty),
            missing_evidence=_json(_text_list(request.missing_evidence)),
            attention_minutes=request.attention_minutes,
        )
    )


def _estimated_baseline(
    decision: DecisionRecord, request: FollowUpRequest
) -> tuple[Decimal | None, str | None]:
    """The estimate a follow-up compares its measured result with, and its basis."""
    explicit_basis = _optional_text(request.estimated_baseline_basis)
    if request.baseline_value_key is not None:
        if request.estimated_baseline_eur is not None or explicit_basis is not None:
            raise DecisionValidationError(
                "Give either baseline_value_key or an explicit estimated baseline, not both."
            )
        if decision.commitment is None:
            raise DecisionValidationError(
                "This decision has no pinned commitment baseline to compare with."
            )
        values = json.loads(decision.commitment.baseline).get("values") or {}
        pinned = values.get(request.baseline_value_key)
        if pinned is None:
            allowed = ", ".join(sorted(values)) or "none"
            raise DecisionValidationError(
                f"Unknown baseline_value_key; pinned baseline values: {allowed}"
            )
        if pinned.get("value") is None:
            raise DecisionValidationError(
                "The pinned baseline value is missing; record the gap in missing_evidence."
            )
        return (
            Decimal(str(pinned["value"])),
            f"Decision baseline {request.baseline_value_key} "
            f"({pinned.get('status') or 'estimated'}, {pinned.get('unit') or 'unit unknown'}).",
        )
    if request.estimated_baseline_eur is not None:
        if explicit_basis is None:
            raise DecisionValidationError(
                "An estimated baseline needs estimated_baseline_basis stating where it came from."
            )
        return request.estimated_baseline_eur, explicit_basis
    if explicit_basis is not None:
        raise DecisionValidationError("estimated_baseline_basis requires estimated_baseline_eur.")
    return None, None


def _optional_text(value: str | None) -> str | None:
    return (value or "").strip() or None


def _text_list(values: Sequence[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        text = value.strip()
        if text and text not in seen:
            seen.append(text)
    return seen


# ---------------------------------------------------------------------------
# Lifecycle: operator stop / reopen and derived state
# ---------------------------------------------------------------------------


def _owner_of(
    record: DecisionRecord, definition_lookup: Callable[[str], DecisionDefinition | None]
) -> tuple[str, str | None]:
    if record.commitment is not None:
        return record.commitment.owner_role, record.commitment.owner_principal
    definition = definition_lookup(record.decision_key)
    return (definition.owner.role, definition.owner.principal) if definition else ("operator", None)


def _pinned_stop_condition_keys(
    record: DecisionRecord, definition_lookup: Callable[[str], DecisionDefinition | None]
) -> list[str]:
    if record.commitment is not None:
        return [item["key"] for item in json.loads(record.commitment.stop_conditions)]
    definition = definition_lookup(record.decision_key)
    return [condition.key for condition in definition.stop_conditions] if definition else []


def stop_commitment(
    store: DecisionLedgerStore,
    *,
    decision_id: str,
    stop_condition_key: str,
    reason: str,
    actor: DecisionActor,
    definition_lookup: Callable[[str], DecisionDefinition | None],
    now: datetime | None = None,
) -> DecisionLifecycleEvent:
    """The owner ends a commitment under one of its pinned stop conditions."""
    occurred_at = now or datetime.now(UTC)
    record = store.get_decision_record(decision_id)
    owner_role, owner_principal = _owner_of(record, definition_lookup)
    check_owner(owner_role=owner_role, owner_principal=owner_principal, actor=actor)
    allowed = _pinned_stop_condition_keys(record, definition_lookup)
    if stop_condition_key not in allowed:
        raise DecisionValidationError(
            f"Unknown stop condition {stop_condition_key!r}; allowed: {', '.join(allowed)}"
        )
    if not reason.strip():
        raise DecisionValidationError("A stop reason is required.")
    events = store.list_decision_lifecycle_events(decision_id)
    if _is_stopped(events):
        raise DecisionStateConflictError("The commitment is already stopped.")
    sequence = sum(1 for event in events if event.event_kind == "stopped") + 1
    event, _ = store.append_decision_lifecycle_event(
        DecisionLifecycleEventCreate(
            event_id=f"dle_{uuid.uuid4().hex}",
            decision_id=decision_id,
            event_kind="stopped",
            dedupe_key=f"{decision_id}:stopped:{sequence}",
            reason_code=stop_condition_key,
            reason=reason.strip(),
            details=_json({"stop_condition_key": stop_condition_key}),
            actor=actor,
            occurred_at=occurred_at,
            created_at=occurred_at,
        )
    )
    return event


def reopen_commitment(
    store: DecisionLedgerStore,
    *,
    decision_id: str,
    reason: str,
    actor: DecisionActor,
    definition_lookup: Callable[[str], DecisionDefinition | None],
    now: datetime | None = None,
) -> DecisionLifecycleEvent:
    occurred_at = now or datetime.now(UTC)
    record = store.get_decision_record(decision_id)
    owner_role, owner_principal = _owner_of(record, definition_lookup)
    check_owner(owner_role=owner_role, owner_principal=owner_principal, actor=actor)
    if not reason.strip():
        raise DecisionValidationError("A reopen reason is required.")
    events = store.list_decision_lifecycle_events(decision_id)
    if not _is_stopped(events):
        raise DecisionStateConflictError("Only a stopped commitment can be reopened.")
    sequence = sum(1 for event in events if event.event_kind == "reopened") + 1
    event, _ = store.append_decision_lifecycle_event(
        DecisionLifecycleEventCreate(
            event_id=f"dle_{uuid.uuid4().hex}",
            decision_id=decision_id,
            event_kind="reopened",
            dedupe_key=f"{decision_id}:reopened:{sequence}",
            reason_code="owner_reopened",
            reason=reason.strip(),
            details=_json({}),
            actor=actor,
            occurred_at=occurred_at,
            created_at=occurred_at,
        )
    )
    return event


def _is_stopped(events: Sequence[DecisionLifecycleEvent]) -> bool:
    stopped = False
    for event in events:
        if event.event_kind == "stopped":
            stopped = True
        elif event.event_kind == "reopened":
            stopped = False
    return stopped


def _success_measure(record: DecisionRecord) -> DecisionSuccessMeasure | None:
    if record.commitment is None:
        return None
    payload = json.loads(record.commitment.success_measure)
    return DecisionSuccessMeasure(
        key=str(payload["key"]),
        description=str(payload["description"]),
        unit=str(payload["unit"]),
        comparison=str(payload["comparison"]),
        threshold=Decimal(str(payload["threshold"])),
        accepted_value_statuses=tuple(payload.get("accepted_value_statuses") or ()),
    )


def evaluate_follow_up_success(
    record: DecisionRecord, follow_up: DecisionFollowUpRecord
) -> str:
    """``met`` / ``not_met`` / ``unmeasured`` against the pinned success measure."""
    measure = _success_measure(record)
    if measure is None:
        return "unmeasured"
    return measure.evaluate(follow_up.realized_value_eur, follow_up.realized_value_status)


def derive_commitment_state(
    record: DecisionRecord,
    follow_ups: Sequence[DecisionFollowUpRecord],
    events: Sequence[DecisionLifecycleEvent],
    *,
    today: date,
) -> dict[str, Any]:
    """Derived lifecycle view: state, next review, open supersessions, reasons."""
    commitment = record.commitment
    if commitment is not None:
        cadence = commitment.review_cadence_days
        next_review = commitment.next_review_due_on
    else:
        cadence = LEGACY_REVIEW_CADENCE_DAYS
        next_review = record.follow_up_due_on
    stopped = False
    stop_event: DecisionLifecycleEvent | None = None
    open_supersessions: list[DecisionLifecycleEvent] = []
    timeline: list[tuple[datetime, str, Any]] = [
        *((follow_up.observed_at, "follow_up", follow_up) for follow_up in follow_ups),
        *((event.occurred_at, event.event_kind, event) for event in events),
    ]
    timeline.sort(key=lambda item: item[0])
    for occurred_at, kind, item in timeline:
        if kind == "follow_up":
            open_supersessions = []
            next_review = max(next_review, occurred_at.date() + timedelta(days=cadence))
        elif kind == "evidence_superseded":
            open_supersessions.append(item)
        elif kind == "stopped":
            stopped = True
            stop_event = item
        elif kind == "reopened":
            stopped = False
            stop_event = None
            next_review = max(next_review, occurred_at.date() + timedelta(days=cadence))
    superseded_by = [json.loads(event.details) for event in events if event.event_kind == "evidence_superseded"]
    stop_conditions_met = (
        json.loads(commitment.stop_conditions_met) if commitment is not None else []
    )
    if stopped:
        state = "stopped"
    elif open_supersessions:
        state = "review_required"
    elif today >= next_review:
        state = "review_due"
    else:
        state = "active"
    if record.subject_verdict == "insufficient_evidence" or json.loads(
        record.evidence_gaps_acknowledged
    ):
        evidence_status = "insufficient"
    else:
        evidence_status = "as_recorded"
    if superseded_by:
        evidence_status = "superseded"
    reasons: list[str] = []
    if state == "stopped" and stop_event is not None:
        reasons.append(f"Stopped ({stop_event.reason_code}): {stop_event.reason}")
    elif state == "review_required":
        for event in open_supersessions:
            reasons.append(event.reason)
    elif state == "review_due":
        reasons.append(
            f"The review was due on {next_review.isoformat()} (observation window closed)."
        )
    else:
        reasons.append(
            f"Active until a stop condition is met; next review on {next_review.isoformat()}."
        )
    if evidence_status == "insufficient":
        reasons.append("The decision was recorded on insufficient evidence (gaps acknowledged).")
    if stop_conditions_met and state != "stopped":
        reasons.append(
            "Stop condition(s) met at record time: "
            + ", ".join(stop_conditions_met)
            + "; the owner may stop the commitment."
        )
    latest_supersession = superseded_by[-1] if superseded_by else None
    return {
        "state": state,
        "evidence_status": evidence_status,
        "next_review_due_on": None if stopped else next_review.isoformat(),
        "stop_recommended": bool(stop_conditions_met) and not stopped,
        "stop_conditions_met": stop_conditions_met,
        "reasons": reasons,
        "open_supersessions": [json.loads(event.details) for event in open_supersessions],
        "superseded_by": latest_supersession,
        "proactive_review": state in REVIEW_QUEUE_STATES,
    }


def serialize_follow_up(
    follow_up: DecisionFollowUpRecord, *, success: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
        "attribution_review": serialize_attribution_review(follow_up),
        "attention": {
            "minutes": follow_up.attention_minutes,
            "value_status": "user_entered" if follow_up.attention_minutes is not None else None,
            "capture_coverage": (
                "captured" if follow_up.attention_minutes is not None else "not_captured"
            ),
        },
        "actor": _serialize_actor(follow_up.actor),
        "created_at": follow_up.created_at.isoformat(),
    }
    if success is not None:
        payload["success"] = success
    return payload


def serialize_lifecycle_event(event: DecisionLifecycleEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "decision_id": event.decision_id,
        "event_kind": event.event_kind,
        "reason_code": event.reason_code,
        "reason": event.reason,
        "details": json.loads(event.details),
        "actor": _serialize_actor(event.actor),
        "occurred_at": event.occurred_at.isoformat(),
    }


def serialize_attribution_review(follow_up: DecisionFollowUpRecord) -> dict[str, Any]:
    """Measured result, estimated baseline and attribution, kept apart (HLA-K03)."""
    measured = follow_up.realized_value_eur
    estimate = follow_up.estimated_baseline_eur
    confounders = json.loads(follow_up.confounders or "[]")
    missing = json.loads(follow_up.missing_evidence or "[]")
    recorded = {
        "measured_result": measured is not None,
        "estimated_baseline": estimate is not None,
        "attribution_hypothesis": follow_up.attribution_hypothesis is not None,
        "confounders": bool(confounders),
        "uncertainty": follow_up.attribution_uncertainty is not None,
    }
    return {
        "measured": {
            "value_eur": str(measured) if measured is not None else None,
            "value_status": follow_up.realized_value_status,
        },
        "estimated_baseline": (
            {
                "value_eur": str(estimate),
                "value_status": "estimated",
                "basis": follow_up.estimated_baseline_basis,
            }
            if estimate is not None
            else None
        ),
        "measured_minus_estimate_eur": (
            str(measured - estimate) if measured is not None and estimate is not None else None
        ),
        "attribution_hypothesis": follow_up.attribution_hypothesis,
        "confounders": confounders,
        "uncertainty": follow_up.attribution_uncertainty,
        "missing_evidence": missing,
        "not_recorded": [key for key, present in recorded.items() if not present],
        "causal_claim": False,
    }


def serialize_commitment(commitment: DecisionCommitment | None) -> dict[str, Any] | None:
    if commitment is None:
        return None
    return {
        "purpose": commitment.purpose,
        "owner": {
            "role": commitment.owner_role,
            "principal": commitment.owner_principal,
            "verified": commitment.owner_verified,
        },
        "baseline": json.loads(commitment.baseline),
        "success_measure": json.loads(commitment.success_measure),
        "observation_window": {
            "start": commitment.observation_window_start.isoformat(),
            "end": commitment.observation_window_end.isoformat(),
            "review_cadence_days": commitment.review_cadence_days,
        },
        "first_review_due_on": commitment.next_review_due_on.isoformat(),
        "review_triggers": json.loads(commitment.review_triggers),
        "stop_conditions": json.loads(commitment.stop_conditions),
        "stop_conditions_met": json.loads(commitment.stop_conditions_met),
        "evidence_fingerprint": commitment.evidence_fingerprint,
        "evidence_components": json.loads(commitment.evidence_components),
    }


def serialize_decision(
    record: DecisionRecord,
    follow_ups: list[DecisionFollowUpRecord],
    lifecycle_events: list[DecisionLifecycleEvent] | None = None,
    *,
    today: date | None = None,
    include_snapshot: bool = False,
) -> dict[str, Any]:
    events = lifecycle_events or []
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
        "decided_at": record.effective_decided_at.isoformat(),
        "entry_mode": "retrospective" if record.is_retrospective else "contemporaneous",
        "retrospective_basis": record.retrospective_basis,
        "follow_up_due_on": record.follow_up_due_on.isoformat(),
        "created_at": record.created_at.isoformat(),
        "status": "followed_up" if follow_ups else "awaiting_follow_up",
        "actuation_authorized": False,
        "commitment": serialize_commitment(record.commitment),
        "lifecycle": derive_commitment_state(
            record, follow_ups, events, today=today or datetime.now(UTC).date()
        ),
        "history": [serialize_lifecycle_event(event) for event in events],
        "follow_ups": [
            serialize_follow_up(item, success=evaluate_follow_up_success(record, item))
            for item in follow_ups
        ],
    }
    if include_snapshot:
        payload["evidence_snapshot"] = json.loads(record.evidence_snapshot)
    return payload


def load_serialized_decision(
    store: DecisionLedgerStore,
    record: DecisionRecord,
    *,
    today: date | None = None,
    include_snapshot: bool = False,
) -> dict[str, Any]:
    return serialize_decision(
        record,
        store.list_decision_follow_ups(record.decision_id),
        store.list_decision_lifecycle_events(record.decision_id),
        today=today,
        include_snapshot=include_snapshot,
    )


def list_commitment_reviews(
    store: DecisionLedgerStore,
    *,
    today: date,
    decision_key: str | None = None,
) -> list[dict[str, Any]]:
    """The proactive review queue: due or required reviews, never stopped ones."""
    queue: list[dict[str, Any]] = []
    for record in store.list_decision_records(decision_key=decision_key):
        payload = load_serialized_decision(store, record, today=today)
        lifecycle = payload["lifecycle"]
        if lifecycle["state"] in REVIEW_QUEUE_STATES:
            queue.append(
                {
                    "decision_id": record.decision_id,
                    "decision_key": record.decision_key,
                    "subject_period": record.subject_period,
                    "state": lifecycle["state"],
                    "next_review_due_on": lifecycle["next_review_due_on"],
                    "reasons": lifecycle["reasons"],
                    "evidence_status": lifecycle["evidence_status"],
                }
            )
    return queue


def _serialize_actor(actor: DecisionActor) -> dict[str, Any]:
    return {
        "actor": actor.actor,
        "role": actor.actor_role,
        "auth_provider": actor.actor_auth_provider,
        "authenticated": actor.actor_authenticated,
    }


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
