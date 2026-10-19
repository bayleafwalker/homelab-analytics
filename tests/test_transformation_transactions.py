"""Tests for new transaction-domain mart publications.

Covers:
- refresh_spend_by_category_monthly
- refresh_recent_large_transactions
- refresh_account_balance_trend
- refresh_transaction_anomalies_current
- Idempotency for each refresh
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from packages.domains.finance.pipelines.transformation_transactions import (
    get_account_balance_trend,
    get_recent_large_transactions,
    get_spend_by_category_monthly,
    get_transaction_anomalies_current,
    refresh_account_balance_trend,
    refresh_recent_large_transactions,
    refresh_spend_by_category_monthly,
    refresh_transaction_anomalies_current,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Fixture data — transactions across 2 months, 2 accounts, multiple sizes.
# Months are relative to today so now-windowed marts (e.g. transaction
# anomalies, 90-day lookback) keep seeing the fixture rows.
# ---------------------------------------------------------------------------

_CURR_MONTH_START = date.today().replace(day=1)
_PREV_MONTH_START = (_CURR_MONTH_START - timedelta(days=1)).replace(day=1)
MONTH_A = _PREV_MONTH_START.strftime("%Y-%m")
MONTH_B = _CURR_MONTH_START.strftime("%Y-%m")

LANDING_ROWS = [
    {
        "booked_at": f"{MONTH_A}-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-42.50",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": f"{MONTH_A}-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": f"{MONTH_A}-15",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-38.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": f"{MONTH_B}-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-45.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": f"{MONTH_B}-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": f"{MONTH_B}-20",
        "account_id": "CHK-002",
        "counterparty_name": "Insurance Co",
        "amount": "-850.00",
        "currency": "EUR",
        "description": "Annual premium",
    },
    {
        "booked_at": f"{MONTH_B}-25",
        "account_id": "CHK-001",
        "counterparty_name": "One-Off Vendor",
        "amount": "-200.00",
        "currency": "EUR",
        "description": "One-time purchase",
    },
]


@pytest.fixture()
def svc() -> TransformationService:
    store = DuckDBStore.memory()
    s = TransformationService(store)
    s.load_transactions(LANDING_ROWS, run_id="run-tx-001")
    return s


# ---------------------------------------------------------------------------
# spend_by_category_monthly
# ---------------------------------------------------------------------------


class TestSpendByCategoryMonthly:
    def test_refresh_returns_row_count(self, svc: TransformationService) -> None:
        count = refresh_spend_by_category_monthly(svc.store)
        assert count > 0

    def test_only_expenses_appear(self, svc: TransformationService) -> None:
        refresh_spend_by_category_monthly(svc.store)
        rows = get_spend_by_category_monthly(svc.store)
        counterparties = {r["counterparty_name"] for r in rows}
        assert "Employer" not in counterparties

    def test_month_filter(self, svc: TransformationService) -> None:
        refresh_spend_by_category_monthly(svc.store)
        jan = get_spend_by_category_monthly(svc.store, from_month=MONTH_A, to_month=MONTH_A)
        feb = get_spend_by_category_monthly(svc.store, from_month=MONTH_B, to_month=MONTH_B)
        assert all(r["booking_month"] == MONTH_A for r in jan)
        assert all(r["booking_month"] == MONTH_B for r in feb)

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = refresh_spend_by_category_monthly(svc.store)
        count2 = refresh_spend_by_category_monthly(svc.store)
        assert count1 == count2


# ---------------------------------------------------------------------------
# recent_large_transactions
# ---------------------------------------------------------------------------


class TestRecentLargeTransactions:
    def test_refresh_filters_by_threshold(self, svc: TransformationService) -> None:
        from decimal import Decimal

        refresh_recent_large_transactions(svc.store)
        rows = get_recent_large_transactions(svc.store)
        # Insurance (850) and One-Off Vendor (200) and Employer (2450) are >= 100
        amounts = [abs(r["amount"]) for r in rows]
        assert all(a >= Decimal("100") for a in amounts)

    def test_refresh_returns_expected_count(self, svc: TransformationService) -> None:
        count = refresh_recent_large_transactions(svc.store)
        assert count > 0

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = refresh_recent_large_transactions(svc.store)
        count2 = refresh_recent_large_transactions(svc.store)
        assert count1 == count2


# ---------------------------------------------------------------------------
# account_balance_trend
# ---------------------------------------------------------------------------


class TestAccountBalanceTrend:
    def test_refresh_produces_rows(self, svc: TransformationService) -> None:
        count = refresh_account_balance_trend(svc.store)
        assert count > 0

    def test_two_accounts_present(self, svc: TransformationService) -> None:
        refresh_account_balance_trend(svc.store)
        rows = get_account_balance_trend(svc.store)
        accounts = {r["account_id"] for r in rows}
        assert "CHK-001" in accounts
        assert "CHK-002" in accounts

    def test_cumulative_balance_is_running_sum(self, svc: TransformationService) -> None:
        refresh_account_balance_trend(svc.store)
        rows = get_account_balance_trend(svc.store, account_id="CHK-001")
        # Should be ordered by month; cumulative balance of month N =
        # sum of net_change for months 1..N
        running = 0
        for row in rows:
            running += row["net_change"]
            assert row["cumulative_balance"] == running

    def test_month_filter(self, svc: TransformationService) -> None:
        refresh_account_balance_trend(svc.store)
        jan = get_account_balance_trend(svc.store, from_month=MONTH_A, to_month=MONTH_A)
        assert all(r["booking_month"] == MONTH_A for r in jan)

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = refresh_account_balance_trend(svc.store)
        count2 = refresh_account_balance_trend(svc.store)
        assert count1 == count2


# ---------------------------------------------------------------------------
# transaction_anomalies_current
# ---------------------------------------------------------------------------


class TestTransactionAnomaliesCurrent:
    def test_refresh_produces_rows(self, svc: TransformationService) -> None:
        count = refresh_transaction_anomalies_current(svc.store)
        # One-Off Vendor and Insurance Co are first-occurrence counterparties
        assert count > 0

    def test_first_occurrence_detected(self, svc: TransformationService) -> None:
        refresh_transaction_anomalies_current(svc.store)
        rows = get_transaction_anomalies_current(svc.store)
        first_occ = [r for r in rows if r["anomaly_type"] == "first_occurrence"]
        names = {r["counterparty_name"] for r in first_occ}
        # Insurance Co (850) and One-Off Vendor (200) are single-transaction
        # counterparties with abs(amount) >= 50
        assert "Insurance Co" in names
        assert "One-Off Vendor" in names

    def test_anomaly_reason_populated(self, svc: TransformationService) -> None:
        refresh_transaction_anomalies_current(svc.store)
        rows = get_transaction_anomalies_current(svc.store)
        for row in rows:
            assert row["anomaly_reason"], f"Empty reason for {row['counterparty_name']}"

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = refresh_transaction_anomalies_current(svc.store)
        count2 = refresh_transaction_anomalies_current(svc.store)
        assert count1 == count2
