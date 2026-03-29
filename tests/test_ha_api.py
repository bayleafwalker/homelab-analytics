"""API tests for HA integration routes — ingest and query."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.ha_action_proposals import ApprovalActionRegistry
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


def _build_client(
    temp_dir: str,
    *,
    bridge: object | None = None,
    proposal_registry: ApprovalActionRegistry | None = None,
    action_dispatcher: object | None = None,
) -> TestClient:
    from packages.pipelines.account_transaction_service import AccountTransactionService

    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    app = create_app(
        service,
        transformation_service=ts,
        ha_bridge=bridge,
        ha_action_dispatcher=action_dispatcher,
        ha_action_proposal_registry=proposal_registry or ApprovalActionRegistry(),
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


if __name__ == "__main__":
    unittest.main()
