"""API tests for income change scenario routes.

  POST /api/scenarios/income-change
  GET  /api/scenarios/{id}/cashflow
  GET  /api/scenarios/{id}              (metadata — shared with loan scenarios)
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


def _build_client(temp_dir: str, load_cashflow: bool = True) -> tuple[TestClient, TransformationService]:
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
            ]
        ts.load_transactions(transactions, run_id="run-001")
        ts.refresh_monthly_cashflow()

    app = create_app(service, transformation_service=ts)
    return TestClient(app), ts


class IncomeScenarioCreateAPITests(unittest.TestCase):
    def test_post_creates_income_scenario_returns_scenario_id(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "500.00"},
            )
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("scenario_id", data)
            self.assertIsInstance(data["scenario_id"], str)
            self.assertGreater(len(data["scenario_id"]), 0)

    def test_post_returns_annual_net_change(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "500.00"},
            )
            data = resp.json()
            self.assertIn("annual_net_change", data)
            self.assertAlmostEqual(float(data["annual_net_change"]), 6000.0, places=1)

    def test_post_income_loss_sets_months_until_deficit(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "-3000.00"},
            )
            data = resp.json()
            self.assertEqual(data["months_until_deficit"], 1)

    def test_post_invalid_decimal_returns_422(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "abc"},
            )
            self.assertEqual(422, resp.status_code)

    def test_post_no_cashflow_data_returns_422(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp, load_cashflow=False)
            resp = client.post(
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "500.00"},
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
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "500.00"},
            )
            self.assertEqual(503, resp.status_code)


class IncomeScenarioCashflowAPITests(unittest.TestCase):
    def test_get_cashflow_returns_12_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            create_resp = client.post(
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "500.00"},
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
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "500.00"},
            )
            sid = create_resp.json()["scenario_id"]
            resp = client.get(f"/api/scenarios/{sid}/cashflow")
            data = resp.json()
            self.assertGreater(len(data["assumptions"]), 0)

    def test_get_cashflow_unknown_scenario_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.get("/api/scenarios/nonexistent-id/cashflow")
            self.assertEqual(404, resp.status_code)

    def test_get_scenario_metadata_shows_income_change_type(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            create_resp = client.post(
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "-500.00"},
            )
            sid = create_resp.json()["scenario_id"]
            resp = client.get(f"/api/scenarios/{sid}")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual(data["scenario_type"], "income_change")


class IncomeScenarioArchiveAPITests(unittest.TestCase):
    def test_delete_archives_income_scenario(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            create_resp = client.post(
                "/api/scenarios/income-change",
                json={"monthly_income_delta": "200.00"},
            )
            sid = create_resp.json()["scenario_id"]
            resp = client.delete(f"/api/scenarios/{sid}")
            self.assertEqual(200, resp.status_code)
            self.assertEqual(resp.json()["status"], "archived")

    def test_delete_unknown_scenario_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.delete("/api/scenarios/nonexistent-id")
            self.assertEqual(404, resp.status_code)
