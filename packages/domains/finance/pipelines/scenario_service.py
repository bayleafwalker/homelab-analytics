"""Scenario service — create and retrieve scenario comparisons.

Covers loan what-if, income-change, and expense-shock scenarios.
Cross-domain scenario builders (homelab cost/benefit, tariff shock) live in
packages/domains/overview/pipelines/scenario_service_overview.py.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from packages.domains.finance.pipelines.amortization import (
    LoanParameters,
    compute_amortization_schedule,
)
from packages.domains.finance.pipelines.loan_models import (
    CURRENT_DIM_LOAN_VIEW,
    FACT_LOAN_REPAYMENT_TABLE,
    MART_LOAN_SCHEDULE_PROJECTED_TABLE,
)
from packages.domains.finance.pipelines.scenario_models import (
    DIM_SCENARIO_COLUMNS,
    DIM_SCENARIO_COMPARE_SET_COLUMNS,
    DIM_SCENARIO_COMPARE_SET_TABLE,
    DIM_SCENARIO_TABLE,
    FACT_SCENARIO_ASSUMPTION_COLUMNS,
    FACT_SCENARIO_ASSUMPTION_TABLE,
    PROJ_INCOME_CASHFLOW_COLUMNS,
    PROJ_INCOME_CASHFLOW_TABLE,
    PROJ_LOAN_REPAYMENT_VARIANCE_COLUMNS,
    PROJ_LOAN_REPAYMENT_VARIANCE_TABLE,
    PROJ_LOAN_SCHEDULE_COLUMNS,
    PROJ_LOAN_SCHEDULE_TABLE,
)
from packages.domains.finance.pipelines.transaction_models import (
    FACT_TRANSACTION_TABLE,
    MART_MONTHLY_CASHFLOW_COLUMNS,
    MART_MONTHLY_CASHFLOW_TABLE,
)
from packages.platform.source_freshness import SourceFreshnessSummary
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
    assumptions_summary: list[SourceFreshnessSummary] | None = None


@dataclass
class IncomeScenarioResult:
    scenario_id: str
    label: str
    monthly_income_delta: Decimal
    new_monthly_income: Decimal
    baseline_monthly_income: Decimal
    annual_net_change: Decimal
    months_until_deficit: int | None
    is_stale: bool
    assumptions_summary: list[SourceFreshnessSummary] | None = None


@dataclass
class ExpenseShockResult:
    scenario_id: str
    label: str
    expense_pct_delta: Decimal
    new_monthly_expense: Decimal
    baseline_monthly_expense: Decimal
    annual_additional_cost: Decimal
    months_until_deficit: int | None
    is_stale: bool
    assumptions_summary: list[SourceFreshnessSummary] | None = None


@dataclass
class IncomeCashflowComparison:
    scenario_id: str
    label: str
    assumptions: list[dict[str, Any]]
    cashflow_rows: list[dict[str, Any]]
    is_stale: bool
    assumptions_summary: list[SourceFreshnessSummary] | None = None


@dataclass
class ComparisonResult:
    scenario_id: str
    label: str
    assumptions: list[dict[str, Any]]
    baseline_rows: list[dict[str, Any]]
    scenario_rows: list[dict[str, Any]]
    variance_rows: list[dict[str, Any]]
    is_stale: bool
    assumptions_summary: list[SourceFreshnessSummary] | None = None


@dataclass
class ScenarioCompareSetResult:
    compare_set_id: str
    label: str
    left_scenario_id: str
    right_scenario_id: str
    left_scenario_label: str
    right_scenario_label: str
    status: str
    created_at: str
    updated_at: str


def ensure_scenario_storage(store: DuckDBStore) -> None:
    store.ensure_table(DIM_SCENARIO_TABLE, DIM_SCENARIO_COLUMNS)
    store.ensure_table(DIM_SCENARIO_COMPARE_SET_TABLE, DIM_SCENARIO_COMPARE_SET_COLUMNS)
    store.ensure_table(FACT_SCENARIO_ASSUMPTION_TABLE, FACT_SCENARIO_ASSUMPTION_COLUMNS)
    store.ensure_table(PROJ_LOAN_SCHEDULE_TABLE, PROJ_LOAN_SCHEDULE_COLUMNS)
    store.ensure_table(PROJ_LOAN_REPAYMENT_VARIANCE_TABLE, PROJ_LOAN_REPAYMENT_VARIANCE_COLUMNS)
    store.ensure_table(PROJ_INCOME_CASHFLOW_TABLE, PROJ_INCOME_CASHFLOW_COLUMNS)


def _build_assumptions_summary(
    control_plane_store: Any | None,
) -> list[SourceFreshnessSummary] | None:
    """Build a per-source freshness summary from the control-plane store, or return None."""
    if control_plane_store is None:
        return None
    try:
        snapshots = control_plane_store.list_publication_confidence_snapshots()
        return [
            SourceFreshnessSummary(
                source_asset_id=snap.publication_key,
                freshness_state=snap.freshness_state,
                last_ingest_at=snap.assessed_at,
            )
            for snap in snapshots
        ]
    except Exception:
        return None


def _get_scenario_baseline_run_id(
    store: DuckDBStore,
    scenario_id: str,
) -> str | None:
    """Return the stored baseline_run_id for scenario_id, or None if not found."""
    rows = store.fetchall_dicts(
        f"SELECT baseline_run_id FROM {DIM_SCENARIO_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )
    if not rows:
        return None
    return str(rows[0]["baseline_run_id"]) if rows[0]["baseline_run_id"] is not None else None


def _insert_dim_scenario(
    store: DuckDBStore,
    *,
    scenario_id: str,
    scenario_type: str,
    subject_id: str,
    label: str,
    baseline_run_id: str | None,
) -> None:
    store.insert_rows(DIM_SCENARIO_TABLE, [{
        "scenario_id": scenario_id,
        "scenario_type": scenario_type,
        "subject_id": subject_id,
        "label": label,
        "status": "active",
        "baseline_run_id": baseline_run_id,
        "created_at": datetime.now(UTC).isoformat(),
    }])


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
    baseline_run_id = _get_scenario_baseline_run_id(store, scenario_id)
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
    _insert_dim_scenario(
        store,
        scenario_id=scenario_id,
        scenario_type="loan_what_if",
        subject_id=loan_id,
        label=auto_label,
        baseline_run_id=baseline_run_id,
    )

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


def list_scenarios(
    store: DuckDBStore,
    *,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    ensure_scenario_storage(store)
    if include_archived:
        return store.fetchall_dicts(
            f"SELECT * FROM {DIM_SCENARIO_TABLE} ORDER BY created_at DESC"
        )
    return store.fetchall_dicts(
        f"SELECT * FROM {DIM_SCENARIO_TABLE} WHERE status = 'active'"
        " ORDER BY created_at DESC"
    )


def get_scenario(store: DuckDBStore, scenario_id: str) -> dict[str, Any] | None:
    ensure_scenario_storage(store)
    rows = store.fetchall_dicts(
        f"SELECT * FROM {DIM_SCENARIO_TABLE} WHERE scenario_id = ?", [scenario_id]
    )
    return rows[0] if rows else None


def get_scenario_comparison(
    store: DuckDBStore,
    scenario_id: str,
    *,
    control_plane_store: Any | None = None,
) -> ComparisonResult | None:
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

    assumptions_summary = _build_assumptions_summary(control_plane_store)

    return ComparisonResult(
        scenario_id=scenario_id,
        label=scenario["label"],
        assumptions=assumptions,
        baseline_rows=baseline_rows,
        scenario_rows=scenario_rows,
        variance_rows=variance_rows,
        is_stale=stale,
        assumptions_summary=assumptions_summary,
    )


def get_scenario_assumptions(store: DuckDBStore, scenario_id: str) -> list[dict[str, Any]]:
    ensure_scenario_storage(store)
    return store.fetchall_dicts(
        f"SELECT * FROM {FACT_SCENARIO_ASSUMPTION_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )


def _get_active_compare_set_by_pair(
    store: DuckDBStore,
    *,
    left_scenario_id: str,
    right_scenario_id: str,
) -> dict[str, Any] | None:
    rows = store.fetchall_dicts(
        f"SELECT * FROM {DIM_SCENARIO_COMPARE_SET_TABLE}"
        " WHERE left_scenario_id = ? AND right_scenario_id = ? AND status = 'active'"
        " ORDER BY updated_at DESC LIMIT 1",
        [left_scenario_id, right_scenario_id],
    )
    return rows[0] if rows else None


def _get_compare_set_by_id(
    store: DuckDBStore,
    compare_set_id: str,
) -> dict[str, Any] | None:
    rows = store.fetchall_dicts(
        f"SELECT * FROM {DIM_SCENARIO_COMPARE_SET_TABLE}"
        " WHERE compare_set_id = ?",
        [compare_set_id],
    )
    return rows[0] if rows else None


def _scenario_compare_set_result(row: dict[str, Any]) -> ScenarioCompareSetResult:
    return ScenarioCompareSetResult(
        compare_set_id=str(row["compare_set_id"]),
        label=row["label"],
        left_scenario_id=row["left_scenario_id"],
        right_scenario_id=row["right_scenario_id"],
        left_scenario_label=row["left_scenario_label"],
        right_scenario_label=row["right_scenario_label"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_scenario_compare_sets(
    store: DuckDBStore,
    *,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    ensure_scenario_storage(store)
    if include_archived:
        return store.fetchall_dicts(
            f"SELECT * FROM {DIM_SCENARIO_COMPARE_SET_TABLE} ORDER BY created_at DESC"
        )
    return store.fetchall_dicts(
        f"SELECT * FROM {DIM_SCENARIO_COMPARE_SET_TABLE}"
        " WHERE status = 'active' ORDER BY created_at DESC"
    )


def create_scenario_compare_set(
    store: DuckDBStore,
    *,
    left_scenario_id: str,
    right_scenario_id: str,
    label: str | None = None,
) -> ScenarioCompareSetResult:
    ensure_scenario_storage(store)

    if left_scenario_id == right_scenario_id:
        raise ValueError("Compare sets require two different scenarios.")

    left_scenario = get_scenario(store, left_scenario_id)
    right_scenario = get_scenario(store, right_scenario_id)
    if left_scenario is None:
        raise ValueError(f"Scenario not found: {left_scenario_id!r}")
    if right_scenario is None:
        raise ValueError(f"Scenario not found: {right_scenario_id!r}")

    created_at = datetime.now(UTC).isoformat()
    auto_label = label or (
        f"Compare: {left_scenario['label']} vs {right_scenario['label']}"
    )
    left_label = left_scenario["label"]
    right_label = right_scenario["label"]
    existing = _get_active_compare_set_by_pair(
        store,
        left_scenario_id=left_scenario_id,
        right_scenario_id=right_scenario_id,
    )

    if existing is not None:
        compare_set_id = str(existing["compare_set_id"])
        store.execute(
            f"UPDATE {DIM_SCENARIO_COMPARE_SET_TABLE}"
            " SET label = ?, left_scenario_label = ?, right_scenario_label = ?, updated_at = ?"
            " WHERE compare_set_id = ?",
            [auto_label, left_label, right_label, created_at, compare_set_id],
        )
        rows = store.fetchall_dicts(
            f"SELECT * FROM {DIM_SCENARIO_COMPARE_SET_TABLE} WHERE compare_set_id = ?",
            [compare_set_id],
        )
        row = rows[0]
    else:
        compare_set_id = str(uuid.uuid4())
        store.insert_rows(
            DIM_SCENARIO_COMPARE_SET_TABLE,
            [
                {
                    "compare_set_id": compare_set_id,
                    "label": auto_label,
                    "left_scenario_id": left_scenario_id,
                    "right_scenario_id": right_scenario_id,
                    "left_scenario_label": left_label,
                    "right_scenario_label": right_label,
                    "status": "active",
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            ],
        )
        row = {
            "compare_set_id": compare_set_id,
            "label": auto_label,
            "left_scenario_id": left_scenario_id,
            "right_scenario_id": right_scenario_id,
            "left_scenario_label": left_label,
            "right_scenario_label": right_label,
            "status": "active",
            "created_at": created_at,
            "updated_at": created_at,
        }

    return ScenarioCompareSetResult(
        compare_set_id=str(row["compare_set_id"]),
        label=row["label"],
        left_scenario_id=row["left_scenario_id"],
        right_scenario_id=row["right_scenario_id"],
        left_scenario_label=row["left_scenario_label"],
        right_scenario_label=row["right_scenario_label"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def update_scenario_compare_set_label(
    store: DuckDBStore,
    compare_set_id: str,
    *,
    label: str,
) -> ScenarioCompareSetResult | None:
    ensure_scenario_storage(store)
    new_label = label.strip()
    if not new_label:
        raise ValueError("Compare set label cannot be empty.")

    existing = _get_compare_set_by_id(store, compare_set_id)
    if existing is None:
        return None

    updated_at = datetime.now(UTC).isoformat()
    store.execute(
        f"UPDATE {DIM_SCENARIO_COMPARE_SET_TABLE}"
        " SET label = ?, updated_at = ? WHERE compare_set_id = ?",
        [new_label, updated_at, compare_set_id],
    )
    row = _get_compare_set_by_id(store, compare_set_id)
    if row is None:
        return None
    return _scenario_compare_set_result(row)


def archive_scenario_compare_set(store: DuckDBStore, compare_set_id: str) -> bool:
    ensure_scenario_storage(store)
    existing = _get_compare_set_by_id(store, compare_set_id)
    if existing is None or existing["status"] != "active":
        return False
    store.execute(
        f"UPDATE {DIM_SCENARIO_COMPARE_SET_TABLE}"
        " SET status = 'archived', updated_at = ? WHERE compare_set_id = ?",
        [datetime.now(UTC).isoformat(), compare_set_id],
    )
    return True


def restore_scenario_compare_set(
    store: DuckDBStore,
    compare_set_id: str,
) -> ScenarioCompareSetResult | None:
    ensure_scenario_storage(store)
    existing = _get_compare_set_by_id(store, compare_set_id)
    if existing is None:
        return None
    if existing["status"] == "archived":
        active_pair = _get_active_compare_set_by_pair(
            store,
            left_scenario_id=str(existing["left_scenario_id"]),
            right_scenario_id=str(existing["right_scenario_id"]),
        )
        if active_pair is not None and str(active_pair["compare_set_id"]) != compare_set_id:
            raise ValueError("An active compare set already exists for this scenario pair.")
        store.execute(
            f"UPDATE {DIM_SCENARIO_COMPARE_SET_TABLE}"
            " SET status = 'active', updated_at = ? WHERE compare_set_id = ?",
            [datetime.now(UTC).isoformat(), compare_set_id],
        )
    row = _get_compare_set_by_id(store, compare_set_id)
    return _scenario_compare_set_result(row) if row is not None else None


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


# ---------------------------------------------------------------------------
# Income change scenarios
# ---------------------------------------------------------------------------

_LOOKUP_MONTHS = 3
_DEFAULT_PROJECTION_MONTHS = 12


def get_latest_transaction_run_id(store: DuckDBStore) -> str | None:
    """Return the most recent run_id from fact_transaction, or None if no rows."""
    rows = store.fetchall_dicts(
        f"SELECT run_id FROM {FACT_TRANSACTION_TABLE}"
        " WHERE run_id IS NOT NULL ORDER BY run_id DESC LIMIT 1"
    )
    return str(rows[0]["run_id"]) if rows else None


def _is_income_scenario_stale(store: DuckDBStore, scenario_id: str) -> bool:
    """True if the latest transaction run_id has advanced since the scenario was computed."""
    baseline_run_id = _get_scenario_baseline_run_id(store, scenario_id)
    current_run_id = get_latest_transaction_run_id(store)
    if baseline_run_id is None or current_run_id is None:
        return False
    return baseline_run_id != current_run_id


def get_baseline_cashflow(store: DuckDBStore) -> tuple[Decimal, Decimal]:
    """Return (avg_income, avg_expense) from the last _LOOKUP_MONTHS months of cashflow."""
    store.ensure_table(MART_MONTHLY_CASHFLOW_TABLE, MART_MONTHLY_CASHFLOW_COLUMNS)
    rows = store.fetchall_dicts(
        f"SELECT income, expense FROM {MART_MONTHLY_CASHFLOW_TABLE}"
        " ORDER BY booking_month DESC"
        f" LIMIT {_LOOKUP_MONTHS}"
    )
    if not rows:
        raise ValueError("No cashflow data available. Load transactions before creating income scenarios.")
    count = Decimal(len(rows))
    avg_income = sum((Decimal(str(r["income"])) for r in rows), Decimal("0")) / count
    avg_expense = sum((Decimal(str(r["expense"])) for r in rows), Decimal("0")) / count
    return avg_income, avg_expense


def _add_months(d: date, n: int) -> date:
    """Return date shifted forward by n calendar months."""
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    return d.replace(year=year, month=month, day=1)


def _project_cashflow_rows(
    *,
    scenario_id: str,
    baseline_income: Decimal,
    baseline_expense: Decimal,
    scenario_income: Decimal,
    scenario_expense: Decimal,
    projection_months: int,
    q: Decimal = Decimal("0.01"),
) -> tuple[list[dict[str, Any]], int | None]:
    """Build projected cashflow rows and return (rows, months_until_deficit)."""
    today = date.today()
    proj_rows: list[dict[str, Any]] = []
    months_until_deficit: int | None = None

    for i in range(1, projection_months + 1):
        projected_month = _add_months(today, i).strftime("%Y-%m")
        baseline_net = baseline_income - baseline_expense
        scenario_net = scenario_income - scenario_expense
        net_delta = scenario_net - baseline_net

        if scenario_net < Decimal("0") and months_until_deficit is None:
            months_until_deficit = i

        proj_rows.append({
            "scenario_id": scenario_id,
            "period": i,
            "projected_month": projected_month,
            "baseline_income": str(baseline_income.quantize(q)),
            "scenario_income": str(scenario_income.quantize(q)),
            "baseline_expense": str(baseline_expense.quantize(q)),
            "scenario_expense": str(scenario_expense.quantize(q)),
            "baseline_net": str(baseline_net.quantize(q)),
            "scenario_net": str(scenario_net.quantize(q)),
            "net_delta": str(net_delta.quantize(q)),
        })

    return proj_rows, months_until_deficit


def create_income_change_scenario(
    store: DuckDBStore,
    *,
    monthly_income_delta: Decimal,
    label: str | None = None,
    projection_months: int = _DEFAULT_PROJECTION_MONTHS,
) -> IncomeScenarioResult:
    """Create an income-change what-if scenario.

    Projects household cashflow over *projection_months* months assuming income
    shifts by *monthly_income_delta* each month (negative = income loss).

    Writes dim_scenario, fact_scenario_assumption, and proj_income_cashflow rows.
    """
    ensure_scenario_storage(store)

    baseline_income, baseline_expense = get_baseline_cashflow(store)
    new_monthly_income = baseline_income + monthly_income_delta
    baseline_run_id = get_latest_transaction_run_id(store)

    scenario_id = str(uuid.uuid4())
    sign = "+" if monthly_income_delta >= 0 else ""
    auto_label = label or f"Income change: {sign}{monthly_income_delta}"

    _insert_dim_scenario(
        store,
        scenario_id=scenario_id,
        scenario_type="income_change",
        subject_id="household",
        label=auto_label,
        baseline_run_id=baseline_run_id,
    )

    q = Decimal("0.01")
    store.insert_rows(FACT_SCENARIO_ASSUMPTION_TABLE, [{
        "scenario_id": scenario_id,
        "assumption_key": "monthly_income_delta",
        "baseline_value": "0",
        "override_value": str(monthly_income_delta.quantize(q)),
        "unit": "currency",
    }])

    proj_rows, months_until_deficit = _project_cashflow_rows(
        scenario_id=scenario_id,
        baseline_income=baseline_income,
        baseline_expense=baseline_expense,
        scenario_income=new_monthly_income,
        scenario_expense=baseline_expense,
        projection_months=projection_months,
    )
    store.insert_rows(PROJ_INCOME_CASHFLOW_TABLE, proj_rows)

    return IncomeScenarioResult(
        scenario_id=scenario_id,
        label=auto_label,
        monthly_income_delta=monthly_income_delta,
        new_monthly_income=new_monthly_income,
        baseline_monthly_income=baseline_income,
        annual_net_change=(monthly_income_delta * 12).quantize(q),
        months_until_deficit=months_until_deficit,
        is_stale=False,
    )


def create_expense_shock_scenario(
    store: DuckDBStore,
    *,
    expense_pct_delta: Decimal,
    label: str | None = None,
    projection_months: int = _DEFAULT_PROJECTION_MONTHS,
) -> ExpenseShockResult:
    """Create an expense-shock what-if scenario.

    Projects household cashflow over *projection_months* months assuming expenses
    shift by *expense_pct_delta* as a fraction (e.g. Decimal("0.10") = 10% increase).
    Income is held flat at the baseline average.

    Reuses proj_income_cashflow storage (scenario_expense varies; scenario_income = baseline).
    """
    ensure_scenario_storage(store)

    baseline_income, baseline_expense = get_baseline_cashflow(store)
    new_monthly_expense = baseline_expense * (1 + expense_pct_delta)
    baseline_run_id = get_latest_transaction_run_id(store)

    scenario_id = str(uuid.uuid4())
    pct_display = expense_pct_delta * 100
    sign = "+" if expense_pct_delta >= 0 else ""
    auto_label = label or f"Expense shock: {sign}{pct_display:.1f}%"

    _insert_dim_scenario(
        store,
        scenario_id=scenario_id,
        scenario_type="expense_shock",
        subject_id="household",
        label=auto_label,
        baseline_run_id=baseline_run_id,
    )

    q = Decimal("0.0001")
    store.insert_rows(FACT_SCENARIO_ASSUMPTION_TABLE, [{
        "scenario_id": scenario_id,
        "assumption_key": "expense_pct_delta",
        "baseline_value": "0",
        "override_value": str(expense_pct_delta.quantize(q)),
        "unit": "%",
    }])

    proj_rows, months_until_deficit = _project_cashflow_rows(
        scenario_id=scenario_id,
        baseline_income=baseline_income,
        baseline_expense=baseline_expense,
        scenario_income=baseline_income,
        scenario_expense=new_monthly_expense,
        projection_months=projection_months,
    )
    store.insert_rows(PROJ_INCOME_CASHFLOW_TABLE, proj_rows)

    return ExpenseShockResult(
        scenario_id=scenario_id,
        label=auto_label,
        expense_pct_delta=expense_pct_delta,
        new_monthly_expense=new_monthly_expense,
        baseline_monthly_expense=baseline_expense,
        annual_additional_cost=((new_monthly_expense - baseline_expense) * 12).quantize(q2),
        months_until_deficit=months_until_deficit,
        is_stale=False,
    )


def get_expense_shock_comparison(
    store: DuckDBStore,
    scenario_id: str,
    *,
    control_plane_store: Any | None = None,
) -> IncomeCashflowComparison | None:
    """Return projected cashflow rows for an expense_shock scenario.

    Delegates to the same storage queries as get_income_scenario_comparison
    since both types use proj_income_cashflow.
    """
    return get_income_scenario_comparison(
        store, scenario_id, control_plane_store=control_plane_store
    )


def get_income_scenario_comparison(
    store: DuckDBStore,
    scenario_id: str,
    *,
    control_plane_store: Any | None = None,
) -> IncomeCashflowComparison | None:
    """Return projected cashflow rows + assumptions for an income_change scenario."""
    ensure_scenario_storage(store)

    scenario = get_scenario(store, scenario_id)
    if scenario is None:
        return None

    assumptions = store.fetchall_dicts(
        f"SELECT * FROM {FACT_SCENARIO_ASSUMPTION_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )
    cashflow_rows = store.fetchall_dicts(
        f"SELECT * FROM {PROJ_INCOME_CASHFLOW_TABLE} WHERE scenario_id = ?"
        " ORDER BY period",
        [scenario_id],
    )

    assumptions_summary = _build_assumptions_summary(control_plane_store)

    return IncomeCashflowComparison(
        scenario_id=scenario_id,
        label=scenario["label"],
        assumptions=assumptions,
        cashflow_rows=cashflow_rows,
        is_stale=_is_income_scenario_stale(store, scenario_id),
        assumptions_summary=assumptions_summary,
    )
