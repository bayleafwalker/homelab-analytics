"""Cross-domain scenario builders and comparison getters for the overview layer.

Homelab cost/benefit and tariff-shock scenarios depend on sibling domain packs
(homelab, utilities), so they live here in the overview composition layer rather
than inside the finance product pack.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from packages.domains.finance.pipelines.scenario_models import (
    DIM_SCENARIO_COLUMNS,
    DIM_SCENARIO_TABLE,
    FACT_SCENARIO_ASSUMPTION_COLUMNS,
    FACT_SCENARIO_ASSUMPTION_TABLE,
    PROJ_HOMELAB_COST_BENEFIT_SUMMARY_COLUMNS,
    PROJ_HOMELAB_COST_BENEFIT_SUMMARY_TABLE,
    PROJ_INCOME_CASHFLOW_COLUMNS,
    PROJ_INCOME_CASHFLOW_TABLE,
)
from packages.domains.finance.pipelines.scenario_service import (
    IncomeCashflowComparison,
    _insert_dim_scenario,
    ensure_scenario_storage,
    get_baseline_cashflow,
    get_latest_transaction_run_id,
    get_scenario,
)
from packages.domains.homelab.pipelines.homelab_models import (
    MART_SERVICE_HEALTH_CURRENT_TABLE,
    MART_WORKLOAD_COST_7D_TABLE,
)
from packages.domains.utilities.pipelines.utility_models import (
    MART_UTILITY_COST_TREND_MONTHLY_TABLE,
)
from packages.domains.overview.pipelines.scenario_models_overview import (
    HomelabCostBenefitComparison,
    HomelabCostBenefitResult,
    TariffShockResult,
)
from packages.platform.source_freshness import SourceFreshnessSummary
from packages.storage.duckdb_store import DuckDBStore

_DEFAULT_PROJECTION_MONTHS = 12


def _ensure_homelab_scenario_storage(store: DuckDBStore) -> None:
    """Extend scenario storage with the homelab-specific projection table."""
    ensure_scenario_storage(store)
    store.ensure_table(PROJ_HOMELAB_COST_BENEFIT_SUMMARY_TABLE, PROJ_HOMELAB_COST_BENEFIT_SUMMARY_COLUMNS)


def _add_months(d: date, n: int) -> date:
    """Return date shifted forward by n calendar months."""
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    return d.replace(year=year, month=month, day=1)


# ---------------------------------------------------------------------------
# Homelab cost/benefit scenario
# ---------------------------------------------------------------------------


def _get_homelab_current_rows(
    store: DuckDBStore,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    service_rows = store.fetchall_dicts(
        f"SELECT * FROM {MART_SERVICE_HEALTH_CURRENT_TABLE} ORDER BY service_id"
    )
    workload_rows = store.fetchall_dicts(
        f"SELECT * FROM {MART_WORKLOAD_COST_7D_TABLE} ORDER BY est_monthly_cost DESC NULLS LAST"
    )
    return service_rows, workload_rows


def build_homelab_cost_benefit_baseline_signature(
    *,
    service_rows: list[dict[str, Any]],
    workload_rows: list[dict[str, Any]],
) -> str | None:
    if not service_rows and not workload_rows:
        return None

    normalized = {
        "services": sorted(
            [
                {
                    "service_id": str(row.get("service_id") or ""),
                    "state": str(row.get("state") or ""),
                    "last_state_change": str(row.get("last_state_change") or ""),
                    "recorded_at": str(row.get("recorded_at") or ""),
                }
                for row in service_rows
            ],
            key=lambda row: row["service_id"],
        ),
        "workloads": sorted(
            [
                {
                    "workload_id": str(row.get("workload_id") or ""),
                    "avg_cpu_pct_7d": str(row.get("avg_cpu_pct_7d") or ""),
                    "avg_mem_gb_7d": str(row.get("avg_mem_gb_7d") or ""),
                    "reading_count_7d": str(row.get("reading_count_7d") or ""),
                    "est_monthly_cost": str(row.get("est_monthly_cost") or "0"),
                }
                for row in workload_rows
            ],
            key=lambda row: row["workload_id"],
        ),
    }
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_homelab_current_summary(
    *,
    service_rows: list[dict[str, Any]],
    workload_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not service_rows and not workload_rows:
        raise ValueError(
            "No homelab service or workload rows are available. "
            "Refresh homelab marts before creating a cost/benefit scenario."
        )

    running_services = sum(1 for row in service_rows if row.get("state") == "running")
    needs_attention = len(service_rows) - running_services
    monthly_cost = sum(
        Decimal(str(row.get("est_monthly_cost") or 0)) for row in workload_rows
    )
    workload_count = len(workload_rows)
    top_workload_cost = (
        max((Decimal(str(row.get("est_monthly_cost") or 0)) for row in workload_rows), default=Decimal("0"))
        if workload_rows
        else Decimal("0")
    )

    healthy_service_ratio = (
        Decimal(running_services) / Decimal(len(service_rows))
        if service_rows
        else None
    )
    cost_per_healthy_service = (
        monthly_cost / Decimal(running_services) if running_services > 0 else None
    )
    cost_per_tracked_workload = (
        monthly_cost / Decimal(workload_count) if workload_count > 0 else None
    )
    largest_workload_share = (
        top_workload_cost / monthly_cost if monthly_cost > 0 else None
    )

    return {
        "running_services": running_services,
        "needs_attention": needs_attention,
        "monthly_cost": monthly_cost,
        "workload_count": workload_count,
        "top_workload_cost": top_workload_cost,
        "healthy_service_ratio": healthy_service_ratio,
        "cost_per_healthy_service": cost_per_healthy_service,
        "cost_per_tracked_workload": cost_per_tracked_workload,
        "largest_workload_share": largest_workload_share,
    }


def _get_latest_homelab_run_signature(store: DuckDBStore) -> str | None:
    service_rows, workload_rows = _get_homelab_current_rows(store)
    return build_homelab_cost_benefit_baseline_signature(
        service_rows=service_rows,
        workload_rows=workload_rows,
    )


def _is_homelab_cost_benefit_stale(
    store: DuckDBStore,
    scenario_id: str,
    *,
    current_baseline_run_id: str | None = None,
) -> bool:
    scenario_rows = store.fetchall_dicts(
        f"SELECT baseline_run_id FROM {DIM_SCENARIO_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )
    if not scenario_rows:
        return False
    baseline_run_id = scenario_rows[0]["baseline_run_id"]
    current_run_id = current_baseline_run_id
    if current_run_id is None:
        current_run_id = _get_latest_homelab_run_signature(store)
    if baseline_run_id is None or current_run_id is None:
        return False
    return str(baseline_run_id) != current_run_id


def _homelab_summary_rows(
    scenario_id: str,
    summary: dict[str, Any],
    *,
    monthly_cost_delta: Decimal,
    new_monthly_cost: Decimal,
) -> list[dict[str, Any]]:
    q = Decimal("0.01")
    ratio_q = Decimal("0.0001")
    running_services = summary["running_services"]
    workload_count = summary["workload_count"]
    top_workload_cost = summary["top_workload_cost"]
    healthy_service_ratio = summary["healthy_service_ratio"]
    cost_per_healthy_service = summary["cost_per_healthy_service"]
    cost_per_tracked_workload = summary["cost_per_tracked_workload"]
    largest_workload_share = summary["largest_workload_share"]
    healthy_services_per_cost_unit = (
        Decimal(running_services) / summary["monthly_cost"]
        if summary["monthly_cost"] > 0
        else None
    )

    scenario_cost_per_healthy_service = (
        new_monthly_cost / Decimal(running_services) if running_services > 0 else None
    )
    scenario_cost_per_tracked_workload = (
        new_monthly_cost / Decimal(workload_count) if workload_count > 0 else None
    )
    scenario_largest_workload_share = (
        top_workload_cost / new_monthly_cost if new_monthly_cost > 0 else None
    )
    scenario_healthy_services_per_cost_unit = (
        Decimal(running_services) / new_monthly_cost if new_monthly_cost > 0 else None
    )

    def _q(value: Decimal | None, quantizer: Decimal) -> str | None:
        if value is None:
            return None
        return str(value.quantize(quantizer))

    return [
        {
            "scenario_id": scenario_id,
            "metric": "Monthly workload cost",
            "metric_key": "monthly_workload_cost",
            "baseline_value": str(summary["monthly_cost"].quantize(q)),
            "scenario_value": str(new_monthly_cost.quantize(q)),
            "delta_value": str(monthly_cost_delta.quantize(q)),
            "unit": "currency",
        },
        {
            "scenario_id": scenario_id,
            "metric": "Healthy service count",
            "metric_key": "healthy_service_count",
            "baseline_value": str(running_services),
            "scenario_value": str(running_services),
            "delta_value": "0",
            "unit": "count",
        },
        {
            "scenario_id": scenario_id,
            "metric": "Needs attention count",
            "metric_key": "needs_attention_count",
            "baseline_value": str(summary["needs_attention"]),
            "scenario_value": str(summary["needs_attention"]),
            "delta_value": "0",
            "unit": "count",
        },
        {
            "scenario_id": scenario_id,
            "metric": "Service health ratio",
            "metric_key": "service_health_ratio",
            "baseline_value": _q(healthy_service_ratio, ratio_q),
            "scenario_value": _q(healthy_service_ratio, ratio_q),
            "delta_value": "0",
            "unit": "ratio",
        },
        {
            "scenario_id": scenario_id,
            "metric": "Cost per healthy service",
            "metric_key": "cost_per_healthy_service",
            "baseline_value": _q(cost_per_healthy_service, q),
            "scenario_value": _q(scenario_cost_per_healthy_service, q),
            "delta_value": (
                _q(scenario_cost_per_healthy_service - cost_per_healthy_service, q)
                if scenario_cost_per_healthy_service is not None
                and cost_per_healthy_service is not None
                else None
            ),
            "unit": "currency",
        },
        {
            "scenario_id": scenario_id,
            "metric": "Healthy services per cost unit",
            "metric_key": "healthy_services_per_cost_unit",
            "baseline_value": _q(healthy_services_per_cost_unit, ratio_q),
            "scenario_value": _q(scenario_healthy_services_per_cost_unit, ratio_q),
            "delta_value": (
                _q(
                    scenario_healthy_services_per_cost_unit - healthy_services_per_cost_unit,
                    ratio_q,
                )
                if scenario_healthy_services_per_cost_unit is not None
                and healthy_services_per_cost_unit is not None
                else None
            ),
            "unit": "ratio",
        },
        {
            "scenario_id": scenario_id,
            "metric": "Cost per tracked workload",
            "metric_key": "cost_per_tracked_workload",
            "baseline_value": _q(cost_per_tracked_workload, q),
            "scenario_value": _q(scenario_cost_per_tracked_workload, q),
            "delta_value": (
                _q(scenario_cost_per_tracked_workload - cost_per_tracked_workload, q)
                if scenario_cost_per_tracked_workload is not None
                and cost_per_tracked_workload is not None
                else None
            ),
            "unit": "currency",
        },
        {
            "scenario_id": scenario_id,
            "metric": "Largest workload share",
            "metric_key": "largest_workload_share",
            "baseline_value": _q(largest_workload_share, ratio_q),
            "scenario_value": _q(scenario_largest_workload_share, ratio_q),
            "delta_value": (
                _q(scenario_largest_workload_share - largest_workload_share, ratio_q)
                if scenario_largest_workload_share is not None
                and largest_workload_share is not None
                else None
            ),
            "unit": "ratio",
        },
    ]


def create_homelab_cost_benefit_scenario(
    store: DuckDBStore,
    *,
    monthly_cost_delta: Decimal,
    label: str | None = None,
    service_rows: list[dict[str, Any]] | None = None,
    workload_rows: list[dict[str, Any]] | None = None,
    baseline_run_id: str | None = None,
) -> HomelabCostBenefitResult:
    """Create a homelab cost/benefit scenario from current homelab marts."""
    _ensure_homelab_scenario_storage(store)

    if service_rows is None or workload_rows is None:
        service_rows, workload_rows = _get_homelab_current_rows(store)
    summary = _build_homelab_current_summary(
        service_rows=service_rows,
        workload_rows=workload_rows,
    )
    resolved_baseline_run_id = baseline_run_id or build_homelab_cost_benefit_baseline_signature(
        service_rows=service_rows,
        workload_rows=workload_rows,
    )
    new_monthly_cost = summary["monthly_cost"] + monthly_cost_delta
    if new_monthly_cost < Decimal("0"):
        raise ValueError("monthly_cost_delta would make the projected homelab cost negative.")

    scenario_id = str(uuid.uuid4())
    sign = "+" if monthly_cost_delta >= 0 else ""
    auto_label = label or f"Homelab cost/benefit: {sign}{monthly_cost_delta.quantize(Decimal('0.01'))}"

    _insert_dim_scenario(
        store,
        scenario_id=scenario_id,
        scenario_type="homelab_cost_benefit",
        subject_id="homelab",
        label=auto_label,
        baseline_run_id=resolved_baseline_run_id,
    )

    q = Decimal("0.01")
    store.insert_rows(
        FACT_SCENARIO_ASSUMPTION_TABLE,
        [
            {
                "scenario_id": scenario_id,
                "assumption_key": "monthly_cost_delta",
                "baseline_value": "0",
                "override_value": str(monthly_cost_delta.quantize(q)),
                "unit": "currency",
            }
        ],
    )

    summary_rows = _homelab_summary_rows(
        scenario_id,
        summary,
        monthly_cost_delta=monthly_cost_delta,
        new_monthly_cost=new_monthly_cost,
    )
    store.insert_rows(PROJ_HOMELAB_COST_BENEFIT_SUMMARY_TABLE, summary_rows)

    return HomelabCostBenefitResult(
        scenario_id=scenario_id,
        label=auto_label,
        monthly_cost_delta=monthly_cost_delta,
        baseline_monthly_cost=summary["monthly_cost"],
        new_monthly_cost=new_monthly_cost,
        annual_cost_delta=(monthly_cost_delta * 12).quantize(q),
        is_stale=False,
    )


def get_homelab_cost_benefit_comparison(
    store: DuckDBStore,
    scenario_id: str,
    *,
    current_baseline_run_id: str | None = None,
    control_plane_store: Any | None = None,
) -> HomelabCostBenefitComparison | None:
    _ensure_homelab_scenario_storage(store)

    scenario = get_scenario(store, scenario_id)
    if scenario is None or scenario["scenario_type"] != "homelab_cost_benefit":
        return None

    assumptions = store.fetchall_dicts(
        f"SELECT * FROM {FACT_SCENARIO_ASSUMPTION_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )
    summary_rows = store.fetchall_dicts(
        f"SELECT * FROM {PROJ_HOMELAB_COST_BENEFIT_SUMMARY_TABLE} WHERE scenario_id = ?"
        " ORDER BY metric_key",
        [scenario_id],
    )

    assumptions_summary = None
    if control_plane_store is not None:
        try:
            snapshots = control_plane_store.list_publication_confidence_snapshots()
            assumptions_summary = [
                SourceFreshnessSummary(
                    source_asset_id=snap.publication_key,
                    freshness_state=snap.freshness_state,
                    last_ingest_at=snap.assessed_at,
                )
                for snap in snapshots
            ]
        except Exception:
            pass

    return HomelabCostBenefitComparison(
        scenario_id=scenario_id,
        label=scenario["label"],
        assumptions=assumptions,
        summary_rows=summary_rows,
        is_stale=_is_homelab_cost_benefit_stale(
            store,
            scenario_id,
            current_baseline_run_id=current_baseline_run_id,
        ),
        assumptions_summary=assumptions_summary,
    )


# ---------------------------------------------------------------------------
# Tariff shock scenario
# ---------------------------------------------------------------------------


def _get_latest_utility_snapshot_signature(
    store: DuckDBStore,
    *,
    utility_type: str,
) -> str | None:
    rows = store.fetchall_dicts(
        f"SELECT billing_month, total_cost, usage_amount, meter_count"
        f" FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}"
        " WHERE utility_type = ?"
        " ORDER BY billing_month DESC LIMIT 1",
        [utility_type],
    )
    if not rows:
        return None
    row = rows[0]
    return (
        f"{row.get('billing_month')}|{row.get('total_cost')}|"
        f"{row.get('usage_amount')}|{row.get('meter_count')}"
    )


def _get_latest_utility_monthly_cost(
    store: DuckDBStore,
    *,
    utility_type: str,
) -> Decimal:
    rows = store.fetchall_dicts(
        f"SELECT total_cost FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}"
        " WHERE utility_type = ?"
        " ORDER BY billing_month DESC LIMIT 1",
        [utility_type],
    )
    if not rows:
        raise ValueError(
            f"No utility trend data available for utility_type={utility_type!r}."
        )
    return Decimal(str(rows[0]["total_cost"]))


def _is_tariff_scenario_stale(
    store: DuckDBStore,
    scenario_id: str,
    utility_type: str,
) -> bool:
    scenario_rows = store.fetchall_dicts(
        f"SELECT baseline_run_id FROM {DIM_SCENARIO_TABLE} WHERE scenario_id = ?",
        [scenario_id],
    )
    if not scenario_rows:
        return False
    baseline_run_id = scenario_rows[0]["baseline_run_id"]
    current_signature = (
        f"transactions:{get_latest_transaction_run_id(store) or 'none'}|"
        f"utility:{_get_latest_utility_snapshot_signature(store, utility_type=utility_type) or 'none'}"
    )
    if baseline_run_id is None:
        return False
    return str(baseline_run_id) != current_signature


def create_tariff_shock_scenario(
    store: DuckDBStore,
    *,
    tariff_pct_delta: Decimal,
    utility_type: str = "electricity",
    label: str | None = None,
    projection_months: int = _DEFAULT_PROJECTION_MONTHS,
) -> TariffShockResult:
    """Create a utility tariff-shock scenario.

    Projects household cashflow over *projection_months* months assuming the selected
    utility cost moves by *tariff_pct_delta* as a fraction (e.g. Decimal("0.10") = 10%
    increase).  Income stays flat at the baseline average; the expense delta flows
    through the current household expense total.
    """
    ensure_scenario_storage(store)

    baseline_income, baseline_expense = get_baseline_cashflow(store)
    baseline_utility_cost = _get_latest_utility_monthly_cost(
        store,
        utility_type=utility_type,
    )
    new_monthly_utility_cost = baseline_utility_cost * (1 + tariff_pct_delta)
    utility_delta = new_monthly_utility_cost - baseline_utility_cost
    new_monthly_expense = baseline_expense + utility_delta
    baseline_run_id = (
        f"transactions:{get_latest_transaction_run_id(store) or 'none'}|"
        f"utility:{_get_latest_utility_snapshot_signature(store, utility_type=utility_type) or 'none'}"
    )

    scenario_id = str(uuid.uuid4())
    pct_display = tariff_pct_delta * 100
    sign = "+" if tariff_pct_delta >= 0 else ""
    auto_label = label or f"Tariff shock: {sign}{pct_display:.1f}% {utility_type}"

    _insert_dim_scenario(
        store,
        scenario_id=scenario_id,
        scenario_type="tariff_shock",
        subject_id=utility_type,
        label=auto_label,
        baseline_run_id=baseline_run_id,
    )

    q = Decimal("0.01")
    store.insert_rows(FACT_SCENARIO_ASSUMPTION_TABLE, [
        {
            "scenario_id": scenario_id,
            "assumption_key": "tariff_pct_delta",
            "baseline_value": "0",
            "override_value": str(tariff_pct_delta.quantize(q)),
            "unit": "%",
        },
        {
            "scenario_id": scenario_id,
            "assumption_key": "baseline_utility_cost",
            "baseline_value": str(baseline_utility_cost.quantize(q)),
            "override_value": str(new_monthly_utility_cost.quantize(q)),
            "unit": "currency",
        },
    ])

    today = date.today()
    proj_rows: list[dict[str, Any]] = []
    months_until_deficit: int | None = None
    for i in range(1, projection_months + 1):
        projected_month = _add_months(today, i).strftime("%Y-%m")
        baseline_net = baseline_income - baseline_expense
        scenario_net = baseline_income - new_monthly_expense
        net_delta = scenario_net - baseline_net

        if scenario_net < Decimal("0") and months_until_deficit is None:
            months_until_deficit = i

        proj_rows.append({
            "scenario_id": scenario_id,
            "period": i,
            "projected_month": projected_month,
            "baseline_income": str(baseline_income.quantize(q)),
            "scenario_income": str(baseline_income.quantize(q)),
            "baseline_expense": str(baseline_expense.quantize(q)),
            "scenario_expense": str(new_monthly_expense.quantize(q)),
            "baseline_net": str(baseline_net.quantize(q)),
            "scenario_net": str(scenario_net.quantize(q)),
            "net_delta": str(net_delta.quantize(q)),
        })

    store.insert_rows(PROJ_INCOME_CASHFLOW_TABLE, proj_rows)

    return TariffShockResult(
        scenario_id=scenario_id,
        label=auto_label,
        tariff_pct_delta=tariff_pct_delta,
        baseline_monthly_utility_cost=baseline_utility_cost,
        new_monthly_utility_cost=new_monthly_utility_cost,
        annual_additional_cost=(utility_delta * 12).quantize(q),
        months_until_deficit=months_until_deficit,
        is_stale=False,
    )


def get_tariff_shock_comparison(
    store: DuckDBStore,
    scenario_id: str,
    *,
    control_plane_store: Any | None = None,
) -> IncomeCashflowComparison | None:
    """Return projected cashflow rows + assumptions for a tariff_shock scenario."""
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

    assumptions_summary = None
    if control_plane_store is not None:
        try:
            snapshots = control_plane_store.list_publication_confidence_snapshots()
            assumptions_summary = [
                SourceFreshnessSummary(
                    source_asset_id=snap.publication_key,
                    freshness_state=snap.freshness_state,
                    last_ingest_at=snap.assessed_at,
                )
                for snap in snapshots
            ]
        except Exception:
            pass

    return IncomeCashflowComparison(
        scenario_id=scenario_id,
        label=scenario["label"],
        assumptions=assumptions,
        cashflow_rows=cashflow_rows,
        is_stale=_is_tariff_scenario_stale(store, scenario_id, scenario["subject_id"]),
        assumptions_summary=assumptions_summary,
    )
