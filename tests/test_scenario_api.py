"""API tests for scenario routes — loan and homelab cost/benefit scenarios."""

from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.reporting_service import HomelabCostBenefitBaseline
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository
from tests.test_homelab_domain import _service_rows, _workload_rows


def _build_client(temp_dir: str) -> tuple[TestClient, TransformationService]:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

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


def _build_homelab_client(temp_dir: str) -> tuple[TestClient, TransformationService]:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    ts.load_service_health(_service_rows(), run_id="run-homelab-services")
    ts.refresh_service_health_current()
    ts.load_workload_sensors(_workload_rows(), run_id="run-homelab-workloads")
    ts.refresh_workload_cost_7d()
    app = create_app(service, transformation_service=ts)
    return TestClient(app), ts


class _StubHomelabReportingService:
    def __init__(self) -> None:
        self._baseline = HomelabCostBenefitBaseline(
            service_rows=[
                {"service_id": "svc-a", "state": "running"},
                {"service_id": "svc-b", "state": "running"},
            ],
            workload_rows=[
                {"workload_id": "wk-a", "est_monthly_cost": "5.00"},
            ],
            signature="published-homelab-v1",
        )

    def set_signature(self, signature: str) -> None:
        self._baseline = HomelabCostBenefitBaseline(
            service_rows=self._baseline.service_rows,
            workload_rows=self._baseline.workload_rows,
            signature=signature,
        )

    def get_homelab_cost_benefit_baseline(self) -> HomelabCostBenefitBaseline:
        return self._baseline


def _build_homelab_client_with_reporting(
    temp_dir: str,
) -> tuple[TestClient, TransformationService, _StubHomelabReportingService]:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    ts.load_service_health(_service_rows(), run_id="run-homelab-services")
    ts.refresh_service_health_current()
    ts.load_workload_sensors(_workload_rows(), run_id="run-homelab-workloads")
    ts.refresh_workload_cost_7d()
    reporting_service = _StubHomelabReportingService()
    app = create_app(
        service,
        transformation_service=ts,
        reporting_service=reporting_service,
    )
    return TestClient(app), ts, reporting_service


