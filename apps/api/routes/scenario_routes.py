"""Scenario API routes — loan, income, and homelab what-if scenarios.

  POST /api/scenarios/loan-what-if      → create loan scenario, return scenario_id + headline deltas
  POST /api/scenarios/income-change     → create income scenario, return scenario_id + headline deltas
  POST /api/scenarios/homelab-cost-benefit
                                        → create homelab scenario, return summary deltas
  GET  /api/scenarios/{id}              → scenario metadata + status
  GET  /api/scenarios/{id}/comparison   → baseline vs projected rows + variance + staleness
  GET  /api/scenarios/{id}/cashflow     → projected cashflow rows for income_change scenario
  GET  /api/scenarios/{id}/assumptions  → assumption list
  DELETE /api/scenarios/{id}            → archive (soft delete, preserves projection rows)
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import packages.application.use_cases.scenario_management as scenario_management
from packages.pipelines.reporting_service import HomelabCostBenefitBaseline, ReportingService
from packages.pipelines.transformation_service import TransformationService


class LoanWhatIfRequest(BaseModel):
    loan_id: str
    label: str | None = None
    extra_repayment: str | None = None   # decimal string, e.g. "500.00"
    annual_rate: str | None = None       # decimal string, e.g. "0.035"
    term_months: int | None = None


class IncomeChangeRequest(BaseModel):
    monthly_income_delta: str            # decimal string, may be negative e.g. "-500.00"
    currency: str = "GBP"               # ISO 4217 code for the delta amount
    label: str | None = None
    projection_months: int | None = None  # default 12


class ExpenseShockRequest(BaseModel):
    expense_pct_delta: str               # decimal fraction, e.g. "0.10" = 10% increase
    label: str | None = None
    projection_months: int | None = None  # default 12


class TariffShockRequest(BaseModel):
    tariff_pct_delta: str                # decimal fraction, e.g. "0.10" = 10% increase
    utility_type: str | None = None
    label: str | None = None
    projection_months: int | None = None  # default 12


class HomelabCostBenefitRequest(BaseModel):
    monthly_cost_delta: str
    label: str | None = None


class ScenarioCompareSetRequest(BaseModel):
    left_scenario_id: str
    right_scenario_id: str
    label: str | None = None


class ScenarioCompareSetUpdateRequest(BaseModel):
    label: str


def register_scenario_routes(
    app: FastAPI,
    *,
    transformation_service: TransformationService | None,
    resolved_reporting_service: ReportingService | None = None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    def _svc() -> TransformationService:
        if transformation_service is not None:
            return transformation_service
        raise HTTPException(
            status_code=503,
            detail="Scenario service requires a transformation service.",
        )

    def _homelab_baseline() -> HomelabCostBenefitBaseline | None:
        if resolved_reporting_service is None:
            return None
        return resolved_reporting_service.get_homelab_cost_benefit_baseline()

    @app.post("/api/scenarios/loan-what-if")
    async def create_loan_what_if(body: LoanWhatIfRequest) -> dict[str, Any]:
        svc = _svc()
        try:
            result = scenario_management.create_loan_what_if(
                svc,
                body.loan_id,
                label=body.label,
                extra_repayment=Decimal(body.extra_repayment) if body.extra_repayment else None,
                annual_rate=Decimal(body.annual_rate) if body.annual_rate else None,
                term_months=body.term_months,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        assumptions_summary = None
        if result.assumptions_summary is not None:
            assumptions_summary = [
                {
                    "source_asset_id": item.source_asset_id,
                    "freshness_state": item.freshness_state,
                    "last_ingest_at": item.last_ingest_at.isoformat() if item.last_ingest_at else None,
                    "covered_through": item.covered_through.isoformat() if item.covered_through else None,
                }
                for item in result.assumptions_summary
            ]
        return {
            "scenario_id": result.scenario_id,
            "label": result.label,
            "months_saved": result.months_saved,
            "interest_saved": str(result.interest_saved),
            "new_payoff_date": result.new_payoff_date.isoformat() if result.new_payoff_date else None,
            "baseline_payoff_date": result.baseline_payoff_date.isoformat() if result.baseline_payoff_date else None,
            "is_stale": result.is_stale,
            "assumptions_summary": assumptions_summary,
        }

    @app.get("/api/scenarios")
    async def list_scenarios_route(include_archived: bool = False) -> dict[str, Any]:
        svc = _svc()
        rows = scenario_management.list_scenarios(svc, include_archived=include_archived)
        return {"rows": to_jsonable(rows)}

    @app.get("/api/scenarios/compare-sets")
    async def list_scenario_compare_sets_route(include_archived: bool = False) -> dict[str, Any]:
        svc = _svc()
        rows = scenario_management.list_compare_sets(svc, include_archived=include_archived)
        return {"rows": to_jsonable(rows)}

    @app.post("/api/scenarios/compare-sets")
    async def create_scenario_compare_set_route(body: ScenarioCompareSetRequest) -> dict[str, Any]:
        svc = _svc()
        try:
            result = scenario_management.create_compare_set(
                svc,
                left_scenario_id=body.left_scenario_id,
                right_scenario_id=body.right_scenario_id,
                label=body.label,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return to_jsonable(result)

    @app.patch("/api/scenarios/compare-sets/{compare_set_id}")
    async def update_scenario_compare_set_route(
        compare_set_id: str,
        body: ScenarioCompareSetUpdateRequest,
    ) -> dict[str, Any]:
        svc = _svc()
        try:
            result = scenario_management.update_compare_set_label(svc, compare_set_id, label=body.label)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="Scenario compare set not found.")
        return to_jsonable(result)

    @app.get("/api/scenarios/{scenario_id}")
    async def get_scenario_metadata(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        scenario = scenario_management.get_scenario(svc, scenario_id)
        if scenario is None:
            raise HTTPException(status_code=404, detail="Scenario not found.")
        return to_jsonable(scenario)

    @app.get("/api/scenarios/{scenario_id}/comparison")
    async def get_scenario_comparison(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        comparison = scenario_management.load_scenario_comparison(
            svc, scenario_id, homelab_baseline=_homelab_baseline()
        )
        if comparison is None:
            raise HTTPException(status_code=404, detail="Scenario not found.")
        if hasattr(comparison, "summary_rows"):
            return {
                "scenario_id": comparison.scenario_id,
                "label": comparison.label,
                "is_stale": comparison.is_stale,
                "assumptions": to_jsonable(comparison.assumptions),
                "summary_rows": to_jsonable(comparison.summary_rows),
            }
        return {
            "scenario_id": comparison.scenario_id,
            "label": comparison.label,
            "is_stale": comparison.is_stale,
            "assumptions": to_jsonable(comparison.assumptions),
            "baseline_rows": to_jsonable(comparison.baseline_rows),
            "scenario_rows": to_jsonable(comparison.scenario_rows),
            "variance_rows": to_jsonable(comparison.variance_rows),
        }

    @app.post("/api/scenarios/income-change")
    async def create_income_change(body: IncomeChangeRequest) -> dict[str, Any]:
        svc = _svc()
        try:
            delta = Decimal(body.monthly_income_delta)
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid monthly_income_delta: {body.monthly_income_delta!r}",
            ) from exc
        try:
            result = scenario_management.create_income_change(
                svc,
                monthly_income_delta=delta,
                currency=body.currency,
                label=body.label,
                projection_months=body.projection_months or 12,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        assumptions_summary = None
        if result.assumptions_summary is not None:
            assumptions_summary = [
                {
                    "source_asset_id": item.source_asset_id,
                    "freshness_state": item.freshness_state,
                    "last_ingest_at": item.last_ingest_at.isoformat() if item.last_ingest_at else None,
                    "covered_through": item.covered_through.isoformat() if item.covered_through else None,
                }
                for item in result.assumptions_summary
            ]
        return {
            "scenario_id": result.scenario_id,
            "label": result.label,
            "monthly_income_delta": str(result.monthly_income_delta),
            "new_monthly_income": str(result.new_monthly_income),
            "baseline_monthly_income": str(result.baseline_monthly_income),
            "annual_net_change": str(result.annual_net_change),
            "months_until_deficit": result.months_until_deficit,
            "is_stale": result.is_stale,
            "assumptions_summary": assumptions_summary,
        }

    @app.post("/api/scenarios/expense-shock")
    async def create_expense_shock(body: ExpenseShockRequest) -> dict[str, Any]:
        svc = _svc()
        try:
            pct = Decimal(body.expense_pct_delta)
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid expense_pct_delta: {body.expense_pct_delta!r}",
            ) from exc
        try:
            result = scenario_management.create_expense_shock(
                svc,
                expense_pct_delta=pct,
                label=body.label,
                projection_months=body.projection_months or 12,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        assumptions_summary = None
        if result.assumptions_summary is not None:
            assumptions_summary = [
                {
                    "source_asset_id": item.source_asset_id,
                    "freshness_state": item.freshness_state,
                    "last_ingest_at": item.last_ingest_at.isoformat() if item.last_ingest_at else None,
                    "covered_through": item.covered_through.isoformat() if item.covered_through else None,
                }
                for item in result.assumptions_summary
            ]
        return {
            "scenario_id": result.scenario_id,
            "label": result.label,
            "expense_pct_delta": str(result.expense_pct_delta),
            "new_monthly_expense": str(result.new_monthly_expense),
            "baseline_monthly_expense": str(result.baseline_monthly_expense),
            "annual_additional_cost": str(result.annual_additional_cost),
            "months_until_deficit": result.months_until_deficit,
            "is_stale": result.is_stale,
            "assumptions_summary": assumptions_summary,
        }

    @app.post("/api/scenarios/tariff-shock")
    async def create_tariff_shock(body: TariffShockRequest) -> dict[str, Any]:
        svc = _svc()
        try:
            pct = Decimal(body.tariff_pct_delta)
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid tariff_pct_delta: {body.tariff_pct_delta!r}",
            ) from exc
        try:
            result = scenario_management.create_tariff_shock(
                svc,
                tariff_pct_delta=pct,
                utility_type=body.utility_type or "electricity",
                label=body.label,
                projection_months=body.projection_months or 12,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        assumptions_summary = None
        if result.assumptions_summary is not None:
            assumptions_summary = [
                {
                    "source_asset_id": item.source_asset_id,
                    "freshness_state": item.freshness_state,
                    "last_ingest_at": item.last_ingest_at.isoformat() if item.last_ingest_at else None,
                    "covered_through": item.covered_through.isoformat() if item.covered_through else None,
                }
                for item in result.assumptions_summary
            ]
        return {
            "scenario_id": result.scenario_id,
            "label": result.label,
            "tariff_pct_delta": str(result.tariff_pct_delta),
            "baseline_monthly_utility_cost": str(result.baseline_monthly_utility_cost),
            "new_monthly_utility_cost": str(result.new_monthly_utility_cost),
            "annual_additional_cost": str(result.annual_additional_cost),
            "months_until_deficit": result.months_until_deficit,
            "is_stale": result.is_stale,
            "assumptions_summary": assumptions_summary,
        }

    @app.post("/api/scenarios/homelab-cost-benefit")
    async def create_homelab_cost_benefit(body: HomelabCostBenefitRequest) -> dict[str, Any]:
        svc = _svc()
        try:
            monthly_cost_delta = Decimal(body.monthly_cost_delta)
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid monthly_cost_delta: {body.monthly_cost_delta!r}",
            ) from exc
        try:
            result = scenario_management.create_homelab_cost_benefit(
                svc,
                monthly_cost_delta=monthly_cost_delta,
                label=body.label,
                homelab_baseline=_homelab_baseline(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        assumptions_summary = None
        if result.assumptions_summary is not None:
            assumptions_summary = [
                {
                    "source_asset_id": item.source_asset_id,
                    "freshness_state": item.freshness_state,
                    "last_ingest_at": item.last_ingest_at.isoformat() if item.last_ingest_at else None,
                    "covered_through": item.covered_through.isoformat() if item.covered_through else None,
                }
                for item in result.assumptions_summary
            ]
        return {
            "scenario_id": result.scenario_id,
            "label": result.label,
            "monthly_cost_delta": str(result.monthly_cost_delta),
            "baseline_monthly_cost": str(result.baseline_monthly_cost),
            "new_monthly_cost": str(result.new_monthly_cost),
            "annual_cost_delta": str(result.annual_cost_delta),
            "is_stale": result.is_stale,
            "assumptions_summary": assumptions_summary,
        }

    @app.delete("/api/scenarios/compare-sets/{compare_set_id}")
    async def archive_scenario_compare_set(compare_set_id: str) -> dict[str, Any]:
        svc = _svc()
        archived = scenario_management.archive_compare_set(svc, compare_set_id)
        if not archived:
            raise HTTPException(status_code=404, detail="Scenario compare set not found.")
        return {"compare_set_id": compare_set_id, "status": "archived"}

    @app.post("/api/scenarios/compare-sets/{compare_set_id}/restore")
    async def restore_scenario_compare_set(compare_set_id: str) -> dict[str, Any]:
        svc = _svc()
        try:
            result = scenario_management.restore_compare_set(svc, compare_set_id)
        except ValueError as exc:
            status_code = 409 if "active compare set already exists" in str(exc) else 422
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="Scenario compare set not found.")
        return to_jsonable(result)

    @app.get("/api/scenarios/{scenario_id}/cashflow")
    async def get_income_scenario_cashflow(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        cashflow = scenario_management.load_scenario_cashflow(
            svc, scenario_id, homelab_baseline=_homelab_baseline()
        )
        if cashflow is None:
            raise HTTPException(status_code=404, detail="Scenario not found.")
        if hasattr(cashflow, "summary_rows"):
            return {
                "scenario_id": cashflow.scenario_id,
                "label": cashflow.label,
                "is_stale": cashflow.is_stale,
                "assumptions": to_jsonable(cashflow.assumptions),
                "summary_rows": to_jsonable(cashflow.summary_rows),
            }
        return {
            "scenario_id": cashflow.scenario_id,
            "label": cashflow.label,
            "is_stale": cashflow.is_stale,
            "assumptions": to_jsonable(cashflow.assumptions),
            "cashflow_rows": to_jsonable(cashflow.cashflow_rows),
        }

    @app.get("/api/scenarios/{scenario_id}/assumptions")
    async def get_scenario_assumptions(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        rows = scenario_management.get_scenario_assumptions(svc, scenario_id)
        return {"rows": to_jsonable(rows)}

    @app.delete("/api/scenarios/{scenario_id}")
    async def archive_scenario(scenario_id: str) -> dict[str, Any]:
        svc = _svc()
        archived = scenario_management.archive_scenario(svc, scenario_id)
        if not archived:
            raise HTTPException(status_code=404, detail="Scenario not found.")
        return {"scenario_id": scenario_id, "status": "archived"}
