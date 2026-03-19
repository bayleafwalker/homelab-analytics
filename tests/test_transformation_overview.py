"""Tests for overview domain composition — cross-domain mart publications.

Covers:
- refresh_household_overview
- refresh_open_attention_items
- refresh_recent_significant_changes
- refresh_current_operating_baseline
- Idempotency for each refresh
"""

from __future__ import annotations

import pytest

from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Fixture data — seed all three feeder domains
# ---------------------------------------------------------------------------

TRANSACTION_ROWS = [
    {
        "booked_at": "2026-01-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-50.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": "2026-01-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2500.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": "2026-02-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-60.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": "2026-02-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2500.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": "2026-02-20",
        "account_id": "CHK-001",
        "counterparty_name": "New Vendor",
        "amount": "-300.00",
        "currency": "EUR",
        "description": "One-time purchase",
    },
]

SUBSCRIPTION_ROWS = [
    {
        "contract_id": "sub-netflix",
        "service_name": "Netflix",
        "provider": "Netflix Inc.",
        "contract_type": "subscription",
        "billing_cycle": "monthly",
        "amount": "15.99",
        "currency": "EUR",
        "start_date": "2025-01-15",
        "end_date": None,
    },
    {
        "contract_id": "sub-gym",
        "service_name": "Gym",
        "provider": "FitCorp",
        "contract_type": "subscription",
        "billing_cycle": "monthly",
        "amount": "29.99",
        "currency": "EUR",
        "start_date": "2025-06-01",
        "end_date": None,
    },
]

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
]


@pytest.fixture()
def svc() -> TransformationService:
    """Seed all domain marts so overview composition has data to read."""
    store = DuckDBStore.memory()
    s = TransformationService(store)

    # Finance
    s.load_transactions(TRANSACTION_ROWS, run_id="run-tx-001")
    s.refresh_monthly_cashflow()
    s.refresh_spend_by_category_monthly()
    s.refresh_account_balance_trend()
    s.refresh_transaction_anomalies_current()

    # Subscriptions
    s.load_subscriptions(SUBSCRIPTION_ROWS, run_id="run-sub-001")
    s.refresh_subscription_summary()
    s.refresh_upcoming_fixed_costs_30d()

    # Utilities
    s.load_bills(BILL_ROWS, run_id="run-bill-001")
    s.refresh_utility_cost_summary()
    s.refresh_utility_cost_trend_monthly()

    return s


# ---------------------------------------------------------------------------
# household_overview
# ---------------------------------------------------------------------------


class TestHouseholdOverview:
    def test_refresh_returns_one_row(self, svc: TransformationService) -> None:
        count = svc.refresh_household_overview()
        assert count == 1

    def test_overview_fields_populated(self, svc: TransformationService) -> None:
        svc.refresh_household_overview()
        rows = svc.get_household_overview()
        assert len(rows) == 1
        row = rows[0]
        assert row["current_month"] != ""
        assert row["cashflow_income"] > 0
        assert row["cashflow_expense"] > 0
        assert row["account_balance_direction"] in ("up", "down", "flat")

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_household_overview()
        count2 = svc.refresh_household_overview()
        assert count1 == count2
        rows = svc.get_household_overview()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# open_attention_items
# ---------------------------------------------------------------------------


class TestOpenAttentionItems:
    def test_refresh_returns_items(self, svc: TransformationService) -> None:
        count = svc.refresh_open_attention_items()
        # New Vendor (300, first occurrence) should produce at least 1 anomaly attention item
        assert count >= 1

    def test_items_have_required_fields(self, svc: TransformationService) -> None:
        svc.refresh_open_attention_items()
        rows = svc.get_open_attention_items()
        for row in rows:
            assert row["item_id"]
            assert row["item_type"]
            assert row["title"]
            assert row["detail"]
            assert row["severity"] >= 1
            assert row["source_domain"] in ("finance", "utilities")

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_open_attention_items()
        count2 = svc.refresh_open_attention_items()
        assert count1 == count2


# ---------------------------------------------------------------------------
# recent_significant_changes
# ---------------------------------------------------------------------------


class TestRecentSignificantChanges:
    def test_refresh_returns_rows(self, svc: TransformationService) -> None:
        count = svc.refresh_recent_significant_changes()
        # 2 months of data → at least 1 month-over-month change
        assert count >= 1

    def test_change_fields_populated(self, svc: TransformationService) -> None:
        svc.refresh_recent_significant_changes()
        rows = svc.get_recent_significant_changes()
        for row in rows:
            assert row["change_type"]
            assert row["period"]
            assert row["description"]
            assert row["direction"] in ("up", "down")

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_recent_significant_changes()
        count2 = svc.refresh_recent_significant_changes()
        assert count1 == count2


# ---------------------------------------------------------------------------
# current_operating_baseline
# ---------------------------------------------------------------------------


class TestCurrentOperatingBaseline:
    def test_refresh_returns_four_baseline_rows(self, svc: TransformationService) -> None:
        count = svc.refresh_current_operating_baseline()
        assert count == 4

    def test_baseline_types(self, svc: TransformationService) -> None:
        svc.refresh_current_operating_baseline()
        rows = svc.get_current_operating_baseline()
        types = {r["baseline_type"] for r in rows}
        assert types == {"monthly_spend", "recurring_costs", "utility_baseline", "account_balance"}

    def test_descriptions_populated(self, svc: TransformationService) -> None:
        svc.refresh_current_operating_baseline()
        rows = svc.get_current_operating_baseline()
        for row in rows:
            assert row["description"], f"Empty description for {row['baseline_type']}"

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_current_operating_baseline()
        count2 = svc.refresh_current_operating_baseline()
        assert count1 == count2
