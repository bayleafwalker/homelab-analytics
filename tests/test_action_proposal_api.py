"""API tests for the adapter-agnostic action proposal queue.

  GET  /api/actions/proposals
  POST /api/actions/proposals
  GET  /api/actions/proposals/{action_id}
  POST /api/actions/proposals/{action_id}/approve
  POST /api/actions/proposals/{action_id}/dismiss

The queue is shared with the HA approval surface: agent proposals must be
visible and approvable through the same ``/api/ha/actions/proposals`` routes
the web shell uses, without triggering the HA dispatcher release path.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.homelab.pipelines.ha_action_proposals import (
    ApprovalActionProposal,
    ApprovalActionRegistry,
)
from packages.platform.action_proposals import (
    ActionProposal,
    ActionProposalRegistry,
)
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


class _DispatchRecord:
    result = "success"


class _StubDispatcher:
    """Counts HA release calls so tests can assert adapter gating."""

    def __init__(self) -> None:
        self.resolutions: list[tuple[str, str]] = []

    async def resolve_approval(self, proposal, resolution) -> _DispatchRecord:
        self.resolutions.append((proposal.action_id, resolution))
        return _DispatchRecord()


def _build_client(
    tmp: str,
    *,
    dispatcher: _StubDispatcher | None = None,
    registry: ActionProposalRegistry | None = None,
) -> TestClient:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )
    from packages.pipelines.transformation_service import TransformationService

    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    app = create_app(
        service,
        transformation_service=TransformationService(DuckDBStore.memory()),
        ha_action_dispatcher=dispatcher,
        ha_action_proposal_registry=registry,
    )
    return TestClient(app)


def _agent_proposal_body(**overrides) -> dict:
    body = {
        "policy_id": "mcp:propose_action",
        "policy_name": "Agent drafted: lower office heating",
        "verdict": "notify",
        "value": "19.5",
        "adapter": "platform",
        "source_kind": "agent",
        "source_summary": "Suggested from mart_climate_summary trend",
        "provenance": {
            "publication_keys": ["mart_climate_summary"],
            "confidence_verdict_at_draft": "trusted",
        },
    }
    body.update(overrides)
    return body


class ActionProposalQueueAPITests(unittest.TestCase):
    def test_agent_proposal_enters_shared_queue(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            created = client.post("/api/actions/proposals", json=_agent_proposal_body())
            self.assertEqual(200, created.status_code)
            data = created.json()
            self.assertEqual("pending", data["status"])
            self.assertEqual("agent", data["source_kind"])
            self.assertEqual("platform", data["adapter"])
            self.assertEqual(
                ["mart_climate_summary"],
                data["provenance"]["publication_keys"],
            )

            # Visible on the generalized list and on the HA list the web shell reads.
            generalized = client.get("/api/actions/proposals").json()["proposals"]
            ha_view = client.get("/api/ha/actions/proposals").json()["proposals"]
            self.assertEqual([data["action_id"]], [p["action_id"] for p in generalized])
            self.assertEqual([data["action_id"]], [p["action_id"] for p in ha_view])

    def test_agent_proposal_approvable_from_web_shell_route_without_ha_release(self) -> None:
        dispatcher = _StubDispatcher()
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp, dispatcher=dispatcher)
            action_id = client.post(
                "/api/actions/proposals", json=_agent_proposal_body()
            ).json()["action_id"]

            # The web shell posts to the HA approve route; a platform-adapter
            # proposal must approve without releasing anything through HA.
            resp = client.post(f"/api/ha/actions/proposals/{action_id}/approve")
            self.assertEqual(200, resp.status_code)
            self.assertEqual("approved", resp.json()["status"])
            self.assertEqual([], dispatcher.resolutions)

    def test_ha_proposal_approval_still_releases_through_dispatcher(self) -> None:
        dispatcher = _StubDispatcher()
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp, dispatcher=dispatcher)
            action_id = client.post(
                "/api/ha/actions/proposals",
                json={
                    "policy_id": "office_temp_low",
                    "policy_name": "Office temperature low",
                    "verdict": "approval_required",
                    "value": "17.0",
                },
            ).json()["action_id"]

            resp = client.post(f"/api/actions/proposals/{action_id}/approve")
            self.assertEqual(200, resp.status_code)
            self.assertEqual([(action_id, "approved")], dispatcher.resolutions)

    def test_dismiss_and_status_filter(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            kept = client.post("/api/actions/proposals", json=_agent_proposal_body()).json()
            dropped = client.post("/api/actions/proposals", json=_agent_proposal_body()).json()

            resp = client.post(f"/api/actions/proposals/{dropped['action_id']}/dismiss")
            self.assertEqual(200, resp.status_code)
            self.assertEqual("dismissed", resp.json()["status"])

            pending = client.get("/api/actions/proposals", params={"status": "pending"})
            self.assertEqual(
                [kept["action_id"]],
                [p["action_id"] for p in pending.json()["proposals"]],
            )

    def test_unknown_action_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            self.assertEqual(404, client.get("/api/actions/proposals/missing").status_code)
            self.assertEqual(
                404, client.post("/api/actions/proposals/missing/approve").status_code
            )

    def test_queue_shared_with_explicit_ha_registry(self) -> None:
        registry = ActionProposalRegistry()
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp, registry=registry)
            action_id = client.post(
                "/api/actions/proposals", json=_agent_proposal_body()
            ).json()["action_id"]
            self.assertIsNotNone(registry.get(action_id))


class LegacyAliasTests(unittest.TestCase):
    def test_ha_module_aliases_platform_model(self) -> None:
        self.assertIs(ApprovalActionRegistry, ActionProposalRegistry)
        self.assertIs(ApprovalActionProposal, ActionProposal)

    def test_ha_registrations_default_to_home_assistant_adapter(self) -> None:
        registry = ApprovalActionRegistry()
        proposal = registry.register(
            policy_id="p1",
            policy_name="Policy 1",
            verdict="approval_required",
            value=None,
            notification_id=None,
        )
        self.assertEqual("home_assistant", proposal.adapter)
        self.assertEqual("home_assistant", proposal.to_dict()["adapter"])


if __name__ == "__main__":
    unittest.main()
