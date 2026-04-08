"""API tests for HA integration routes — ingest and query."""
from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.ha_action_proposals import ApprovalActionRegistry
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


def _build_client(
    temp_dir: str,
    *,
    bridge: object | None = None,
    proposal_registry: ApprovalActionRegistry | None = None,
    action_dispatcher: object | None = None,
    ha_policy_evaluator: object | None = None,
    configure_transformation_service: Callable[[TransformationService], None] | None = None,
    reporting_service: ReportingService | None = None,
) -> TestClient:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    if configure_transformation_service is not None:
        configure_transformation_service(ts)
    app = create_app(
        service,
        transformation_service=ts,
        reporting_service=reporting_service or ReportingService(ts),
        ha_bridge=bridge,
        ha_action_dispatcher=action_dispatcher,
        ha_action_proposal_registry=proposal_registry or ApprovalActionRegistry(),
        ha_policy_evaluator=ha_policy_evaluator,
    )
    return TestClient(app)


def _sample_states() -> list[dict]:
    return [
        {
            "entity_id": "sensor.living_room_temp",
            "state": "21.3",
            "attributes": {"unit_of_measurement": "°C", "friendly_name": "LR Temp"},
            "last_changed": "2026-03-21T10:00:00+00:00",
        },
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "attributes": {"friendly_name": "Kitchen Light"},
            "last_changed": "2026-03-21T10:00:00+00:00",
        },
    ]


def _seed_metric_reporting(ts: TransformationService) -> None:
    today = date.today()
    month_start = today.replace(day=1)

    ts.load_transactions(
        [
            {
                "booked_at": f"{today.year}-{today.month:02d}-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "2500.00",
                "currency": "EUR",
                "description": "salary",
            },
            {
                "booked_at": f"{today.year}-{today.month:02d}-05T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Landlord",
                "amount": "-900.00",
                "currency": "EUR",
                "description": "rent",
            },
        ],
        run_id="txn-001",
    )
    ts.refresh_monthly_cashflow()
    ts.refresh_household_overview()

    ts.load_utility_usage(
        [
            {
                "meter_id": "elec-001",
                "meter_name": "Main Meter",
                "utility_type": "electricity",
                "location": "home",
                "usage_start": month_start.isoformat(),
                "usage_end": today.isoformat(),
                "usage_quantity": "320.50",
                "usage_unit": "kWh",
                "reading_source": "smart-meter",
            }
        ],
        run_id="usage-001",
    )
    ts.load_bills(
        [
            {
                "meter_id": "elec-001",
                "meter_name": "Main Meter",
                "provider": "City Power",
                "utility_type": "electricity",
                "location": "home",
                "billing_period_start": month_start.isoformat(),
                "billing_period_end": today.isoformat(),
                "billed_amount": "48.08",
                "currency": "EUR",
                "billed_quantity": "320.50",
                "usage_unit": "kWh",
                "invoice_date": today.isoformat(),
            }
        ],
        run_id="bill-001",
    )
    ts.refresh_utility_cost_summary()
    ts.refresh_utility_cost_trend_monthly()
    ts.refresh_household_overview()

    ts.load_loan_repayments(
        [
            {
                "loan_id": "loan-001",
                "loan_name": "Test Mortgage",
                "lender": "Test Bank",
                "loan_type": "mortgage",
                "principal": "200000.00",
                "annual_rate": "0.045",
                "term_months": "240",
                "start_date": month_start.isoformat(),
                "payment_frequency": "monthly",
                "repayment_date": today.isoformat(),
                "repayment_month": f"{today.year}-{today.month:02d}",
                "payment_amount": "1265.00",
                "principal_portion": "515.00",
                "interest_portion": "750.00",
                "extra_amount": None,
                "currency": "EUR",
            }
        ],
        run_id="loan-001",
    )
    ts.refresh_loan_schedule_projected()


