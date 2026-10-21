"""Decision ledger routes: record household decisions against published evidence.

Reads require ``control.decisions.read`` (reader); writes require
``control.decisions.write`` (operator, the declared decision-maker role). No
route here can change a tariff, contract or device: a decision record is a
record, not an authorization.

Beyond record/follow-up, the routes expose the commitment lifecycle (owner
stop/reopen, the proactive review queue), evidence-correction tracing and the
portable outcome-reference export. The export is pull-only: nothing here
makes an outbound call.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from apps.api.support import to_jsonable
from packages.application.use_cases.decision_evidence_trace import (
    trace_evidence_corrections,
)
from packages.application.use_cases.decision_ledger import (
    DecisionAuthorizationError,
    DecisionRequest,
    DecisionStateConflictError,
    DecisionSubjectConflictError,
    DecisionValidationError,
    FollowUpRequest,
    actor_from_principal,
    list_commitment_reviews,
    load_serialized_decision,
    record_decision,
    record_follow_up,
    reopen_commitment,
    serialize_follow_up,
    serialize_lifecycle_event,
    stop_commitment,
)
from packages.application.use_cases.decision_outcome_reference import (
    latest_outcome_reference,
    outcome_reference_feed,
)
from packages.pipelines.household_decisions import (
    DECISION_DEFINITIONS,
    get_decision_definition,
    list_decision_subjects,
    read_decision_subject,
    snapshot_evidence_components,
)
from packages.pipelines.reporting_service import ReportingService
from packages.platform.decision_definitions import DecisionSubjectEvidence
from packages.storage.decision_ledger import DecisionLedgerStore


class DecisionCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    decision_key: str
    subject_period: str = Field(
        description="Subject period of the decision (see the definition's subject_period_label)."
    )
    subject_row_ref: str | None = Field(
        default=None,
        description="Row reference (assessment_id) the decision-maker reviewed; refused if stale.",
    )
    outcome: str
    rationale: str
    evidence_gaps_acknowledged: list[str] = Field(default_factory=list)
    uncertainty: str | None = None
    follow_up_due_on: date | None = Field(
        default=None,
        description="Optional review date; may not fall before the observation window closes.",
    )
    decided_at: datetime | None = Field(
        default=None,
        description=(
            "Retrospective entry: when the household actually decided, if earlier than now. "
            "The observation window derives from it; requires retrospective_basis."
        ),
    )
    retrospective_basis: str | None = Field(
        default=None,
        description="What shows the decision was made then (contract date, bill, note).",
    )


class DecisionFollowUpCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    observed_at: datetime
    realized_result: str
    evidence_effect: str
    observation_period: str | None = None
    realized_value_eur: Decimal | None = None
    realized_value_status: str | None = None
    notes: str | None = None
    baseline_value_key: str | None = Field(
        default=None,
        description="Compare with this value pinned in the decision's commitment baseline.",
    )
    estimated_baseline_eur: Decimal | None = Field(
        default=None,
        description="Explicit estimate to compare with; requires estimated_baseline_basis.",
    )
    estimated_baseline_basis: str | None = None
    attribution_hypothesis: str | None = None
    confounders: list[str] = Field(default_factory=list)
    attribution_uncertainty: str | None = None
    missing_evidence: list[str] = Field(default_factory=list)
    attention_minutes: int | None = Field(
        default=None,
        description="Operator minutes spent on this review; omit when unknown (never zero).",
    )


class CommitmentStopRequest(BaseModel):
    model_config = {"extra": "forbid"}

    stop_condition_key: str
    reason: str


class CommitmentReopenRequest(BaseModel):
    model_config = {"extra": "forbid"}

    reason: str


class EvidenceTraceRequest(BaseModel):
    model_config = {"extra": "forbid"}

    decision_key: str | None = None


def serialize_subject(subject: DecisionSubjectEvidence) -> dict[str, Any]:
    return to_jsonable({
        "publication_key": subject.publication_key,
        "schema_version": subject.schema_version,
        "period": subject.period,
        "row_ref": subject.row_ref,
        "verdict": subject.verdict,
        "reason_codes": list(subject.reason_codes),
        "baseline": subject.baseline,
        "evidence_fingerprint": subject.evidence_fingerprint,
        "lineage_reference": subject.lineage_reference,
        "snapshot": subject.snapshot,
    })


def register_decision_routes(
    app: FastAPI,
    *,
    resolved_config_repository: object,
    resolved_reporting_service: ReportingService | None,
) -> None:
    def _ledger() -> DecisionLedgerStore:
        if not isinstance(resolved_config_repository, DecisionLedgerStore):
            raise HTTPException(
                status_code=404, detail="The control plane has no decision ledger."
            )
        return resolved_config_repository

    def _reporting() -> ReportingService:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404, detail="Decision evidence requires the reporting layer."
            )
        return resolved_reporting_service

    def _today() -> date:
        return datetime.now(UTC).date()

    def _actor(request: Request) -> Any:
        return actor_from_principal(cast(Any, getattr(request.state, "principal", None)))

    @app.get("/control/decisions/definitions")
    async def list_decision_definitions() -> dict[str, Any]:
        return {
            "definitions": [definition.to_dict() for definition in DECISION_DEFINITIONS.values()]
        }

    @app.get("/control/decisions/definitions/{decision_key}/subjects")
    async def list_decision_subject_evidence(
        decision_key: str, period: str | None = None
    ) -> dict[str, Any]:
        definition = get_decision_definition(decision_key)
        if definition is None:
            raise HTTPException(status_code=404, detail="Unknown decision.")
        reporting = _reporting()
        if period is not None:
            subject = read_decision_subject(decision_key, reporting, period)
            subjects = [subject] if subject is not None else []
        else:
            subjects = list_decision_subjects(decision_key, reporting)
        return {
            "decision": definition.to_dict(),
            "subjects": [serialize_subject(subject) for subject in subjects],
        }

    @app.get("/control/decisions/reviews")
    async def list_decision_reviews(decision_key: str | None = None) -> dict[str, Any]:
        """Commitments whose review is due or required; stopped ones never appear."""
        return {
            "as_of": _today().isoformat(),
            "reviews": list_commitment_reviews(
                _ledger(), today=_today(), decision_key=decision_key
            ),
        }

    @app.get("/control/decisions/outcome-references")
    async def list_outcome_references(
        decision_key: str | None = None, latest_only: bool = False
    ) -> dict[str, Any]:
        return outcome_reference_feed(
            _ledger(), decision_key=decision_key, include_history=not latest_only
        )

    @app.post("/control/decisions/evidence-trace")
    async def trace_decision_evidence(body: EvidenceTraceRequest) -> dict[str, Any]:
        """Mark decisions whose evidence was corrected since they were recorded."""
        ledger = _ledger()
        reporting = _reporting()
        report = trace_evidence_corrections(
            ledger,
            definition_lookup=get_decision_definition,
            subject_reader=lambda key, period: read_decision_subject(key, reporting, period),
            snapshot_components=snapshot_evidence_components,
            decision_key=body.decision_key,
        )
        return {"trace": report.as_dict()}

    @app.get("/control/decisions")
    async def list_decisions(
        decision_key: str | None = None,
        subject_period: str | None = None,
    ) -> dict[str, Any]:
        ledger = _ledger()
        records = ledger.list_decision_records(
            decision_key=decision_key, subject_period=subject_period
        )
        today = _today()
        return {
            "decisions": [
                load_serialized_decision(ledger, record, today=today) for record in records
            ]
        }

    @app.post("/control/decisions", status_code=201)
    async def create_decision(body: DecisionCreateRequest, request: Request) -> dict[str, Any]:
        ledger = _ledger()
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404, detail="Recording a decision requires the reporting layer."
            )
        reporting = resolved_reporting_service
        try:
            record = record_decision(
                ledger,
                definition_lookup=get_decision_definition,
                subject_reader=lambda key, period: read_decision_subject(key, reporting, period),
                request=DecisionRequest(
                    decision_key=body.decision_key,
                    subject_period=body.subject_period,
                    subject_row_ref=body.subject_row_ref,
                    outcome=body.outcome,
                    rationale=body.rationale,
                    evidence_gaps_acknowledged=tuple(body.evidence_gaps_acknowledged),
                    uncertainty=body.uncertainty,
                    follow_up_due_on=body.follow_up_due_on,
                    decided_at=body.decided_at,
                    retrospective_basis=body.retrospective_basis,
                ),
                actor=_actor(request),
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'\"")) from exc
        except DecisionAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DecisionSubjectConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DecisionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "decision": load_serialized_decision(
                ledger, record, today=_today(), include_snapshot=True
            )
        }

    @app.get("/control/decisions/{decision_id}")
    async def get_decision(decision_id: str) -> dict[str, Any]:
        ledger = _ledger()
        try:
            record = ledger.get_decision_record(decision_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown decision.") from exc
        return {
            "decision": load_serialized_decision(
                ledger, record, today=_today(), include_snapshot=True
            )
        }

    @app.get("/control/decisions/{decision_id}/outcome-reference")
    async def get_outcome_reference(decision_id: str) -> dict[str, Any]:
        try:
            latest, revisions = latest_outcome_reference(_ledger(), decision_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown decision.") from exc
        return {"reference": latest, "revisions": revisions}

    @app.post("/control/decisions/{decision_id}/follow-ups", status_code=201)
    async def create_decision_follow_up(
        decision_id: str,
        body: DecisionFollowUpCreateRequest,
        request: Request,
    ) -> dict[str, Any]:
        ledger = _ledger()
        try:
            follow_up = record_follow_up(
                ledger,
                decision_id=decision_id,
                request=FollowUpRequest(
                    observed_at=body.observed_at,
                    realized_result=body.realized_result,
                    evidence_effect=body.evidence_effect,
                    observation_period=body.observation_period,
                    realized_value_eur=body.realized_value_eur,
                    realized_value_status=body.realized_value_status,
                    notes=body.notes,
                    baseline_value_key=body.baseline_value_key,
                    estimated_baseline_eur=body.estimated_baseline_eur,
                    estimated_baseline_basis=body.estimated_baseline_basis,
                    attribution_hypothesis=body.attribution_hypothesis,
                    confounders=tuple(body.confounders),
                    attribution_uncertainty=body.attribution_uncertainty,
                    missing_evidence=tuple(body.missing_evidence),
                    attention_minutes=body.attention_minutes,
                ),
                actor=_actor(request),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown decision.") from exc
        except DecisionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"follow_up": serialize_follow_up(follow_up)}

    @app.post("/control/decisions/{decision_id}/stop", status_code=201)
    async def stop_decision_commitment(
        decision_id: str, body: CommitmentStopRequest, request: Request
    ) -> dict[str, Any]:
        ledger = _ledger()
        try:
            event = stop_commitment(
                ledger,
                decision_id=decision_id,
                stop_condition_key=body.stop_condition_key,
                reason=body.reason,
                actor=_actor(request),
                definition_lookup=get_decision_definition,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown decision.") from exc
        except DecisionAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DecisionStateConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DecisionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"event": serialize_lifecycle_event(event)}

    @app.post("/control/decisions/{decision_id}/reopen", status_code=201)
    async def reopen_decision_commitment(
        decision_id: str, body: CommitmentReopenRequest, request: Request
    ) -> dict[str, Any]:
        ledger = _ledger()
        try:
            event = reopen_commitment(
                ledger,
                decision_id=decision_id,
                reason=body.reason,
                actor=_actor(request),
                definition_lookup=get_decision_definition,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown decision.") from exc
        except DecisionAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DecisionStateConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DecisionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"event": serialize_lifecycle_event(event)}
