"""Scenario service — create and retrieve loan what-if scenarios.

Delegates compute to the canonical amortization engine (compute_amortization_schedule).
Never reimplements amortization logic.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from packages.pipelines.amortization import LoanParameters, compute_amortization_schedule
from packages.pipelines.loan_models import (
    CURRENT_DIM_LOAN_VIEW,
    FACT_LOAN_REPAYMENT_TABLE,
    MART_LOAN_SCHEDULE_PROJECTED_TABLE,
)
from packages.pipelines.scenario_models import (
    DIM_SCENARIO_COLUMNS,
    DIM_SCENARIO_TABLE,
    FACT_SCENARIO_ASSUMPTION_COLUMNS,
    FACT_SCENARIO_ASSUMPTION_TABLE,
    PROJ_LOAN_REPAYMENT_VARIANCE_COLUMNS,
    PROJ_LOAN_REPAYMENT_VARIANCE_TABLE,
    PROJ_LOAN_SCHEDULE_COLUMNS,
    PROJ_LOAN_SCHEDULE_TABLE,
)
from packages.storage.duckdb_store import DuckDBStore


@dataclass
class ScenarioResult:
    scenario_id: str
    label: str
    months_saved: int
    interest_saved: Decimal
    new_payoff_date: date | None
    baseline_payoff_date: date | None
    is_stale: bool


@dataclass
class ComparisonResult:
    scenario_id: str
    label: str
    assumptions: list[dict[str, Any]]
    baseline_rows: list[dict[str, Any]]
    scenario_rows: list[dict[str, Any]]
    variance_rows: list[dict[str, Any]]
    is_stale: bool


def ensure_scenario_storage(store: DuckDBStore) -> None:
    store.ensure_table(DIM_SCENARIO_TABLE, DIM_SCENARIO_COLUMNS)
    store.ensure_table(FACT_SCENARIO_ASSUMPTION_TABLE, FACT_SCENARIO_ASSUMPTION_COLUMNS)
    store.ensure_table(PROJ_LOAN_SCHEDULE_TABLE, PROJ_LOAN_SCHEDULE_COLUMNS)
    store.ensure_table(PROJ_LOAN_REPAYMENT_VARIANCE_TABLE, PROJ_LOAN_REPAYMENT_VARIANCE_COLUMNS)


def _get_loan(store: DuckDBStore, loan_id: str) -> dict[str, Any] | None:
    rows = store.fetchall_dicts(
        f"SELECT * FROM {CURRENT_DIM_LOAN_VIEW} WHERE loan_id = ?", [loan_id]
    )
    return rows[0] if rows else None


def _get_latest_run_id(store: DuckDBStore, loan_id: str) -> str | None:
    rows = store.fetchall_dicts(
        f"SELECT run_id FROM {FACT_LOAN_REPAYMENT_TABLE}"
        " WHERE loan_id = ? AND run_id IS NOT NULL"
        " ORDER BY run_id DESC LIMIT 1",
        [loan_id],
    )
    return rows[0]["run_id"] if rows else None


def _is_stale(store: DuckDBStore, scenario_id: str, loan_id: str) -> bool:
    """True if the canonical run_id for this loan has changed since scenario was computed."""
    scenario_rows = store.fetchall_dicts(
        f"SELECT baseline_run_id FROM {DIM_SCENARIO_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )
    if not scenario_rows:
        return False
    baseline_run_id = scenario_rows[0]["baseline_run_id"]
    current_run_id = _get_latest_run_id(store, loan_id)
    if baseline_run_id is None or current_run_id is None:
        return False
    return baseline_run_id != current_run_id


def create_loan_what_if_scenario(
    store: DuckDBStore,
    *,
    loan_id: str,
    label: str | None = None,
    extra_repayment: Decimal | None = None,
    annual_rate: Decimal | None = None,
    term_months: int | None = None,
) -> ScenarioResult:
    """Create a loan what-if scenario with one or more overrides.

    Writes dim_scenario, fact_scenario_assumption, and proj_loan_schedule rows.
    Returns a ScenarioResult with headline deltas.
    """
    ensure_scenario_storage(store)

    loan = _get_loan(store, loan_id)
    if loan is None:
        raise ValueError(f"Loan not found: {loan_id!r}")

    baseline_run_id = _get_latest_run_id(store, loan_id)

    # Resolve baseline params
    base_annual_rate = Decimal(str(loan["annual_rate"]))
    base_term_months = int(loan["term_months"])
    base_principal = Decimal(str(loan["principal"]))
    start_date = loan["start_date"]
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    currency = loan.get("currency", "")
    loan_name = loan.get("loan_name", loan_id)

    # Apply overrides
    effective_rate = annual_rate if annual_rate is not None else base_annual_rate
    effective_term = term_months if term_months is not None else base_term_months
    effective_extra = extra_repayment if extra_repayment is not None else Decimal("0")

    scenario_params = LoanParameters(
        principal=base_principal,
        annual_rate=effective_rate,
        term_months=effective_term,
        start_date=start_date,
        extra_repayment=effective_extra,
    )
    baseline_params = LoanParameters(
        principal=base_principal,
        annual_rate=base_annual_rate,
        term_months=base_term_months,
        start_date=start_date,
    )

    scenario_schedule = compute_amortization_schedule(scenario_params)
    baseline_schedule = compute_amortization_schedule(baseline_params)

    scenario_id = str(uuid.uuid4())
    auto_label = label or f"What-if: {loan_name}"

    # Write dim_scenario
    store.insert_rows(DIM_SCENARIO_TABLE, [{
        "scenario_id": scenario_id,
        "scenario_type": "loan_what_if",
        "subject_id": loan_id,
        "label": auto_label,
        "status": "active",
        "baseline_run_id": baseline_run_id,
        "created_at": datetime.now(UTC).isoformat(),
    }])

    # Write assumptions
    assumption_rows: list[dict[str, Any]] = []
    if extra_repayment is not None:
        assumption_rows.append({
            "scenario_id": scenario_id,
            "assumption_key": "extra_repayment",
            "baseline_value": "0",
            "override_value": str(extra_repayment),
            "unit": currency,
        })
    if annual_rate is not None:
        assumption_rows.append({
            "scenario_id": scenario_id,
            "assumption_key": "annual_rate",
            "baseline_value": str(base_annual_rate),
            "override_value": str(annual_rate),
            "unit": "%",
        })
    if term_months is not None:
        assumption_rows.append({
            "scenario_id": scenario_id,
            "assumption_key": "term_months",
            "baseline_value": str(base_term_months),
            "override_value": str(term_months),
            "unit": "months",
        })
    if assumption_rows:
        store.insert_rows(FACT_SCENARIO_ASSUMPTION_TABLE, assumption_rows)

    # Write proj_loan_schedule
    proj_rows = [
        {
            "scenario_id": scenario_id,
            "loan_id": loan_id,
            "loan_name": loan_name,
            "period": row.period,
            "payment_date": row.payment_date,
            "payment": str(row.payment),
            "principal_portion": str(row.principal_portion),
            "interest_portion": str(row.interest_portion),
            "extra_repayment": str(row.extra_repayment),
            "remaining_balance": str(row.remaining_balance),
            "currency": currency,
        }
        for row in scenario_schedule
    ]
    if proj_rows:
        store.insert_rows(PROJ_LOAN_SCHEDULE_TABLE, proj_rows)

    # Compute headline deltas
    baseline_total_interest = sum(
        (r.interest_portion for r in baseline_schedule), Decimal("0")
    )
    scenario_total_interest = sum(
        (r.interest_portion for r in scenario_schedule), Decimal("0")
    )
    interest_saved = baseline_total_interest - scenario_total_interest

    months_saved = len(baseline_schedule) - len(scenario_schedule)

    baseline_payoff = baseline_schedule[-1].payment_date if baseline_schedule else None
    scenario_payoff = scenario_schedule[-1].payment_date if scenario_schedule else None

    # Write variance rows
    _write_variance_rows(
        store, scenario_id, loan_id, currency, baseline_schedule, scenario_schedule
    )

    return ScenarioResult(
        scenario_id=scenario_id,
        label=auto_label,
        months_saved=months_saved,
        interest_saved=interest_saved,
        new_payoff_date=scenario_payoff,
        baseline_payoff_date=baseline_payoff,
        is_stale=False,
    )


def _write_variance_rows(
    store: DuckDBStore,
    scenario_id: str,
    loan_id: str,
    currency: str,
    baseline_schedule: list,
    scenario_schedule: list,
) -> None:
    baseline_by_period = {r.period: r for r in baseline_schedule}
    scenario_by_period = {r.period: r for r in scenario_schedule}

    all_periods = sorted(
        set(baseline_by_period) | set(scenario_by_period)
    )
    variance_rows = []
    for period in all_periods:
        b = baseline_by_period.get(period)
        s = scenario_by_period.get(period)
        if s is None:
            continue
        variance_rows.append({
            "scenario_id": scenario_id,
            "loan_id": loan_id,
            "period": period,
            "payment_date": s.payment_date,
            "baseline_payment": str(b.payment) if b else None,
            "scenario_payment": str(s.payment),
            "baseline_balance": str(b.remaining_balance) if b else None,
            "scenario_balance": str(s.remaining_balance),
            "payment_delta": str(s.payment - b.payment) if b else None,
            "balance_delta": str(s.remaining_balance - b.remaining_balance) if b else None,
            "currency": currency,
        })
    if variance_rows:
        store.insert_rows(PROJ_LOAN_REPAYMENT_VARIANCE_TABLE, variance_rows)


def get_scenario(store: DuckDBStore, scenario_id: str) -> dict[str, Any] | None:
    ensure_scenario_storage(store)
    rows = store.fetchall_dicts(
        f"SELECT * FROM {DIM_SCENARIO_TABLE} WHERE scenario_id = ?", [scenario_id]
    )
    return rows[0] if rows else None


def get_scenario_comparison(store: DuckDBStore, scenario_id: str) -> ComparisonResult | None:
    ensure_scenario_storage(store)

    scenario = get_scenario(store, scenario_id)
    if scenario is None:
        return None

    loan_id = scenario["subject_id"]

    assumptions = store.fetchall_dicts(
        f"SELECT * FROM {FACT_SCENARIO_ASSUMPTION_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )

    scenario_rows = store.fetchall_dicts(
        f"SELECT * FROM {PROJ_LOAN_SCHEDULE_TABLE} WHERE scenario_id = ?"
        " ORDER BY period",
        [scenario_id],
    )

    baseline_rows = store.fetchall_dicts(
        f"SELECT * FROM {MART_LOAN_SCHEDULE_PROJECTED_TABLE} WHERE loan_id = ?"
        " ORDER BY period",
        [loan_id],
    )

    variance_rows = store.fetchall_dicts(
        f"SELECT * FROM {PROJ_LOAN_REPAYMENT_VARIANCE_TABLE} WHERE scenario_id = ?"
        " ORDER BY period",
        [scenario_id],
    )

    stale = _is_stale(store, scenario_id, loan_id)

    return ComparisonResult(
        scenario_id=scenario_id,
        label=scenario["label"],
        assumptions=assumptions,
        baseline_rows=baseline_rows,
        scenario_rows=scenario_rows,
        variance_rows=variance_rows,
        is_stale=stale,
    )


def get_scenario_assumptions(store: DuckDBStore, scenario_id: str) -> list[dict[str, Any]]:
    ensure_scenario_storage(store)
    return store.fetchall_dicts(
        f"SELECT * FROM {FACT_SCENARIO_ASSUMPTION_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )


def archive_scenario(store: DuckDBStore, scenario_id: str) -> bool:
    """Soft-delete: set status=archived. Does NOT delete projection rows."""
    ensure_scenario_storage(store)
    existing = get_scenario(store, scenario_id)
    if existing is None:
        return False
    store.execute(
        f"UPDATE {DIM_SCENARIO_TABLE} SET status = 'archived' WHERE scenario_id = ?",
        [scenario_id],
    )
    return True
