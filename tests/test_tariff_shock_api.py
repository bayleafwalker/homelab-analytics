"""API tests for tariff shock scenario routes.

  POST /api/scenarios/tariff-shock
  GET  /api/scenarios/{id}/cashflow     (shared with income change)
  GET  /api/scenarios/{id}              (metadata — shared)
  DELETE /api/scenarios/{id}            (archive — shared)
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

UTILITY_BILL_ROWS = [
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

UTILITY_USAGE_ROWS = [
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


def _build_client(
    temp_dir: str,
    *,
    load_cashflow: bool = True,
    load_utility_data: bool = True,
) -> tuple[TestClient, TransformationService]:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())

    if load_cashflow:
        transactions = []
        for month in ["01", "02", "03"]:
            transactions += [
                {
                    "booked_at": f"2026-{month}-03T08:00:00+00:00",
                    "account_id": "checking",
                    "counterparty_name": "Employer",
                    "amount": "3000.00",
                    "currency": "EUR",
                    "description": "salary",
                },
                {
                    "booked_at": f"2026-{month}-10T08:00:00+00:00",
                    "account_id": "checking",
                    "counterparty_name": "Landlord",
                    "amount": "-1200.00",
                    "currency": "EUR",
                    "description": "rent",
                },
                {
                    "booked_at": f"2026-{month}-15T08:00:00+00:00",
                    "account_id": "checking",
                    "counterparty_name": "Supermarket",
                    "amount": "-400.00",
                    "currency": "EUR",
                    "description": "groceries",
                },
            ]
        ts.load_transactions(transactions, run_id="run-api-tariff-001")
        ts.refresh_monthly_cashflow()

    if load_utility_data:
        ts.load_bills(UTILITY_BILL_ROWS, run_id="run-api-bill-001")
        ts.load_utility_usage(UTILITY_USAGE_ROWS, run_id="run-api-usage-001")
        ts.refresh_utility_cost_summary()
        ts.refresh_utility_cost_trend_monthly()

    app = create_app(service, transformation_service=ts)
    return TestClient(app), ts


class TariffShockCreateAPITests(unittest.TestCase):
    def test_post_creates_tariff_shock_returns_scenario_id(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "0.10"},
            )
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("scenario_id", data)
            self.assertIsInstance(data["scenario_id"], str)
            self.assertGreater(len(data["scenario_id"]), 0)

    def test_post_returns_headline_deltas(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "0.10"},
            )
            data = resp.json()
            self.assertIn("baseline_monthly_utility_cost", data)
            self.assertIn("new_monthly_utility_cost", data)
            self.assertIn("annual_additional_cost", data)
            self.assertIn("months_until_deficit", data)
            self.assertGreater(
                float(data["new_monthly_utility_cost"]),
                float(data["baseline_monthly_utility_cost"]),
            )

    def test_post_invalid_decimal_returns_422(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "not-a-number"},
            )
            self.assertEqual(422, resp.status_code)

    def test_post_no_utility_data_returns_422(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp, load_utility_data=False)
            resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "0.10"},
            )
            self.assertEqual(422, resp.status_code)

    def test_post_no_transformation_service_returns_503(self) -> None:
        with TemporaryDirectory() as tmp:
            from packages.domains.finance.pipelines.account_transaction_service import (
                AccountTransactionService,
            )

            service = AccountTransactionService(
                landing_root=Path(tmp) / "landing",
                metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
            )
            app = create_app(service, transformation_service=None)
            client = TestClient(app)
            resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "0.10"},
            )
            self.assertEqual(503, resp.status_code)


class TariffShockComparisonAPITests(unittest.TestCase):
    def test_get_cashflow_returns_12_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            create_resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "0.10"},
            )
            sid = create_resp.json()["scenario_id"]
            resp = client.get(f"/api/scenarios/{sid}/cashflow")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual(len(data["cashflow_rows"]), 12)

    def test_get_cashflow_includes_assumptions(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            create_resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "0.10"},
            )
            sid = create_resp.json()["scenario_id"]
            resp = client.get(f"/api/scenarios/{sid}/cashflow")
            data = resp.json()
            self.assertGreater(len(data["assumptions"]), 0)

    def test_get_scenario_metadata_shows_tariff_shock_type(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            create_resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "0.15"},
            )
            sid = create_resp.json()["scenario_id"]
            resp = client.get(f"/api/scenarios/{sid}")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual(data["scenario_type"], "tariff_shock")

    def test_delete_archives_tariff_shock_scenario(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            create_resp = client.post(
                "/api/scenarios/tariff-shock",
                json={"tariff_pct_delta": "0.10"},
            )
            sid = create_resp.json()["scenario_id"]
            resp = client.delete(f"/api/scenarios/{sid}")
            self.assertEqual(200, resp.status_code)
            self.assertEqual(resp.json()["status"], "archived")