class HaIngestAPITests(unittest.TestCase):
    def test_post_ingest_returns_count(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.post("/api/ha/ingest", json={"states": _sample_states()})
            self.assertEqual(200, resp.status_code)
            self.assertEqual(2, resp.json()["ingested"])

    def test_post_empty_states_returns_zero(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.post("/api/ha/ingest", json={"states": []})
            self.assertEqual(200, resp.status_code)
            self.assertEqual(0, resp.json()["ingested"])

    def test_post_invalid_body_returns_422(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.post("/api/ha/ingest", json={"not_states": "wrong"})
            self.assertEqual(422, resp.status_code)

    def test_post_run_id_echoed(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.post(
                "/api/ha/ingest",
                json={"states": _sample_states(), "run_id": "test-run-42"},
            )
            self.assertEqual("test-run-42", resp.json()["run_id"])


class HaEntitiesAPITests(unittest.TestCase):
    def _ingest(self, client: TestClient) -> None:
        client.post("/api/ha/ingest", json={"states": _sample_states()})

    def test_get_entities_returns_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            self._ingest(client)
            resp = client.get("/api/ha/entities")
            self.assertEqual(200, resp.status_code)
            rows = resp.json()["rows"]
            self.assertEqual(2, len(rows))

    def test_get_entities_filter_by_class(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            self._ingest(client)
            resp = client.get("/api/ha/entities?entity_class=sensor")
            rows = resp.json()["rows"]
            self.assertEqual(1, len(rows))
            self.assertEqual("sensor.living_room_temp", rows[0]["entity_id"])

    def test_get_entity_history_returns_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            self._ingest(client)
            resp = client.get("/api/ha/entities/sensor.living_room_temp/history")
            self.assertEqual(200, resp.status_code)
            rows = resp.json()["rows"]
            self.assertGreater(len(rows), 0)
            self.assertEqual("21.3", rows[0]["state"])

    def test_get_history_unknown_entity_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/api/ha/entities/sensor.unknown/history")
            self.assertEqual(200, resp.status_code)
            self.assertEqual([], resp.json()["rows"])

    def test_get_history_limit_param(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            # Ingest 5 times
            for i in range(5):
                client.post(
                    "/api/ha/ingest",
                    json={
                        "states": [{"entity_id": "sensor.temp", "state": str(i), "last_changed": f"2026-03-21T{10 + i}:00:00"}],
                        "run_id": f"run-{i:03d}",
                    },
                )
            resp = client.get("/api/ha/entities/sensor.temp/history?limit=2")
            self.assertEqual(2, len(resp.json()["rows"]))


class HaMetricsAPITests(unittest.TestCase):
    def test_get_metric_endpoints_return_scalar_payloads(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp, configure_transformation_service=_seed_metric_reporting)

            cashflow_resp = client.get("/api/ha/metrics/current-month/net-cashflow")
            self.assertEqual(200, cashflow_resp.status_code)
            self.assertEqual(Decimal("1600.0"), Decimal(str(cashflow_resp.json()["value"])))
            self.assertEqual("EUR", cashflow_resp.json()["unit"])

            electricity_resp = client.get("/api/ha/metrics/current-month/electricity-cost")
            self.assertEqual(200, electricity_resp.status_code)
            self.assertEqual(Decimal("48.08"), Decimal(str(electricity_resp.json()["value"])))
            self.assertEqual("EUR", electricity_resp.json()["unit"])

            loan_resp = client.get("/api/ha/metrics/next-loan-payment")
            self.assertEqual(200, loan_resp.status_code)
            self.assertEqual(Decimal("1265.30"), Decimal(str(loan_resp.json()["value"])))
            self.assertEqual("EUR", loan_resp.json()["unit"])

    def test_get_metric_endpoints_return_null_payloads_when_unpopulated(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)

            for path in (
                "/api/ha/metrics/current-month/net-cashflow",
                "/api/ha/metrics/current-month/electricity-cost",
                "/api/ha/metrics/next-loan-payment",
            ):
                resp = client.get(path)
                self.assertEqual(200, resp.status_code)
                self.assertEqual({"value": None, "unit": ""}, resp.json())


class HaApprovalProposalAPITests(unittest.TestCase):
    def test_create_action_proposal_registers_pending_proposal(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)

            create_resp = client.post(
                "/api/ha/actions/proposals",
                json={
                    "policy_id": "monthly_cashflow_review",
                    "policy_name": "Monthly Cashflow Review",
                    "verdict": "warning",
                    "value": "Needs operator review",
                    "source_kind": "assistant",
                    "source_key": "publication.monthly-cashflow",
                    "source_summary": "Review the monthly cashflow publication before executing anything.",
                    "created_by": "assistant",
                    "metadata": {
                        "approval_action": {
                            "domain": "light",
                            "service": "turn_on",
                            "data": {"entity_id": "light.kitchen"},
                        }
                    },
                },
            )
            self.assertEqual(200, create_resp.status_code)
            created = create_resp.json()
            self.assertEqual("pending", created["status"])
            self.assertEqual("assistant", created["source_kind"])
            self.assertEqual("publication.monthly-cashflow", created["source_key"])
            self.assertEqual(
                "Review the monthly cashflow publication before executing anything.",
                created["source_summary"],
            )
            self.assertEqual("assistant", created["created_by"])
            self.assertTrue(created["notification_id"].startswith("approval_"))

    def test_list_and_mutate_action_proposals(self) -> None:
        with TemporaryDirectory() as tmp:
            class _FakeDispatcher:
                def __init__(self) -> None:
                    self.calls: list[tuple[str, str]] = []

                async def resolve_approval(self, proposal, resolution: str):
                    self.calls.append((proposal.action_id, resolution))
                    return type(
                        "Record",
                        (),
                        {"result": resolution},
                    )()

            registry = ApprovalActionRegistry()
            registry.register(
                policy_id="device_control",
                policy_name="Device Control",
                verdict="warning",
                value="needs approval",
                notification_id="homelab_analytics_approval_device_control",
                action_id="homelab_analytics_approval_device_control",
            )
            dispatcher = _FakeDispatcher()
            client = _build_client(tmp, proposal_registry=registry, action_dispatcher=dispatcher)

            list_resp = client.get("/api/ha/actions/proposals")
            self.assertEqual(200, list_resp.status_code)
            self.assertEqual(1, len(list_resp.json()["proposals"]))

            get_resp = client.get("/api/ha/actions/proposals/homelab_analytics_approval_device_control")
            self.assertEqual(200, get_resp.status_code)
            self.assertEqual("pending", get_resp.json()["status"])

            approve_resp = client.post(
                "/api/ha/actions/proposals/homelab_analytics_approval_device_control/approve"
            )
            self.assertEqual(200, approve_resp.status_code)
            self.assertEqual("approved", approve_resp.json()["status"])
            self.assertEqual(
                [("homelab_analytics_approval_device_control", "approved")],
                dispatcher.calls,
            )

            registry.register(
                policy_id="device_control_2",
                policy_name="Device Control 2",
                verdict="warning",
                value=None,
                notification_id="homelab_analytics_approval_device_control_2",
                action_id="homelab_analytics_approval_device_control_2",
            )
            dismiss_resp = client.post(
                "/api/ha/actions/proposals/homelab_analytics_approval_device_control_2/dismiss"
            )
            self.assertEqual(200, dismiss_resp.status_code)
            self.assertEqual("dismissed", dismiss_resp.json()["status"])


class HaStatusAPITests(unittest.TestCase):
    def test_bridge_and_action_status_endpoints_expose_typed_payloads(self) -> None:
        with TemporaryDirectory() as tmp:
            class _FakeBridge:
                def get_status(self) -> dict[str, object]:
                    return {
                        "connected": True,
                        "last_sync_at": "2026-03-21T10:00:00+00:00",
                        "reconnect_count": 3,
                    }

            class _FakeDispatcher:
                def get_status(self) -> dict[str, object]:
                    return {
                        "connected": True,
                        "last_dispatch_at": "2026-03-21T10:05:00+00:00",
                        "dispatch_count": 7,
                        "error_count": 1,
                        "action_log_size": 5,
                        "tracked_policies": 4,
                        "approval_tracked_count": 2,
                        "approval_pending_count": 1,
                        "approval_approved_count": 1,
                        "approval_dismissed_count": 0,
                    }

            client = _build_client(
                tmp,
                bridge=_FakeBridge(),
                action_dispatcher=_FakeDispatcher(),
            )

            bridge_response = client.get("/api/ha/bridge/status")
            self.assertEqual(200, bridge_response.status_code)
            self.assertEqual(
                {
                    "enabled": True,
                    "connected": True,
                    "last_sync_at": "2026-03-21T10:00:00+00:00",
                    "reconnect_count": 3,
                },
                bridge_response.json(),
            )

            actions_response = client.get("/api/ha/actions/status")
            self.assertEqual(200, actions_response.status_code)
            self.assertEqual(
                {
                    "enabled": True,
                    "connected": True,
                    "last_dispatch_at": "2026-03-21T10:05:00+00:00",
                    "dispatch_count": 7,
                    "error_count": 1,
                    "action_log_size": 5,
                    "tracked_policies": 4,
                    "approval_tracked_count": 2,
                    "approval_pending_count": 1,
                    "approval_approved_count": 1,
                    "approval_dismissed_count": 0,
                },
                actions_response.json(),
            )


class HaPoliciesDetailAPITests(unittest.TestCase):
    def test_get_policy_by_id_returns_404_when_evaluator_unavailable(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/api/ha/policies/budget_status")
            self.assertEqual(404, resp.status_code)
            self.assertIn("Policy evaluator unavailable", resp.json()["detail"])

    def test_get_policy_by_id_returns_404_when_policy_not_found(self) -> None:
        with TemporaryDirectory() as tmp:
            class MockEvaluator:
                def evaluate(self):
                    from packages.pipelines.ha_policy import PolicyResult
                    return [
                        PolicyResult(
                            id="budget_status",
                            name="Budget Status",
                            description="Test policy",
                            verdict="ok",
                            value="50%",
                            evaluated_at="2026-03-21T10:00:00+00:00",
                        )
                    ]

            client = _build_client(tmp, ha_policy_evaluator=MockEvaluator())
            resp = client.get("/api/ha/policies/nonexistent_policy")
            self.assertEqual(404, resp.status_code)
            self.assertIn("Policy not found", resp.json()["detail"])

    def test_get_policy_by_id_returns_policy_when_found(self) -> None:
        with TemporaryDirectory() as tmp:
            class MockEvaluator:
                def evaluate(self):
                    from packages.pipelines.ha_policy import PolicyResult
                    return [
                        PolicyResult(
                            id="budget_status",
                            name="Budget Status",
                            description="Test policy",
                            verdict="warning",
                            value="85%",
                            evaluated_at="2026-03-21T10:00:00+00:00",
                        )
                    ]

            client = _build_client(tmp, ha_policy_evaluator=MockEvaluator())
            resp = client.get("/api/ha/policies/budget_status")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("budget_status", data["id"])
            self.assertEqual("Budget Status", data["name"])
            self.assertEqual("warning", data["verdict"])
            self.assertEqual("85%", data["value"])
            self.assertIn("input_freshness", data)


if __name__ == "__main__":
    unittest.main()
