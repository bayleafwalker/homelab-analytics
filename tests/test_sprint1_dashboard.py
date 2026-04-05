"""Sprint 1 — Weekly Money View: fixture-backed tests.

Covers:
- Category aggregation correctness from mart_spend_by_category_monthly
- Utility cost trend API response shape and billing_month field
- Spend-by-category API with date filters
- Utility cost summary API with utility_type filter
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

TRANSACTION_ROWS = [
    # January — groceries
    {
        "booked_at": "2026-01-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-120.00",
        "currency": "EUR",
        "description": "Weekly groceries",
    },
    # January — utilities
    {
        "booked_at": "2026-01-15",
        "account_id": "CHK-001",
        "counterparty_name": "City Power",
        "amount": "-95.00",
        "currency": "EUR",
        "description": "Electricity bill",
    },
    # January — income
    {
        "booked_at": "2026-01-31",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "3000.00",
        "currency": "EUR",
        "description": "Salary",
    },
    # February — groceries
    {
        "booked_at": "2026-02-05",
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-130.00",
        "currency": "EUR",
        "description": "Weekly groceries",
    },
    # February — income
    {
        "booked_at": "2026-02-28",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "3000.00",
        "currency": "EUR",
        "description": "Salary",
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


def _make_transformation_service() -> TransformationService:
    ts = TransformationService(DuckDBStore.memory())
    ts.load_transactions(TRANSACTION_ROWS, run_id="txn-001")
    ts.refresh_monthly_cashflow()
    ts.refresh_spend_by_category_monthly()
    ts.load_bills(BILL_ROWS, run_id="bill-001")
    ts.load_utility_usage(USAGE_ROWS, run_id="usage-001")
    ts.refresh_utility_cost_summary()
    ts.refresh_utility_cost_trend_monthly()
    return ts


def _make_client(ts: TransformationService, temp_dir: str) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    app = create_app(service, transformation_service=ts)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Category aggregation correctness
# ---------------------------------------------------------------------------


class CategoryAggregationTests(unittest.TestCase):
    def test_spend_by_category_monthly_returns_rows(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/spend-by-category-monthly")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertGreater(len(rows), 0)

    def test_spend_by_category_includes_expected_fields(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/spend-by-category-monthly")
        rows = response.json()["rows"]
        first = rows[0]
        for field in ("booking_month", "category", "counterparty_name", "total_expense", "transaction_count"):
            self.assertIn(field, first, f"Missing field: {field}")

    def test_spend_by_category_monthly_from_month_filter(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/spend-by-category-monthly?from_month=2026-02")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        months = {r["booking_month"] for r in rows}
        self.assertNotIn("2026-01", months, "from_month filter should exclude January rows")

    def test_spend_by_category_monthly_to_month_filter(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/spend-by-category-monthly?to_month=2026-01")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        months = {r["booking_month"] for r in rows}
        self.assertNotIn("2026-02", months, "to_month filter should exclude February rows")

    def test_category_totals_are_aggregated(self) -> None:
        """Supermarket appears in both Jan and Feb; each month should have one row per counterparty."""
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/spend-by-category-monthly?from_month=2026-01&to_month=2026-01")
        rows = response.json()["rows"]
        supermarket_rows = [r for r in rows if r["counterparty_name"] == "Supermarket"]
        # Should collapse to one row for the month (or zero if uncategorised hides it, but expense should be present)
        total = sum(float(r["total_expense"]) for r in supermarket_rows)
        self.assertAlmostEqual(120.0, total, places=1)


# ---------------------------------------------------------------------------
# Utility cost trend — billing_month field and API shape
# ---------------------------------------------------------------------------


class UtilityCostTrendTests(unittest.TestCase):
    def test_utility_cost_trend_returns_rows(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-trend")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertGreater(len(rows), 0)

    def test_utility_cost_trend_rows_have_billing_month(self) -> None:
        """Rows must use billing_month (not booking_month) — this was a bug in the UI."""
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-trend")
        rows = response.json()["rows"]
        for row in rows:
            self.assertIn("billing_month", row, "Row must have billing_month field")
            self.assertNotIn("booking_month", row, "billing_month, not booking_month")

    def test_utility_cost_trend_includes_expected_fields(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-trend")
        rows = response.json()["rows"]
        first = rows[0]
        for field in ("billing_month", "utility_type", "total_cost", "currency"):
            self.assertIn(field, first, f"Missing field: {field}")

    def test_utility_cost_trend_electricity_filter(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-trend?utility_type=electricity")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        types = {r["utility_type"] for r in rows}
        self.assertEqual({"electricity"}, types)

    def test_utility_cost_trend_totals_match_bills(self) -> None:
        """Jan electricity total should equal 95.00 from bill fixture."""
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-trend?utility_type=electricity")
        rows = response.json()["rows"]
        jan_row = next((r for r in rows if r["billing_month"] == "2026-01"), None)
        self.assertIsNotNone(jan_row, "Expected a January row for electricity")
        self.assertAlmostEqual(95.0, float(jan_row["total_cost"]), places=1)


# ---------------------------------------------------------------------------
# Utility cost summary API with filters
# ---------------------------------------------------------------------------


class UtilityCostSummaryTests(unittest.TestCase):
    def test_utility_cost_summary_returns_rows(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-summary")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertGreater(len(rows), 0)

    def test_utility_cost_summary_includes_expected_fields(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-summary")
        rows = response.json()["rows"]
        first = rows[0]
        for field in ("period", "meter_id", "utility_type", "billed_amount", "currency"):
            self.assertIn(field, first, f"Missing field: {field}")

    def test_utility_cost_summary_utility_type_filter(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-summary?utility_type=gas")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        types = {r["utility_type"] for r in rows}
        self.assertEqual({"gas"}, types)

    def test_utility_cost_summary_meter_id_filter(self) -> None:
        ts = _make_transformation_service()
        with TemporaryDirectory() as tmp:
            client = _make_client(ts, tmp)
            response = client.get("/reports/utility-cost-summary?meter_id=elec-001")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        meter_ids = {r["meter_id"] for r in rows}
        self.assertEqual({"elec-001"}, meter_ids)


if __name__ == "__main__":
    unittest.main()