def _shift_homelab_rows(rows: list[dict], *, hours: int = 1) -> list[dict]:
    shifted = deepcopy(rows)
    for index, row in enumerate(shifted):
        recorded_at = datetime.fromisoformat(row["recorded_at"]) + timedelta(hours=hours)
        row["recorded_at"] = recorded_at.replace(minute=index, second=0, microsecond=0).isoformat()
        if "last_state_change" in row:
            last_state_change = datetime.fromisoformat(row["last_state_change"]) + timedelta(hours=hours)
            row["last_state_change"] = last_state_change.replace(minute=index, second=0, microsecond=0).isoformat()
    return shifted


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
        from packages.domains.finance.pipelines.account_transaction_service import (
            AccountTransactionService,
        )

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

    def test_post_includes_assumptions_summary_key(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.post(
                "/api/scenarios/loan-what-if",
                json={"loan_id": "loan-001", "extra_repayment": "500.00"},
            )
            data = resp.json()
            self.assertIn("assumptions_summary", data)
            # When no control plane is wired, assumptions_summary should be None
            self.assertIsNone(data["assumptions_summary"])


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


class ScenarioCompareSetAPITests(unittest.TestCase):
    def _create_scenario(self, client: TestClient) -> str:
        return client.post(
            "/api/scenarios/loan-what-if",
            json={"loan_id": "loan-001", "extra_repayment": "150.00"},
        ).json()["scenario_id"]

    def _create_two_scenarios(self, client: TestClient) -> tuple[str, str]:
        left = client.post(
            "/api/scenarios/loan-what-if",
            json={"loan_id": "loan-001", "extra_repayment": "100.00"},
        ).json()["scenario_id"]
        right = client.post(
            "/api/scenarios/loan-what-if",
            json={"loan_id": "loan-001", "extra_repayment": "250.00"},
        ).json()["scenario_id"]
        return left, right

    def test_post_creates_compare_set(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            left, right = self._create_two_scenarios(client)
            resp = client.post(
                "/api/scenarios/compare-sets",
                json={
                    "left_scenario_id": left,
                    "right_scenario_id": right,
                    "label": "Loan pair",
                },
            )
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("compare_set_id", data)
            self.assertEqual("Loan pair", data["label"])
            self.assertEqual(left, data["left_scenario_id"])
            self.assertEqual(right, data["right_scenario_id"])

    def test_get_compare_sets_returns_saved_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            left, right = self._create_two_scenarios(client)
            client.post(
                "/api/scenarios/compare-sets",
                json={"left_scenario_id": left, "right_scenario_id": right},
            )
            resp = client.get("/api/scenarios/compare-sets")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual(1, len(data["rows"]))
            self.assertEqual(left, data["rows"][0]["left_scenario_id"])

    def test_patch_renames_compare_set(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            left, right = self._create_two_scenarios(client)
            create_resp = client.post(
                "/api/scenarios/compare-sets",
                json={"left_scenario_id": left, "right_scenario_id": right},
            )
            compare_set_id = create_resp.json()["compare_set_id"]
            patch_resp = client.patch(
                f"/api/scenarios/compare-sets/{compare_set_id}",
                json={"label": "Renamed pair"},
            )
            self.assertEqual(200, patch_resp.status_code)
            self.assertEqual("Renamed pair", patch_resp.json()["label"])

    def test_get_compare_sets_can_include_archived_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            left, right = self._create_two_scenarios(client)
            create_resp = client.post(
                "/api/scenarios/compare-sets",
                json={"left_scenario_id": left, "right_scenario_id": right},
            )
            compare_set_id = create_resp.json()["compare_set_id"]
            client.delete(f"/api/scenarios/compare-sets/{compare_set_id}")
            resp = client.get("/api/scenarios/compare-sets?include_archived=true")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual(1, len(data["rows"]))
            self.assertEqual("archived", data["rows"][0]["status"])

    def test_delete_compare_set_archives_saved_row(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            left, right = self._create_two_scenarios(client)
            create_resp = client.post(
                "/api/scenarios/compare-sets",
                json={"left_scenario_id": left, "right_scenario_id": right},
            )
            compare_set_id = create_resp.json()["compare_set_id"]
            delete_resp = client.delete(f"/api/scenarios/compare-sets/{compare_set_id}")
            self.assertEqual(200, delete_resp.status_code)
            self.assertEqual("archived", delete_resp.json()["status"])
            self.assertEqual(0, len(client.get("/api/scenarios/compare-sets").json()["rows"]))

    def test_post_restore_compare_set_reactivates_archived_row(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            left, right = self._create_two_scenarios(client)
            create_resp = client.post(
                "/api/scenarios/compare-sets",
                json={"left_scenario_id": left, "right_scenario_id": right},
            )
            compare_set_id = create_resp.json()["compare_set_id"]
            client.delete(f"/api/scenarios/compare-sets/{compare_set_id}")
            restore_resp = client.post(f"/api/scenarios/compare-sets/{compare_set_id}/restore")
            self.assertEqual(200, restore_resp.status_code)
            self.assertEqual("active", restore_resp.json()["status"])
            self.assertEqual(1, len(client.get("/api/scenarios/compare-sets").json()["rows"]))

    def test_post_restore_compare_set_rejects_duplicate_active_pair(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            left, right = self._create_two_scenarios(client)
            original_resp = client.post(
                "/api/scenarios/compare-sets",
                json={
                    "left_scenario_id": left,
                    "right_scenario_id": right,
                    "label": "Original pair",
                },
            )
            original_compare_set_id = original_resp.json()["compare_set_id"]
            client.delete(f"/api/scenarios/compare-sets/{original_compare_set_id}")
            replacement_resp = client.post(
                "/api/scenarios/compare-sets",
                json={
                    "left_scenario_id": left,
                    "right_scenario_id": right,
                    "label": "Replacement pair",
                },
            )
            replacement_compare_set_id = replacement_resp.json()["compare_set_id"]
            restore_resp = client.post(
                f"/api/scenarios/compare-sets/{original_compare_set_id}/restore"
            )
            self.assertEqual(409, restore_resp.status_code)
            self.assertIn("active compare set already exists", restore_resp.json()["detail"])
            rows = client.get("/api/scenarios/compare-sets").json()["rows"]
            self.assertEqual(1, len(rows))
            self.assertEqual(replacement_compare_set_id, rows[0]["compare_set_id"])

    def test_post_rejects_same_scenario(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            scenario_id = self._create_scenario(client)
            resp = client.post(
                "/api/scenarios/compare-sets",
                json={
                    "left_scenario_id": scenario_id,
                    "right_scenario_id": scenario_id,
                },
            )
            self.assertEqual(422, resp.status_code)


class HomelabCostBenefitScenarioAPITests(unittest.TestCase):
    def test_post_creates_homelab_cost_benefit_scenario(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_homelab_client(tmp)
            resp = client.post(
                "/api/scenarios/homelab-cost-benefit",
                json={"monthly_cost_delta": "-1.00"},
            )
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("scenario_id", data)
            self.assertLess(float(data["new_monthly_cost"]), float(data["baseline_monthly_cost"]))

    def test_get_homelab_comparison_returns_summary_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_homelab_client(tmp)
            create_resp = client.post(
                "/api/scenarios/homelab-cost-benefit",
                json={"monthly_cost_delta": "15.00"},
            )
            scenario_id = create_resp.json()["scenario_id"]
            resp = client.get(f"/api/scenarios/{scenario_id}/comparison")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("summary_rows", data)
            self.assertNotIn("baseline_rows", data)
            self.assertGreater(len(data["summary_rows"]), 0)
            self.assertTrue(all("metric_key" in row and "metric" in row for row in data["summary_rows"]))
            self.assertIn(
                "healthy_services_per_cost_unit",
                {row["metric_key"] for row in data["summary_rows"]},
            )

    def test_get_cashflow_returns_summary_rows_for_homelab_scenario(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_homelab_client(tmp)
            create_resp = client.post(
                "/api/scenarios/homelab-cost-benefit",
                json={"monthly_cost_delta": "15.00"},
            )
            scenario_id = create_resp.json()["scenario_id"]
            resp = client.get(f"/api/scenarios/{scenario_id}/cashflow")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("summary_rows", data)
            self.assertGreater(len(data["summary_rows"]), 0)
            self.assertTrue(all("metric_key" in row for row in data["summary_rows"]))

    def test_homelab_cost_benefit_uses_reporting_backed_baseline_when_available(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _, _ = _build_homelab_client_with_reporting(tmp)
            resp = client.post(
                "/api/scenarios/homelab-cost-benefit",
                json={"monthly_cost_delta": "1.00"},
            )
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("5.00", data["baseline_monthly_cost"])
            self.assertEqual("6.00", data["new_monthly_cost"])

    def test_homelab_cost_benefit_staleness_uses_reporting_signature_when_available(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _, reporting_service = _build_homelab_client_with_reporting(tmp)
            create_resp = client.post(
                "/api/scenarios/homelab-cost-benefit",
                json={"monthly_cost_delta": "1.00"},
            )
            scenario_id = create_resp.json()["scenario_id"]
            reporting_service.set_signature("published-homelab-v2")
            resp = client.get(f"/api/scenarios/{scenario_id}/comparison")
            self.assertEqual(200, resp.status_code)
            self.assertTrue(resp.json()["is_stale"])

    def test_homelab_cost_benefit_becomes_stale_after_new_fact_run(self) -> None:
        with TemporaryDirectory() as tmp:
            client, ts = _build_homelab_client(tmp)
            create_resp = client.post(
                "/api/scenarios/homelab-cost-benefit",
                json={"monthly_cost_delta": "10.00"},
            )
            scenario_id = create_resp.json()["scenario_id"]
            ts.load_service_health(
                _shift_homelab_rows(_service_rows()),
                run_id="run-homelab-services-v2",
            )
            ts.refresh_service_health_current()
            ts.load_workload_sensors(
                _shift_homelab_rows(_workload_rows()),
                run_id="run-homelab-workloads-v2",
            )
            ts.refresh_workload_cost_7d()
            resp = client.get(f"/api/scenarios/{scenario_id}/comparison")
            self.assertTrue(resp.json()["is_stale"])


if __name__ == "__main__":
    unittest.main()
