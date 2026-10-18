from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.finance.pipelines.cashflow_map import (
    build_cashflow_map,
    cashflow_map_window,
    match_internal_transfers,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    refresh_monthly_cashflow,
    refresh_monthly_cashflow_by_counterparty,
    refresh_spend_by_category_monthly,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04"]


def _monthly(month: str, income: str, expense: str, count: int = 4) -> dict[str, object]:
    net = Decimal(income) - Decimal(expense)
    return {
        "booking_month": month,
        "income": income,
        "expense": expense,
        "net": str(net),
        "transaction_count": count,
    }


def _cp(month: str, name: str, income: str = "0", expense: str = "0") -> dict[str, object]:
    return {
        "booking_month": month,
        "counterparty_name": name,
        "income": income,
        "expense": expense,
        "net": str(Decimal(income) - Decimal(expense)),
        "transaction_count": 1,
    }


def _cat(month: str, name: str, amount: str, category: str | None = None) -> dict[str, object]:
    return {
        "booking_month": month,
        "counterparty_name": name,
        "category": category,
        "total_expense": amount,
        "transaction_count": 1,
    }


def _fixture() -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    monthly = [_monthly(m, "3500.00", "1300.00") for m in MONTHS]
    counterparty = []
    category = []
    for month in MONTHS:
        counterparty += [
            _cp(month, "Employer", income="3000.00"),
            _cp(month, "Own savings account", income="500.00"),
            _cp(month, "Transfer to savings", expense="500.00"),
            _cp(month, "Grocer", expense="600.00"),
            _cp(month, "Power Co", expense="200.00"),
        ]
        category += [
            _cat(month, "Transfer to savings", "500.00"),
            _cat(month, "Grocer", "600.00"),
            _cat(month, "Power Co", "200.00"),
        ]
    return monthly, counterparty, category


def _node(payload: dict, node_id: str) -> dict:
    return next(node for node in payload["nodes"] if node["id"] == node_id)


def test_window_covers_trend_months() -> None:
    assert cashflow_map_window("2026-03") == ("2025-10", "2026-03")


def test_matched_transfers_are_paired_once_and_by_amount() -> None:
    rows = [
        _cp("2026-01", "Own savings", income="500.00"),
        _cp("2026-01", "To savings", expense="500.00"),
        _cp("2026-01", "Grocer", expense="500.00"),
        _cp("2026-01", "Employer", income="3000.00"),
    ]
    pairs = match_internal_transfers(rows)
    assert len(pairs) == 1
    assert pairs[0]["income_counterparty"] == "Own savings"
    assert pairs[0]["amount"] == Decimal("500.00")


def test_map_excludes_transfers_and_balances_flows() -> None:
    monthly, counterparty, category = _fixture()
    payload = build_cashflow_map(
        monthly_rows=monthly,
        counterparty_rows=counterparty,
        category_rows=category,
        currency="EUR",
        today=date(2026, 5, 3),
    )
    assert payload["month"] == "2026-04"
    assert payload["previous_month"] == "2026-03"
    assert payload["next_month"] is None
    totals = payload["totals"]
    assert totals["income"] == "3500.00"
    assert totals["mapped_income"] == "3000.00"
    assert totals["mapped_expense"] == "800.00"
    assert totals["kept"] == "2200.00"
    assert totals["transfers"] == "500.00"
    codes = {item["code"] for item in payload["disclosures"]}
    assert "transfers_excluded" in codes
    assert "uncategorised" in codes
    assert "stale_data" not in codes
    assert payload["grouping"] == "counterparty"

    # every node's inflow equals its outflow (except the leaves)
    inflow: dict[str, Decimal] = {}
    outflow: dict[str, Decimal] = {}
    for link in payload["links"]:
        outflow[link["source"]] = outflow.get(link["source"], Decimal("0")) + Decimal(link["amount"])
        inflow[link["target"]] = inflow.get(link["target"], Decimal("0")) + Decimal(link["amount"])
    assert inflow["pool"] == outflow["pool"] == Decimal("3000.00")
    assert inflow["bucket:regular"] == outflow["bucket:regular"] == Decimal("800.00")
    assert _node(payload, "bucket:kept")["amount"] == "2200.00"
    grocer = _node(payload, "out:grocer")
    assert grocer["column"] == 3
    assert [point["month"] for point in grocer["trend"]] == MONTHS
    assert "Transfer to savings" not in {node["label"] for node in payload["nodes"]}


def test_map_can_include_transfers() -> None:
    monthly, counterparty, category = _fixture()
    payload = build_cashflow_map(
        monthly_rows=monthly,
        counterparty_rows=counterparty,
        category_rows=category,
        include_transfers=True,
        today=date(2026, 5, 3),
    )
    assert payload["totals"]["mapped_income"] == "3500.00"
    assert payload["totals"]["mapped_expense"] == "1300.00"
    assert "transfers_excluded" not in {item["code"] for item in payload["disclosures"]}


def test_map_reports_overspend_as_drawn_from_savings_and_stale_data() -> None:
    monthly = [_monthly("2026-01", "1000.00", "1400.00")]
    counterparty = [
        _cp("2026-01", "Employer", income="1000.00"),
        _cp("2026-01", "Garage", expense="1400.00"),
    ]
    category = [_cat("2026-01", "Garage", "1400.00", category="Car")]
    payload = build_cashflow_map(
        monthly_rows=monthly,
        counterparty_rows=counterparty,
        category_rows=category,
        today=date(2026, 6, 1),
    )
    assert payload["grouping"] == "category"
    assert _node(payload, "in:savings")["amount"] == "400.00"
    assert _node(payload, "bucket:spending")["amount"] == "1400.00"
    assert _node(payload, "out:car")["label"] == "Car"
    codes = {item["code"] for item in payload["disclosures"]}
    assert {"stale_data", "short_history"} <= codes
    assert not any(node["id"] == "bucket:kept" for node in payload["nodes"])


def test_map_groups_long_tail_and_falls_back_for_unknown_month() -> None:
    monthly = [_monthly("2026-01", "5000.00", "450.00")]
    counterparty = [_cp("2026-01", "Employer", income="5000.00")]
    category = []
    for index in range(9):
        counterparty.append(_cp("2026-01", f"Shop {index}", expense="50.00"))
        category.append(_cat("2026-01", f"Shop {index}", "50.00"))
    payload = build_cashflow_map(
        monthly_rows=monthly,
        counterparty_rows=counterparty,
        category_rows=category,
        month="2030-01",
        today=date(2026, 2, 1),
    )
    assert payload["month"] == "2026-01"
    assert "month_not_available" in {item["code"] for item in payload["disclosures"]}
    leaves = [node for node in payload["nodes"] if node["column"] == 3]
    assert len(leaves) == 7
    other = next(node for node in leaves if node["id"].startswith("out:other-"))
    assert other["label"] == "Everything else (3)"
    assert len(other["members"]) == 3
    assert other["amount"] == "150.00"


def test_map_without_data_is_empty_with_disclosure() -> None:
    payload = build_cashflow_map(monthly_rows=[], counterparty_rows=[], category_rows=[])
    assert payload["nodes"] == []
    assert payload["disclosures"][0]["code"] == "no_data"


def test_cashflow_map_endpoint_reads_reporting_publications() -> None:
    with TemporaryDirectory() as temp_dir:
        transformation_service = TransformationService(DuckDBStore.memory())
        transformation_service.load_transactions(
            [
                {
                    "booked_at": "2026-01-02",
                    "account_id": "CHK-001",
                    "counterparty_name": "Employer",
                    "amount": "2450.00",
                    "currency": "EUR",
                    "description": "Salary",
                },
                {
                    "booked_at": "2026-01-03",
                    "account_id": "CHK-001",
                    "counterparty_name": "Electric Utility",
                    "amount": "-84.15",
                    "currency": "EUR",
                    "description": "Bill",
                },
            ],
            run_id="run-001",
        )
        refresh_monthly_cashflow(transformation_service.store)
        refresh_monthly_cashflow_by_counterparty(transformation_service.store)
        refresh_spend_by_category_monthly(transformation_service.store)
        client = TestClient(
            create_app(
                AccountTransactionService(
                    landing_root=Path(temp_dir) / "landing",
                    metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
                ),
                transformation_service=transformation_service,
            )
        )
        response = client.get("/reports/cashflow-map", params={"month": "2026-01"})
        assert response.status_code == 200
        body = response.json()
        assert body["month"] == "2026-01"
        assert body["totals"]["mapped_income"] == "2450.00"
        assert body["totals"]["mapped_expense"] == "84.15"
        labels = {node["label"] for node in body["nodes"]}
        assert {"Employer", "Money in", "Electric Utility", "Kept"} <= labels
        assert body["provenance"]["publications"][0] == "mart_monthly_cashflow"

        assert client.get("/reports/cashflow-map", params={"month": "jan"}).status_code == 400

        bare_client = TestClient(
            create_app(
                AccountTransactionService(
                    landing_root=Path(temp_dir) / "landing2",
                    metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs2.db"),
                )
            )
        )
        assert bare_client.get("/reports/cashflow-map").status_code == 404
