"""Scenario API routes — loan what-if scenarios.

  POST /api/scenarios/loan-what-if      → create scenario, return scenario_id + headline deltas
  GET  /api/scenarios/{id}              → scenario metadata + status
  GET  /api/scenarios/{id}/comparison   → baseline vs projected rows + variance + staleness
  GET  /api/scenarios/{id}/assumptions  → assumption list
  DELETE /api/scenarios/{id}            → archive (soft delete, preserves projection rows)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from packages.pipelines.transformation_service import TransformationService


class LoanWhatIfRequest(BaseModel):
    loan_id: str
    label: str | None = None
    extra_repayment: str | None = None   # decimal string, e.g. "500.00"
    annual_rate: str | None = None       # decimal string, e.g. "0.035"
    term_months: int | None = None


def register_scenario_routes(
    app: FastAPI,
    *,
    transformation_service: TransformationService | None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    def _svc() -> TransformationService:
        if transformation_service is not None:
            return transformation_service
        raise HTTPException(
            status_code=503,
            detail="Scenario service requires a transformation service.",
        )

    @app.post("/api/scenarios/loan-what-if")
    async def create_loan_what_if(body: LoanWhatIfRequest) -> dict[str, Any]:
        svc = _svc()
        try:
            result = svc.create_loan_what_if_scenario(
                body.loan_id,
                label=body.label,
                extra_repayment=Decimal(body.extra_repayment) if body.extra_repayment else None,
                annual_rate=Decimal(body.annual_rate) if body.annual_rate else None,
                term_months=body.term_months,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "scenario_id": result.scenario_id,
            "label": result.label,
            "months_saved": result.months_saved,
            "interest_saved": str(result.interest_saved),
            "new_payoff_date": result.new_payoff_date.isoformat() if result.new_payoff_date else None,
            "baseline_payoff_date": result.baseline_payoff_date.isoformat() if result.baseline_payoff_date else None,
            "is_stale": result.is_stale,
        }

    @app.get("/api/scenarios/{scenario_id}")
    async def get_scenario_metadata(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        scenario = svc.get_scenario(scenario_id)
        if scenario is None:
            raise HTTPException(status_code=404, detail="Scenario not found.")
        return to_jsonable(scenario)

    @app.get("/api/scenarios/{scenario_id}/comparison")
    async def get_scenario_comparison(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        comparison = svc.get_scenario_comparison(scenario_id)
        if comparison is None:
            raise HTTPException(status_code=404, detail="Scenario not found.")
        return {
            "scenario_id": comparison.scenario_id,
            "label": comparison.label,
            "is_stale": comparison.is_stale,
            "assumptions": to_jsonable(comparison.assumptions),
            "baseline_rows": to_jsonable(comparison.baseline_rows),
            "scenario_rows": to_jsonable(comparison.scenario_rows),
            "variance_rows": to_jsonable(comparison.variance_rows),
        }

    @app.get("/api/scenarios/{scenario_id}/assumptions")
    async def get_scenario_assumptions(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        rows = svc.get_scenario_assumptions(scenario_id)
        return {"rows": to_jsonable(rows)}

    @app.delete("/api/scenarios/{scenario_id}")
    async def archive_scenario(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        archived = svc.archive_scenario(scenario_id)
        if not archived:
            raise HTTPException(status_code=404, detail="Scenario not found.")
        return {"scenario_id": scenario_id, "status": "archived"}
