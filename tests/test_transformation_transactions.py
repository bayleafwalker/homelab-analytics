"""Tests for new transaction-domain mart publications.

Covers:
- refresh_spend_by_category_monthly
- refresh_recent_large_transactions
- refresh_account_balance_trend
- refresh_transaction_anomalies_current
- Idempotency for each refresh
"""

from __future__ import annotations

import pytest

from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Fixture data — transactions across 2 months, 2 accounts, multiple sizes
# ---------------------------------------------------------------------------

LANDING_ROWS = [
    {
        "booked_at": "2026-01-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-42.50",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": "2026-01-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": "2026-01-15",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-38.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": "2026-02-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-45.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": "2026-02-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": "2026-02-20",
        "account_id": "CHK-002",
        "counterparty_name": "Insurance Co",
        "amount": "-850.00",
        "currency": "EUR",
        "description": "Annual premium",
    },
    {
        "booked_at": "2026-02-25",
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
        count = svc.refresh_spend_by_category_monthly()
        assert count > 0

    def test_only_expenses_appear(self, svc: TransformationService) -> None:
        svc.refresh_spend_by_category_monthly()
        rows = svc.get_spend_by_category_monthly()
        counterparties = {r["counterparty_name"] for r in rows}
        assert "Employer" not in counterparties

    def test_month_filter(self, svc: TransformationService) -> None:
        svc.refresh_spend_by_category_monthly()
        jan = svc.get_spend_by_category_monthly(from_month="2026-01", to_month="2026-01")
        feb = svc.get_spend_by_category_monthly(from_month="2026-02", to_month="2026-02")
        assert all(r["booking_month"] == "2026-01" for r in jan)
        assert all(r["booking_month"] == "2026-02" for r in feb)

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_spend_by_category_monthly()
        count2 = svc.refresh_spend_by_category_monthly()
        assert count1 == count2


# ---------------------------------------------------------------------------
# recent_large_transactions
# ---------------------------------------------------------------------------


class TestRecentLargeTransactions:
    def test_refresh_filters_by_threshold(self, svc: TransformationService) -> None:
        from decimal import Decimal

        svc.refresh_recent_large_transactions()
        rows = svc.get_recent_large_transactions()
        # Insurance (850) and One-Off Vendor (200) and Employer (2450) are >= 100
        amounts = [abs(r["amount"]) for r in rows]
        assert all(a >= Decimal("100") for a in amounts)

    def test_refresh_returns_expected_count(self, svc: TransformationService) -> None:
        count = svc.refresh_recent_large_transactions()
        assert count > 0

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_recent_large_transactions()
        count2 = svc.refresh_recent_large_transactions()
        assert count1 == count2


# ---------------------------------------------------------------------------
# account_balance_trend
# ---------------------------------------------------------------------------


class TestAccountBalanceTrend:
    def test_refresh_produces_rows(self, svc: TransformationService) -> None:
        count = svc.refresh_account_balance_trend()
        assert count > 0

    def test_two_accounts_present(self, svc: TransformationService) -> None:
        svc.refresh_account_balance_trend()
        rows = svc.get_account_balance_trend()
        accounts = {r["account_id"] for r in rows}
        assert "CHK-001" in accounts
        assert "CHK-002" in accounts

    def test_cumulative_balance_is_running_sum(self, svc: TransformationService) -> None:
        svc.refresh_account_balance_trend()
        rows = svc.get_account_balance_trend(account_id="CHK-001")
        # Should be ordered by month; cumulative balance of month N =
        # sum of net_change for months 1..N
        running = 0
        for row in rows:
            running += row["net_change"]
            assert row["cumulative_balance"] == running

    def test_month_filter(self, svc: TransformationService) -> None:
        svc.refresh_account_balance_trend()
        jan = svc.get_account_balance_trend(from_month="2026-01", to_month="2026-01")
        assert all(r["booking_month"] == "2026-01" for r in jan)

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_account_balance_trend()
        count2 = svc.refresh_account_balance_trend()
        assert count1 == count2


# ---------------------------------------------------------------------------
# transaction_anomalies_current
# ---------------------------------------------------------------------------


class TestTransactionAnomaliesCurrent:
    def test_refresh_produces_rows(self, svc: TransformationService) -> None:
        count = svc.refresh_transaction_anomalies_current()
        # One-Off Vendor and Insurance Co are first-occurrence counterparties
        assert count > 0

    def test_first_occurrence_detected(self, svc: TransformationService) -> None:
        svc.refresh_transaction_anomalies_current()
        rows = svc.get_transaction_anomalies_current()
        first_occ = [r for r in rows if r["anomaly_type"] == "first_occurrence"]
        names = {r["counterparty_name"] for r in first_occ}
        # Insurance Co (850) and One-Off Vendor (200) are single-transaction
        # counterparties with abs(amount) >= 50
        assert "Insurance Co" in names
        assert "One-Off Vendor" in names

    def test_anomaly_reason_populated(self, svc: TransformationService) -> None:
        svc.refresh_transaction_anomalies_current()
        rows = svc.get_transaction_anomalies_current()
        for row in rows:
            assert row["anomaly_reason"], f"Empty reason for {row['counterparty_name']}"

    def test_idempotent(self, svc: TransformationService) -> None:
        count1 = svc.refresh_transaction_anomalies_current()
        count2 = svc.refresh_transaction_anomalies_current()
        assert count1 == count2
