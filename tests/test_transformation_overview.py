"""Tests for overview domain composition — cross-domain mart publications.

Covers:
- refresh_household_overview
- refresh_open_attention_items
- refresh_recent_significant_changes
- refresh_current_operating_baseline
- Idempotency for each refresh
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from packages.domains.finance.pipelines.transformation_subscriptions import (
    refresh_subscription_summary,
    refresh_upcoming_fixed_costs_30d,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    refresh_account_balance_trend,
    refresh_monthly_cashflow,
    refresh_spend_by_category_monthly,
    refresh_transaction_anomalies_current,
)
from packages.domains.homelab.pipelines.transformation_homelab import (
    refresh_service_health_current,
    refresh_workload_cost_7d,
)
from packages.domains.overview.pipelines.transformation_overview import (
    get_current_operating_baseline,
    get_homelab_roi,
    get_household_overview,
    get_open_attention_items,
    get_recent_significant_changes,
    refresh_current_operating_baseline,
    refresh_homelab_roi,
    refresh_household_overview,
    refresh_open_attention_items,
    refresh_recent_significant_changes,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    refresh_utility_cost_summary,
    refresh_utility_cost_trend_monthly,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from tests.test_homelab_domain import _service_rows, _workload_rows

# ---------------------------------------------------------------------------
# Fixture data — seed all three feeder domains.
# Transaction months are relative to today so now-windowed marts (e.g. the
# transaction-anomalies 90-day lookback feeding open_attention_items) keep
# seeing the fixture rows as real time passes.
# ---------------------------------------------------------------------------

_CURR_MONTH_START = date.today().replace(day=1)
_PREV_MONTH_START = (_CURR_MONTH_START - timedelta(days=1)).replace(day=1)
MONTH_A = _PREV_MONTH_START.strftime("%Y-%m")
MONTH_B = _CURR_MONTH_START.strftime("%Y-%m")

TRANSACTION_ROWS = [
    {
        "booked_at": f"{MONTH_A}-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-50.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": f"{MONTH_A}-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2500.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": f"{MONTH_B}-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-60.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": f"{MONTH_B}-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2500.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": f"{MONTH_B}-20",
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
    refresh_monthly_cashflow(s.store)
    refresh_spend_by_category_monthly(s.store)
    refresh_account_balance_trend(s.store)
    refresh_transaction_anomalies_current(s.store)

    # Subscriptions
    s.load_subscriptions(SUBSCRIPTION_ROWS, run_id="run-sub-001")
    refresh_subscription_summary(s.store)
    refresh_upcoming_fixed_costs_30d(s.store)

    # Utilities
    s.load_bills(BILL_ROWS, run_id="run-bill-001")
    refresh_utility_cost_summary(s.store)
    refresh_utility_cost_trend_monthly(s.store)

    return s


# ---------------------------------------------------------------------------
# household_overview
# ---------------------------------------------------------------------------


class TestHouseholdOverview:
    def test_refresh_returns_one_row(self, svc: TransformationService) -> None:
        count = refresh_household_overview(svc.store)
        assert count == 1

    def test_overview_fields_populated(self, svc: TransformationService) -> None:
        refresh_household_overview(svc.store)
        rows = get_household_overview(svc.store)
        assert len(rows) == 1
        row = rows[0]
        assert row["current_month"] != ""
        assert row["cashflow_income"] > 0
        assert row["cashflow_expense"] > 0
        assert row["account_balance_direction"] in ("up", "down", "flat")

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = refresh_household_overview(svc.store)
        count2 = refresh_household_overview(svc.store)
        assert count1 == count2
        rows = get_household_overview(svc.store)
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# open_attention_items
# ---------------------------------------------------------------------------


class TestOpenAttentionItems:
    def test_refresh_returns_items(self, svc: TransformationService) -> None:
        count = refresh_open_attention_items(svc.store)
        # New Vendor (300, first occurrence) should produce at least 1 anomaly attention item
        assert count >= 1

    def test_items_have_required_fields(self, svc: TransformationService) -> None:
        refresh_open_attention_items(svc.store)
        rows = get_open_attention_items(svc.store)
        for row in rows:
            assert row["item_id"]
            assert row["item_type"]
            assert row["title"]
            assert row["detail"]
            assert row["severity"] >= 1
            assert row["source_domain"] in ("finance", "utilities")

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = refresh_open_attention_items(svc.store)
        count2 = refresh_open_attention_items(svc.store)
        assert count1 == count2


# ---------------------------------------------------------------------------
# recent_significant_changes
# ---------------------------------------------------------------------------


class TestRecentSignificantChanges:
    def test_refresh_returns_rows(self, svc: TransformationService) -> None:
        count = refresh_recent_significant_changes(svc.store)
        # 2 months of data → at least 1 month-over-month change
        assert count >= 1

    def test_change_fields_populated(self, svc: TransformationService) -> None:
        refresh_recent_significant_changes(svc.store)
        rows = get_recent_significant_changes(svc.store)
        for row in rows:
            assert row["change_type"]
            assert row["period"]
            assert row["description"]
            assert row["direction"] in ("up", "down")

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = refresh_recent_significant_changes(svc.store)
        count2 = refresh_recent_significant_changes(svc.store)
        assert count1 == count2


# ---------------------------------------------------------------------------
# current_operating_baseline
# ---------------------------------------------------------------------------


class TestCurrentOperatingBaseline:
    def test_refresh_returns_four_baseline_rows(self, svc: TransformationService) -> None:
        count = refresh_current_operating_baseline(svc.store)
        assert count == 4

    def test_baseline_types(self, svc: TransformationService) -> None:
        refresh_current_operating_baseline(svc.store)
        rows = get_current_operating_baseline(svc.store)
        types = {r["baseline_type"] for r in rows}
        assert types == {"monthly_spend", "recurring_costs", "utility_baseline", "account_balance"}

    def test_descriptions_populated(self, svc: TransformationService) -> None:
        refresh_current_operating_baseline(svc.store)
        rows = get_current_operating_baseline(svc.store)
        for row in rows:
            assert row["description"], f"Empty description for {row['baseline_type']}"

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = refresh_current_operating_baseline(svc.store)
        count2 = refresh_current_operating_baseline(svc.store)
        assert count1 == count2


# ---------------------------------------------------------------------------
# homelab_roi
# ---------------------------------------------------------------------------


@pytest.fixture()
def homelab_svc() -> TransformationService:
    store = DuckDBStore.memory()
    svc = TransformationService(store)
    svc.load_service_health(_service_rows(), run_id="run-homelab-services")
    refresh_service_health_current(svc.store)
    svc.load_workload_sensors(_workload_rows(), run_id="run-homelab-workloads")
    refresh_workload_cost_7d(svc.store)
    return svc


class TestHomelabRoi:
    def test_refresh_returns_one_row(self, homelab_svc: TransformationService) -> None:
        count = refresh_homelab_roi(homelab_svc.store)
        assert count == 1

    def test_roi_fields_populated(self, homelab_svc: TransformationService) -> None:
        refresh_homelab_roi(homelab_svc.store)
        rows = get_homelab_roi(homelab_svc.store)
        assert len(rows) == 1
        row = rows[0]
        assert row["roi_state"] in {"good", "warning", "needs_action", "empty"}
        assert row["decision_cue"]
        assert row["healthy_service_count"] > 0
        assert row["tracked_workload_count"] > 0
        assert row["monthly_workload_cost"] > 0

    def test_idempotent(self, homelab_svc: TransformationService) -> None:
        count1 = refresh_homelab_roi(homelab_svc.store)
        count2 = refresh_homelab_roi(homelab_svc.store)
        assert count1 == count2
