"""Decision ledger routes: record household decisions against published evidence.

Reads require ``control.decisions.read`` (reader); writes require
``control.decisions.write`` (operator, the declared decision-maker role). No
route here can change a tariff, contract or device: a decision record is a
record, not an authorization.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from packages.application.use_cases.decision_ledger import (
    DecisionRequest,
    DecisionSubjectConflictError,
    DecisionValidationError,
    FollowUpRequest,
    actor_from_principal,
    record_decision,
    record_follow_up,
    serialize_decision,
    serialize_follow_up,
)
from packages.pipelines.household_decisions import (
    DECISION_DEFINITIONS,
    get_decision_definition,
    read_decision_subject,
)
from packages.pipelines.reporting_service import ReportingService
from packages.storage.decision_ledger import DecisionLedgerStore


class DecisionCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    decision_key: str
    subject_period: str = Field(description="Period of the subject publication row, e.g. 2026-01.")
    subject_row_ref: str | None = Field(
        default=None,
        description="Row reference (assessment_id) the decision-maker reviewed; refused if stale.",
    )
    outcome: str
    rationale: str
    evidence_gaps_acknowledged: list[str] = Field(default_factory=list)
    uncertainty: str | None = None
    follow_up_due_on: date | None = None


class DecisionFollowUpCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    observed_at: datetime
    realized_result: str
    evidence_effect: str
    observation_period: str | None = None
    realized_value_eur: Decimal | None = None
    realized_value_status: str | None = None
    notes: str | None = None


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

    def _with_follow_ups(ledger: DecisionLedgerStore, record: Any, **kwargs: Any) -> dict[str, Any]:
        return serialize_decision(
            record, ledger.list_decision_follow_ups(record.decision_id), **kwargs
        )

    @app.get("/control/decisions/definitions")
    async def list_decision_definitions() -> dict[str, Any]:
        return {
            "definitions": [definition.to_dict() for definition in DECISION_DEFINITIONS.values()]
        }

    @app.get("/control/decisions")
    async def list_decisions(
        decision_key: str | None = None,
        subject_period: str | None = None,
    ) -> dict[str, Any]:
        ledger = _ledger()
        records = ledger.list_decision_records(
            decision_key=decision_key, subject_period=subject_period
        )
        return {"decisions": [_with_follow_ups(ledger, record) for record in records]}

    @app.post("/control/decisions", status_code=201)
    async def create_decision(body: DecisionCreateRequest, request: Request) -> dict[str, Any]:
        ledger = _ledger()
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404, detail="Recording a decision requires the reporting layer."
            )
        reporting = resolved_reporting_service
        principal = cast(Any, getattr(request.state, "principal", None))
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
                ),
                actor=actor_from_principal(principal),
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'\"")) from exc
        except DecisionSubjectConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DecisionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"decision": _with_follow_ups(ledger, record, include_snapshot=True)}

    @app.get("/control/decisions/{decision_id}")
    async def get_decision(decision_id: str) -> dict[str, Any]:
        ledger = _ledger()
        try:
            record = ledger.get_decision_record(decision_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown decision.") from exc
        return {"decision": _with_follow_ups(ledger, record, include_snapshot=True)}

    @app.post("/control/decisions/{decision_id}/follow-ups", status_code=201)
    async def create_decision_follow_up(
        decision_id: str,
        body: DecisionFollowUpCreateRequest,
        request: Request,
    ) -> dict[str, Any]:
        ledger = _ledger()
        principal = cast(Any, getattr(request.state, "principal", None))
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
                ),
                actor=actor_from_principal(principal),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown decision.") from exc
        except DecisionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"follow_up": serialize_follow_up(follow_up)}
