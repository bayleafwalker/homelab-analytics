"""API tests for scenario routes — POST/GET/DELETE loan what-if scenarios."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


def _build_client(temp_dir: str) -> tuple[TestClient, TransformationService]:
    from packages.pipelines.account_transaction_service import AccountTransactionService

    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    ts.load_loan_repayments(
        [
            {
                "loan_id": "loan-001",
                "loan_name": "API Test Mortgage",
                "lender": "Test Bank",
                "loan_type": "mortgage",
                "principal": "200000.00",
                "annual_rate": "0.045",
                "term_months": "240",
                "start_date": "2023-01-01",
                "payment_frequency": "monthly",
                "repayment_date": "2026-01-01",
                "repayment_month": "2026-01",
                "payment_amount": "1265.00",
                "principal_portion": "515.00",
                "interest_portion": "750.00",
                "extra_amount": None,
                "currency": "EUR",
            }
        ],
        run_id="run-001",
    )
    ts.refresh_loan_schedule_projected()
    app = create_app(service, transformation_service=ts)
    return TestClient(app), ts


class ScenarioCreateAPITests(unittest.TestCase):
    def test_post_creates_scenario_returns_scenario_id(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/loan-what-if",
                json={"loan_id": "loan-001", "extra_repayment": "500.00"},
            )
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("scenario_id", data)
            self.assertIsInstance(data["scenario_id"], str)
            self.assertGreater(len(data["scenario_id"]), 0)

    def test_post_returns_months_saved(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/loan-what-if",
                json={"loan_id": "loan-001", "extra_repayment": "500.00"},
            )
            data = resp.json()
            self.assertGreater(data["months_saved"], 0)

    def test_post_unknown_loan_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/loan-what-if",
                json={"loan_id": "nonexistent-loan"},
            )
            self.assertEqual(404, resp.status_code)

    def test_post_no_transformation_service_returns_503(self) -> None:
        from packages.pipelines.account_transaction_service import AccountTransactionService

        with TemporaryDirectory() as tmp:
            service = AccountTransactionService(
                landing_root=Path(tmp) / "landing",
                metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
            )
            app = create_app(service)
            client = TestClient(app)
            resp = client.post(
                "/api/scenarios/loan-what-if",
                json={"loan_id": "loan-001"},
            )
            self.assertEqual(503, resp.status_code)


class ScenarioGetAPITests(unittest.TestCase):
    def _create_scenario(self, client: TestClient) -> str:
        resp = client.post(
            "/api/scenarios/loan-what-if",
            json={"loan_id": "loan-001", "extra_repayment": "300.00"},
        )
        return resp.json()["scenario_id"]

    def test_get_scenario_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            scenario_id = self._create_scenario(client)
            resp = client.get(f"/api/scenarios/{scenario_id}")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual(scenario_id, data["scenario_id"])
            self.assertEqual("active", data["status"])

    def test_get_unknown_scenario_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.get("/api/scenarios/does-not-exist")
            self.assertEqual(404, resp.status_code)

    def test_get_comparison_returns_baseline_and_scenario_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            scenario_id = self._create_scenario(client)
            resp = client.get(f"/api/scenarios/{scenario_id}/comparison")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("baseline_rows", data)
            self.assertIn("scenario_rows", data)
            self.assertIn("variance_rows", data)
            self.assertGreater(len(data["scenario_rows"]), 0)

    def test_get_comparison_includes_staleness_flag(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            scenario_id = self._create_scenario(client)
            resp = client.get(f"/api/scenarios/{scenario_id}/comparison")
            data = resp.json()
            self.assertIn("is_stale", data)
            self.assertFalse(data["is_stale"])

    def test_get_assumptions_returns_list(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            scenario_id = self._create_scenario(client)
            resp = client.get(f"/api/scenarios/{scenario_id}/assumptions")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("rows", data)
            keys = {r["assumption_key"] for r in data["rows"]}
            self.assertIn("extra_repayment", keys)


class ScenarioDeleteAPITests(unittest.TestCase):
    def test_delete_archives_scenario(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/loan-what-if",
                json={"loan_id": "loan-001", "annual_rate": "0.030"},
            )
            scenario_id = resp.json()["scenario_id"]
            del_resp = client.delete(f"/api/scenarios/{scenario_id}")
            self.assertEqual(200, del_resp.status_code)
            self.assertEqual("archived", del_resp.json()["status"])

    def test_delete_unknown_scenario_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.delete("/api/scenarios/no-such-id")
            self.assertEqual(404, resp.status_code)

    def test_delete_preserves_projection_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            create_resp = client.post(
                "/api/scenarios/loan-what-if",
                json={"loan_id": "loan-001", "extra_repayment": "200.00"},
            )
            scenario_id = create_resp.json()["scenario_id"]
            client.delete(f"/api/scenarios/{scenario_id}")
            # Comparison still returns scenario rows after archive
            comp_resp = client.get(f"/api/scenarios/{scenario_id}/comparison")
            self.assertEqual(200, comp_resp.status_code)
            self.assertGreater(len(comp_resp.json()["scenario_rows"]), 0)


if __name__ == "__main__":
    unittest.main()
