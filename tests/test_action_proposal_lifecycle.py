"""Lifecycle rules for the shared action proposal queue.

- only pending proposals resolve; a second resolution is a 409, never a flip
- every transition lands in an append-only history with actor and reason
- machine principals (service tokens) may draft but never resolve proposals
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.platform.action_proposals import (
    ActionProposalRegistry,
    ProposalTransitionError,
)
from packages.shared.auth import SessionManager, hash_password
from packages.storage.auth_store import LocalUserCreate, UserRole
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


def _register(registry: ActionProposalRegistry, **overrides):
    kwargs = {
        "policy_id": "mcp:propose_action",
        "policy_name": "Agent drafted",
        "verdict": "notify",
        "value": "1",
        "notification_id": None,
        "adapter": "platform",
        "source_kind": "agent",
        "created_by": "agent-a",
    }
    kwargs.update(overrides)
    return registry.register(**kwargs)


def test_registry_records_drafted_and_resolution_history() -> None:
    registry = ActionProposalRegistry()
    proposal = _register(registry)
    resolved = registry.approve(
        proposal.action_id, resolved_by="operator", reason="  looks right  "
    )
    assert resolved.status == "approved"
    assert resolved.resolved_by == "operator"
    assert resolved.resolution_reason == "looks right"
    assert [event.kind for event in resolved.history] == ["drafted", "approved"]
    assert resolved.history[0].actor == "agent-a"
    assert resolved.to_dict()["history"][1] == {
        "kind": "approved",
        "at": resolved.approved_at,
        "actor": "operator",
        "reason": "looks right",
    }


def test_registry_refuses_second_resolution() -> None:
    registry = ActionProposalRegistry()
    proposal = _register(registry)
    registry.dismiss(proposal.action_id, resolved_by="operator")
    with pytest.raises(ProposalTransitionError):
        registry.approve(proposal.action_id, resolved_by="operator")
    stored = registry.get(proposal.action_id)
    assert stored is not None and stored.status == "dismissed"


def test_registry_refresh_appends_history_only_on_change() -> None:
    registry = ActionProposalRegistry()
    proposal = _register(registry, action_id="fixed")
    _register(registry, action_id="fixed")
    _register(registry, action_id="fixed", value="2")
    assert [event.kind for event in proposal.history] == ["drafted", "refreshed"]


def _open_client(tmp: str) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    return TestClient(
        create_app(service, transformation_service=TransformationService(DuckDBStore.memory()))
    )


_BODY = {
    "policy_id": "mcp:propose_action",
    "policy_name": "Agent drafted: lower office heating",
    "verdict": "notify",
    "value": "19.5",
}


@pytest.mark.parametrize("prefix", ["/api/actions/proposals", "/api/ha/actions/proposals"])
def test_second_resolution_is_conflict_on_both_route_families(prefix: str) -> None:
    with TemporaryDirectory() as tmp:
        client = _open_client(tmp)
        action_id = client.post("/api/actions/proposals", json=_BODY).json()["action_id"]
        first = client.post(f"{prefix}/{action_id}/dismiss", json={"reason": "not now"})
        assert first.status_code == 200
        assert first.json()["status"] == "dismissed"
        second = client.post(f"{prefix}/{action_id}/approve")
        assert second.status_code == 409
        assert "already dismissed" in second.json()["detail"]
        detail = client.get(f"/api/actions/proposals/{action_id}").json()
        assert detail["status"] == "dismissed"
        assert detail["resolution_reason"] == "not now"
        assert [event["kind"] for event in detail["history"]] == ["drafted", "dismissed"]


def test_resolution_reason_is_bounded() -> None:
    with TemporaryDirectory() as tmp:
        client = _open_client(tmp)
        action_id = client.post("/api/actions/proposals", json=_BODY).json()["action_id"]
        response = client.post(
            f"/api/actions/proposals/{action_id}/approve", json={"reason": "x" * 501}
        )
        assert response.status_code == 422


def _auth_client(tmp: str) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    repository = IngestionConfigRepository(Path(tmp) / "config.db")
    repository.create_local_user(
        LocalUserCreate(
            user_id="user-1",
            username="admin",
            password_hash=hash_password("admin-password"),
            role=UserRole.ADMIN,
        )
    )
    return TestClient(
        create_app(
            service,
            config_repository=repository,
            auth_store=repository,
            identity_mode="local",
            session_manager=SessionManager("test-session-secret"),
            transformation_service=TransformationService(DuckDBStore.memory()),
        )
    )


def test_machine_principal_can_draft_but_not_resolve() -> None:
    with TemporaryDirectory() as tmp:
        client = _auth_client(tmp)
        login = client.post(
            "/auth/login", json={"username": "admin", "password": "admin-password"}
        )
        assert login.status_code == 200
        csrf = {"x-csrf-token": client.cookies.get("homelab_analytics_csrf") or ""}
        created = client.post(
            "/auth/service-tokens",
            json={
                "token_name": "mcp-agent",
                "role": "admin",
                "scopes": ["reports:read", "admin:write"],
            },
            headers=csrf,
        )
        assert created.status_code == 201
        bearer = {"authorization": f"Bearer {created.json()['token_value']}"}

        agent = TestClient(client.app)
        drafted = agent.post("/api/actions/proposals", json=_BODY, headers=bearer)
        assert drafted.status_code == 200
        assert drafted.json()["created_by"] == "mcp-agent"
        action_id = drafted.json()["action_id"]

        for prefix in ("/api/actions/proposals", "/api/ha/actions/proposals"):
            denied = agent.post(f"{prefix}/{action_id}/approve", headers=bearer)
            assert denied.status_code == 403
            assert "Machine principals" in denied.json()["detail"]

        approved = client.post(
            f"/api/actions/proposals/{action_id}/approve",
            json={"reason": "checked the trend"},
            headers=csrf,
        )
        assert approved.status_code == 200
        payload = approved.json()
        assert payload["resolved_by"] == "admin"
        assert payload["history"][-1]["actor"] == "admin"
