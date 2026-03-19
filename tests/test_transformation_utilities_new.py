"""Tests for new utility-domain mart publications.

Covers:
- refresh_utility_cost_trend_monthly
- refresh_usage_vs_price_summary
- refresh_contract_review_candidates
- refresh_contract_renewal_watchlist
- Idempotency for each refresh
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Fixture data — bills, usage, and contract prices
# ---------------------------------------------------------------------------

BILL_ROWS = [
    {
        "meter_id": "elec-001",
        "meter_name": "Main Meter",
        "provider": "City Power",
        "utility_type": "electricity",
        "location": "home",
        "billing_period_start": "2026-01-01",
        "billing_period_end": "2026-01-31",
        "billed_amount": "95.00",
        "currency": "EUR",
        "billed_quantity": "350",
        "usage_unit": "kWh",
        "invoice_date": "2026-02-05",
    },
    {
        "meter_id": "elec-001",
        "meter_name": "Main Meter",
        "provider": "City Power",
        "utility_type": "electricity",
        "location": "home",
        "billing_period_start": "2026-02-01",
        "billing_period_end": "2026-02-28",
        "billed_amount": "88.00",
        "currency": "EUR",
        "billed_quantity": "310",
        "usage_unit": "kWh",
        "invoice_date": "2026-03-05",
    },
    {
        "meter_id": "gas-001",
        "meter_name": "Gas Meter",
        "provider": "Gas Corp",
        "utility_type": "gas",
        "location": "home",
        "billing_period_start": "2026-01-01",
        "billing_period_end": "2026-01-31",
        "billed_amount": "60.00",
        "currency": "EUR",
        "billed_quantity": "120",
        "usage_unit": "liters",
        "invoice_date": "2026-02-10",
    },
]

USAGE_ROWS = [
    {
        "meter_id": "elec-001",
        "meter_name": "Main Meter",
        "utility_type": "electricity",
        "location": "home",
        "usage_start": "2026-01-01",
        "usage_end": "2026-01-31",
        "usage_quantity": "350",
        "usage_unit": "kWh",
        "reading_source": "smart-meter",
    },
    {
        "meter_id": "elec-001",
        "meter_name": "Main Meter",
        "utility_type": "electricity",
        "location": "home",
        "usage_start": "2026-02-01",
        "usage_end": "2026-02-28",
        "usage_quantity": "310",
        "usage_unit": "kWh",
        "reading_source": "smart-meter",
    },
]

# Contract prices for review/renewal tests
_today = date.today()
_30d = _today + timedelta(days=30)
_past = _today - timedelta(days=400)

CONTRACT_PRICE_ROWS = [
    {
        "contract_id": "cp-elec-std",
        "contract_name": "Electricity Standard",
        "provider": "City Power",
        "contract_type": "electricity",
        "price_component": "energy",
        "billing_cycle": "monthly",
        "unit_price": "0.30",
        "currency": "EUR",
        "quantity_unit": "kWh",
        "valid_from": str(_past),
        "valid_to": None,
    },
    {
        "contract_id": "cp-gas-fixed",
        "contract_name": "Gas Fixed",
        "provider": "Gas Corp",
        "contract_type": "gas",
        "price_component": "energy",
        "billing_cycle": "monthly",
        "unit_price": "0.50",
        "currency": "EUR",
        "quantity_unit": "liters",
        "valid_from": str(_today - timedelta(days=60)),
        "valid_to": str(_30d),
    },
    {
        "contract_id": "cp-elec-premium",
        "contract_name": "Electricity Premium",
        "provider": "Premium Power",
        "contract_type": "electricity",
        "price_component": "energy",
        "billing_cycle": "monthly",
        "unit_price": "0.45",
        "currency": "EUR",
        "quantity_unit": "kWh",
        "valid_from": str(_today - timedelta(days=30)),
        "valid_to": str(_today + timedelta(days=60)),
    },
]


@pytest.fixture()
def svc() -> TransformationService:
    store = DuckDBStore.memory()
    s = TransformationService(store)
    s.load_bills(BILL_ROWS, run_id="run-bill-001")
    s.load_utility_usage(USAGE_ROWS, run_id="run-usage-001")
    s.refresh_utility_cost_summary()
    s.load_contract_prices(CONTRACT_PRICE_ROWS, run_id="run-cp-001")
    s.refresh_contract_price_current()
    return s


# ---------------------------------------------------------------------------
# utility_cost_trend_monthly
# ---------------------------------------------------------------------------


class TestUtilityCostTrendMonthly:
    def test_refresh_returns_row_count(self, svc: TransformationService) -> None:
        count = svc.refresh_utility_cost_trend_monthly()
        assert count > 0

    def test_rows_grouped_by_utility_type(self, svc: TransformationService) -> None:
        svc.refresh_utility_cost_trend_monthly()
        rows = svc.get_utility_cost_trend_monthly()
        types = {r["utility_type"] for r in rows}
        assert "electricity" in types

    def test_type_filter(self, svc: TransformationService) -> None:
        svc.refresh_utility_cost_trend_monthly()
        elec = svc.get_utility_cost_trend_monthly(utility_type="electricity")
        assert all(r["utility_type"] == "electricity" for r in elec)

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_utility_cost_trend_monthly()
        count2 = svc.refresh_utility_cost_trend_monthly()
        assert count1 == count2


# ---------------------------------------------------------------------------
# usage_vs_price_summary
# ---------------------------------------------------------------------------


class TestUsageVsPriceSummary:
    def test_refresh_returns_row_count(self, svc: TransformationService) -> None:
        svc.refresh_utility_cost_trend_monthly()
        count = svc.refresh_usage_vs_price_summary()
        # Need at least 2 months of data to compute changes
        # We have 2 months for electricity, so should get >= 1 row
        assert count >= 1

    def test_dominant_driver_populated(self, svc: TransformationService) -> None:
        svc.refresh_utility_cost_trend_monthly()
        svc.refresh_usage_vs_price_summary()
        rows = svc.get_usage_vs_price_summary()
        for row in rows:
            assert row["dominant_driver"] in ("price", "usage", "unknown")

    def test_idempotent(self, svc: TransformationService) -> None:
        svc.refresh_utility_cost_trend_monthly()
        count1 = svc.refresh_usage_vs_price_summary()
        count2 = svc.refresh_usage_vs_price_summary()
        assert count1 == count2


# ---------------------------------------------------------------------------
# contract_review_candidates
# ---------------------------------------------------------------------------


class TestContractReviewCandidates:
    def test_refresh_returns_row_count(self, svc: TransformationService) -> None:
        count = svc.refresh_contract_review_candidates()
        # With 2 electricity contracts (one above avg price), should flag at least 1
        assert count >= 1

    def test_reason_populated(self, svc: TransformationService) -> None:
        svc.refresh_contract_review_candidates()
        rows = svc.get_contract_review_candidates()
        for row in rows:
            assert row["reason"], f"Empty reason for contract {row['contract_id']}"

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_contract_review_candidates()
        count2 = svc.refresh_contract_review_candidates()
        assert count1 == count2


# ---------------------------------------------------------------------------
# contract_renewal_watchlist
# ---------------------------------------------------------------------------


class TestContractRenewalWatchlist:
    def test_refresh_returns_row_count(self, svc: TransformationService) -> None:
        # Gas Fixed has valid_to in 30 days (within 90-day default lookahead)
        count = svc.refresh_contract_renewal_watchlist()
        assert count >= 1

    def test_days_until_renewal_populated(self, svc: TransformationService) -> None:
        svc.refresh_contract_renewal_watchlist()
        rows = svc.get_contract_renewal_watchlist()
        for row in rows:
            assert row["days_until_renewal"] is not None
            assert row["days_until_renewal"] >= 0

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_contract_renewal_watchlist()
        count2 = svc.refresh_contract_renewal_watchlist()
        assert count1 == count2
