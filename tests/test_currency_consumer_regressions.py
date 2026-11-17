"""Owned currency-correctness regressions for the monetary consumers.

Covers the four consumer paths the independent review flagged:

1. Finance/scenario tariff shock must refuse mixed denominations and
   usage-only (no bill) evidence instead of blending or returning a silent
   zero, while keeping the same-currency and observed-zero controls.
2. Electricity contract decision must refuse a contract whose energy price and
   base fee are in different currencies, with an explicit reason code.
3. The electricity contract estimate units follow the assessment currency
   (USD stays USD/year), never a hard-coded EUR.
4. The utilities cost trend keeps an unbilled meter as its own
   usage-only/null-currency group instead of folding it into the sole billed
   denomination.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    refresh_monthly_cashflow,
)
from packages.domains.overview.pipelines.scenario_service_overview import (
    create_tariff_shock_scenario,
    get_tariff_shock_comparison,
)
from packages.domains.utilities.energy_contract_decision import (
    assess_energy_contract_review,
    energy_contract_baseline,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    get_utility_cost_trend_monthly,
    refresh_utility_cost_summary,
    refresh_utility_cost_trend_monthly,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


def _service() -> TransformationService:
    return TransformationService(DuckDBStore.memory())


def _load_finance(svc: TransformationService, currency: str = "EUR") -> None:
    svc.load_transactions(
        [
            {
                "booked_at": "2026-01-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": currency,
                "description": "salary",
            }
        ],
        run_id="run-finance",
    )
    refresh_monthly_cashflow(svc.store)


def _bill(meter_id: str, amount: str, currency: str, month: str = "2026-01") -> dict:
    return {
        "meter_id": meter_id,
        "meter_name": meter_id,
        "provider": "City Power",
        "utility_type": "electricity",
        "location": "home",
        "billing_period_start": f"{month}-01",
        "billing_period_end": f"{month}-31",
        "billed_amount": amount,
        "currency": currency,
        "billed_quantity": "100",
        "usage_unit": "kWh",
        "invoice_date": f"{month}-05",
    }


def _usage(meter_id: str, quantity: str = "100", month: str = "2026-01") -> dict:
    return {
        "meter_id": meter_id,
        "meter_name": meter_id,
        "utility_type": "electricity",
        "location": "home",
        "usage_start": f"{month}-01",
        "usage_end": f"{month}-31",
        "usage_quantity": quantity,
        "usage_unit": "kWh",
        "reading_source": "smart-meter",
    }


def _refresh_utilities(svc: TransformationService) -> None:
    refresh_utility_cost_summary(svc.store)
    refresh_utility_cost_trend_monthly(svc.store)


# ---------------------------------------------------------------------------
# 1. Tariff shock
# ---------------------------------------------------------------------------


def test_tariff_shock_refuses_usd_utility_against_eur_cashflow() -> None:
    svc = _service()
    _load_finance(svc, currency="EUR")
    svc.load_bills([_bill("m1", "100", "USD")], run_id="run-bill")
    svc.load_utility_usage([_usage("m1")], run_id="run-usage")
    _refresh_utilities(svc)

    with pytest.raises(ValueError) as excinfo:
        create_tariff_shock_scenario(svc.store, tariff_pct_delta=Decimal("0.10"))

    message = str(excinfo.value).lower()
    assert "eur" in message and "usd" in message


def test_tariff_shock_refuses_mixed_denominations_in_the_latest_month() -> None:
    svc = _service()
    _load_finance(svc, currency="EUR")
    svc.load_bills(
        [_bill("m1", "100", "EUR"), _bill("m2", "200", "USD")], run_id="run-bill"
    )
    _refresh_utilities(svc)

    with pytest.raises(ValueError) as excinfo:
        create_tariff_shock_scenario(svc.store, tariff_pct_delta=Decimal("0.10"))

    assert "single denomination" in str(excinfo.value)


def test_tariff_shock_refuses_usage_only_without_a_bill() -> None:
    svc = _service()
    _load_finance(svc, currency="EUR")
    svc.load_utility_usage([_usage("m1")], run_id="run-usage")
    _refresh_utilities(svc)

    with pytest.raises(ValueError) as excinfo:
        create_tariff_shock_scenario(svc.store, tariff_pct_delta=Decimal("0.10"))

    assert "usage without a bill" in str(excinfo.value)


def test_tariff_shock_same_currency_eur_control() -> None:
    svc = _service()
    _load_finance(svc, currency="EUR")
    svc.load_bills([_bill("m1", "100", "EUR")], run_id="run-bill")
    svc.load_utility_usage([_usage("m1")], run_id="run-usage")
    _refresh_utilities(svc)

    result = create_tariff_shock_scenario(svc.store, tariff_pct_delta=Decimal("0.10"))

    assert result.baseline_monthly_utility_cost == Decimal("100")
    assert result.new_monthly_utility_cost == Decimal("110")
    assert result.annual_additional_cost == Decimal("120")


def test_tariff_shock_observed_zero_eur_bill_remains_zero() -> None:
    svc = _service()
    _load_finance(svc, currency="EUR")
    svc.load_bills([_bill("m1", "0", "EUR")], run_id="run-bill")
    svc.load_utility_usage([_usage("m1")], run_id="run-usage")
    _refresh_utilities(svc)

    result = create_tariff_shock_scenario(svc.store, tariff_pct_delta=Decimal("0.10"))

    assert result.baseline_monthly_utility_cost == Decimal("0")
    assert result.new_monthly_utility_cost == Decimal("0")
    assert result.annual_additional_cost == Decimal("0")


def test_tariff_shock_result_and_assumption_carry_the_actual_currency() -> None:
    svc = _service()
    _load_finance(svc, currency="USD")
    svc.load_bills([_bill("m1", "100", "USD")], run_id="run-bill")
    svc.load_utility_usage([_usage("m1")], run_id="run-usage")
    _refresh_utilities(svc)

    result = create_tariff_shock_scenario(svc.store, tariff_pct_delta=Decimal("0.10"))
    assert result.currency == "USD"

    comparison = get_tariff_shock_comparison(svc.store, result.scenario_id)
    assert comparison is not None
    assumption = next(
        row
        for row in comparison.assumptions
        if row["assumption_key"] == "baseline_utility_cost"
    )
    assert assumption["unit"] == "USD"


def test_tariff_shock_public_cashflow_refuses_an_incompatible_persisted_scenario(
    tmp_path: Path,
) -> None:
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    svc = _service()
    _load_finance(svc, currency="EUR")
    svc.load_bills([_bill("m1", "100", "EUR")], run_id="run-bill")
    svc.load_utility_usage([_usage("m1")], run_id="run-usage")
    _refresh_utilities(svc)

    result = create_tariff_shock_scenario(svc.store, tariff_pct_delta=Decimal("0.10"))

    # Simulate a scenario persisted by an older build that recorded the generic
    # "currency" token (or a blended projection) instead of a concrete single
    # denomination. The public projection must refuse it, not serve it blended.
    svc.store.execute(
        "UPDATE fact_scenario_assumption SET unit = 'currency' "
        "WHERE scenario_id = ? AND assumption_key = 'baseline_utility_cost'",
        [result.scenario_id],
    )

    assert get_tariff_shock_comparison(svc.store, result.scenario_id) is None

    client = TestClient(create_app(service, transformation_service=svc))
    response = client.get(f"/api/scenarios/{result.scenario_id}/cashflow")
    assert response.status_code == 404


def _client(tmp_path: Path) -> tuple[TestClient, TransformationService]:
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    svc = _service()
    return TestClient(create_app(service, transformation_service=svc)), svc


def _scenario_ids(client: TestClient) -> set[str]:
    return {row["scenario_id"] for row in client.get("/api/scenarios").json()["rows"]}


def test_tariff_shock_public_catalogue_rejects_mixed_without_a_persisted_blend(
    tmp_path: Path,
) -> None:
    client, svc = _client(tmp_path)
    _load_finance(svc, currency="EUR")
    svc.load_bills([_bill("m1", "100", "USD")], run_id="run-bill")
    svc.load_utility_usage([_usage("m1")], run_id="run-usage")
    _refresh_utilities(svc)

    before = _scenario_ids(client)

    response = client.post(
        "/api/scenarios/tariff-shock",
        json={"tariff_pct_delta": "0.10"},
    )

    # Rejected cleanly: no ID, no nulled-but-served monetary fields, and no
    # new catalogue record (so no persisted-blend projection to expose).
    assert response.status_code == 422
    body = response.json()
    assert "scenario_id" not in body
    assert "months_until_deficit" not in body
    assert _scenario_ids(client) == before


@pytest.mark.parametrize("currency", ["EUR", "USD"])
def test_tariff_shock_valid_currency_publishes_truthful_views(
    tmp_path: Path, currency: str
) -> None:
    client, svc = _client(tmp_path)
    _load_finance(svc, currency=currency)
    svc.load_bills([_bill("m1", "100", currency)], run_id="run-bill")
    svc.load_utility_usage([_usage("m1")], run_id="run-usage")
    _refresh_utilities(svc)

    before = _scenario_ids(client)

    response = client.post(
        "/api/scenarios/tariff-shock",
        json={"tariff_pct_delta": "0.10"},
    )
    assert response.status_code == 200
    body = response.json()
    sid = body["scenario_id"]
    assert body["currency"] == currency
    assert float(body["baseline_monthly_utility_cost"]) == 100.0

    # The new record is visible and its projection/assumptions are truthful.
    after = _scenario_ids(client)
    assert after - before == {sid}

    cashflow = client.get(f"/api/scenarios/{sid}/cashflow")
    assert cashflow.status_code == 200
    cashflow_body = cashflow.json()
    assert len(cashflow_body["cashflow_rows"]) == 12
    assumption = next(
        row
        for row in cashflow_body["assumptions"]
        if row["assumption_key"] == "baseline_utility_cost"
    )
    assert assumption["unit"] == currency

    comparison = client.get(f"/api/scenarios/{sid}/comparison")
    assert comparison.status_code == 200


# ---------------------------------------------------------------------------
# 2 + 3. Electricity contract decision
# ---------------------------------------------------------------------------


def _price(contract_id: str, component: str, price: str, currency: str) -> dict:
    return {
        "contract_id": contract_id,
        "contract_name": contract_id.title(),
        "provider": f"{contract_id}-provider",
        "contract_type": "electricity",
        "price_component": component,
        "billing_cycle": "per_kwh" if component == "energy" else "monthly",
        "unit_price": price,
        "currency": currency,
        "quantity_unit": "kWh" if component == "energy" else None,
        "valid_from": "2025-01-01",
        "valid_to": None,
        "status": "active",
    }


def _usage_months(currency: str, months: int = 12) -> list[dict]:
    return [
        {
            "billing_month": f"2025-{index:02d}",
            "utility_type": "electricity",
            "usage_amount": "400",
            "total_cost": "60.00",
            "currency": currency,
        }
        for index in range(1, months + 1)
    ]


def test_energy_contract_refuses_mixed_base_fee_currency() -> None:
    price_rows = [
        _price("current", "energy", "0.0825", "EUR"),
        _price("current", "base_fee", "5.99", "USD"),
        _price("quote", "energy", "0.06", "EUR"),
        _price("quote", "base_fee", "3.99", "EUR"),
    ]
    assessment = assess_energy_contract_review(
        contract_id="current",
        price_rows=price_rows,
        review_candidates=[],
        renewal_watchlist=[],
        cost_trend_rows=_usage_months("EUR"),
    )

    assert assessment["verdict"] == "insufficient_evidence"
    assert "base_fee_currency_mismatch" in assessment["reason_codes"]
    assert assessment["estimated_annual_cost_current_eur"] is None
    assert assessment["estimated_annual_difference_eur"] is None
    assert assessment["remediation"]


def test_energy_contract_eur_same_currency_still_compares() -> None:
    price_rows = [
        _price("current", "energy", "0.0825", "EUR"),
        _price("current", "base_fee", "5.99", "EUR"),
        _price("quote", "energy", "0.06", "EUR"),
        _price("quote", "base_fee", "3.99", "EUR"),
    ]
    assessment = assess_energy_contract_review(
        contract_id="current",
        price_rows=price_rows,
        review_candidates=[],
        renewal_watchlist=[],
        cost_trend_rows=_usage_months("EUR"),
    )

    assert assessment["verdict"] == "alternative_estimated_cheaper"
    assert assessment["reason_codes"] == []
    assert assessment["currency"] == "EUR"


def test_energy_contract_usd_baseline_units_follow_the_currency() -> None:
    price_rows = [
        _price("current", "energy", "0.0825", "USD"),
        _price("current", "base_fee", "5.99", "USD"),
        _price("quote", "energy", "0.06", "USD"),
        _price("quote", "base_fee", "3.99", "USD"),
    ]
    assessment = assess_energy_contract_review(
        contract_id="current",
        price_rows=price_rows,
        review_candidates=[],
        renewal_watchlist=[],
        cost_trend_rows=_usage_months("USD"),
    )

    assert assessment["currency"] == "USD"
    assert assessment["verdict"] == "alternative_estimated_cheaper"

    # The `_eur` key names are compatibility API keys; the unit is what must be
    # truthful, and for a USD assessment it is USD/year (never EUR/year).
    baseline = energy_contract_baseline(assessment)
    for key in (
        "estimated_annual_cost_current_eur",
        "estimated_annual_cost_best_alternative_eur",
        "estimated_annual_difference_eur",
    ):
        assert baseline[key]["unit"] == "USD/year", key
        assert baseline[key]["value"] is not None


# ---------------------------------------------------------------------------
# 4. Utilities cost trend
# ---------------------------------------------------------------------------


def test_utility_trend_keeps_unbilled_meter_out_of_the_billed_denomination() -> None:
    svc = _service()
    svc.load_bills([_bill("billed", "100", "EUR")], run_id="run-bill")
    svc.load_utility_usage(
        [_usage("billed", "100"), _usage("unbilled", "100")], run_id="run-usage"
    )
    _refresh_utilities(svc)

    rows = get_utility_cost_trend_monthly(svc.store, utility_type="electricity")

    billed = [row for row in rows if row["currency"] == "EUR"]
    unbilled = [row for row in rows if row["currency"] is None]

    assert len(billed) == 1
    assert Decimal(str(billed[0]["total_cost"])) == 100
    assert Decimal(str(billed[0]["usage_amount"])) == 100
    assert Decimal(str(billed[0]["unit_price_effective"])) == 1
    assert billed[0]["meter_count"] == 1

    assert len(unbilled) == 1
    assert Decimal(str(unbilled[0]["total_cost"])) == 0
    assert Decimal(str(unbilled[0]["usage_amount"])) == 100
    assert unbilled[0]["unit_price_effective"] is None
    assert unbilled[0]["meter_count"] == 1
