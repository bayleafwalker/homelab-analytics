"""Draft-only agent scopes and the aligned proposal permissions.

- ``proposals:draft`` lets a token enter proposals into the queue on both
  route families; ``policies:draft`` lets an admin-role token create a policy
  that is stored disabled. Neither reaches approve, dismiss, enable or edit.
- ``admin:write`` still drafts proposals (it implies ``proposals:draft``) but
  never implies ``policies:draft``.
- The generalized ``/api/actions/*`` routes and the HA routes share one
  permission model: drafting is ``control.action_proposals.draft``, resolving
  is the operator-level ``control.action_proposals.write``. Machine
  principals still get 403 on resolution and a second resolution is 409.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.auth_policies import API_ROUTE_AUTHORIZATION_LOOKUP
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.platform.auth.contracts import (
    SERVICE_TOKEN_SCOPES,
    normalize_service_token_scopes,
)
from packages.platform.auth.crypto import has_required_service_token_scope
from packages.platform.auth.permission_registry import (
    PERMISSION_CONTROL_ACTION_PROPOSALS_DRAFT,
    PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE,
    PERMISSION_CONTROL_POLICY_DRAFT,
    PERMISSION_CONTROL_POLICY_WRITE,
    permissions_for_role,
    permissions_for_service_token_scopes,
)
from packages.platform.auth.scope_authorization import (
    required_permission_for_request,
    required_role_for_request,
    required_service_token_scope_for_request,
)
from packages.shared.auth import SessionManager, hash_password
from packages.storage.auth_store import LocalUserCreate, UserRole
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository

# (method, path) -> (role, permission, service-token scope)
EXPECTED_MATRIX = {
    ("GET", "/api/actions/proposals"): (UserRole.READER, "reports.read", "reports:read"),
    ("POST", "/api/actions/proposals"): (
        UserRole.OPERATOR,
        PERMISSION_CONTROL_ACTION_PROPOSALS_DRAFT,
        "proposals:draft",
    ),
    ("POST", "/api/actions/proposals/a1/approve"): (
        UserRole.OPERATOR,
        PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE,
        "admin:write",
    ),
    ("POST", "/api/actions/proposals/a1/dismiss"): (
        UserRole.OPERATOR,
        PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE,
        "admin:write",
    ),
    ("GET", "/api/ha/actions/proposals"): (UserRole.READER, "runs.read", "runs:read"),
    ("POST", "/api/ha/actions/proposals"): (
        UserRole.OPERATOR,
        PERMISSION_CONTROL_ACTION_PROPOSALS_DRAFT,
        "proposals:draft",
    ),
    ("POST", "/api/ha/actions/proposals/a1/approve"): (
        UserRole.OPERATOR,
        PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE,
        "admin:write",
    ),
    ("POST", "/control/policies"): (
        UserRole.ADMIN,
        PERMISSION_CONTROL_POLICY_DRAFT,
        "policies:draft",
    ),
    ("PATCH", "/control/policies/p1"): (
        UserRole.ADMIN,
        PERMISSION_CONTROL_POLICY_WRITE,
        "admin:write",
    ),
    ("GET", "/control/policies"): (UserRole.ADMIN, "control.policy.read", "admin:write"),
}


@pytest.mark.parametrize(("method", "path"), sorted(EXPECTED_MATRIX))
def test_route_policy_matrix(method: str, path: str) -> None:
    role, permission, scope = EXPECTED_MATRIX[(method, path)]
    lookup = API_ROUTE_AUTHORIZATION_LOOKUP
    assert required_role_for_request(lookup, path, method) == role
    assert required_permission_for_request(lookup, path, method=method) == permission
    assert required_service_token_scope_for_request(lookup, path, method) == scope


def test_draft_scopes_are_known_and_grant_only_drafting() -> None:
    assert {"proposals:draft", "policies:draft"} <= set(SERVICE_TOKEN_SCOPES)
    assert normalize_service_token_scopes(["proposals:draft", "reports:read"]) == (
        "reports:read",
        "proposals:draft",
    )
    assert permissions_for_service_token_scopes(("proposals:draft",)) == {
        PERMISSION_CONTROL_ACTION_PROPOSALS_DRAFT
    }
    assert permissions_for_service_token_scopes(("policies:draft",)) == {
        PERMISSION_CONTROL_POLICY_DRAFT
    }
    every_scope = permissions_for_service_token_scopes(tuple(SERVICE_TOKEN_SCOPES))
    # No scope lets a token edit, enable or delete a policy.
    assert PERMISSION_CONTROL_POLICY_WRITE not in every_scope


def test_scope_implications() -> None:
    assert has_required_service_token_scope(("admin:write",), "proposals:draft")
    assert not has_required_service_token_scope(("admin:write",), "policies:draft")
    assert not has_required_service_token_scope(("proposals:draft",), "admin:write")
    assert not has_required_service_token_scope(("policies:draft",), "proposals:draft")
    assert has_required_service_token_scope((), None)


def test_role_bundles_for_draft_permissions() -> None:
    assert PERMISSION_CONTROL_ACTION_PROPOSALS_DRAFT not in permissions_for_role(UserRole.READER)
    assert PERMISSION_CONTROL_ACTION_PROPOSALS_DRAFT in permissions_for_role(UserRole.OPERATOR)
    assert PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE in permissions_for_role(UserRole.OPERATOR)
    assert PERMISSION_CONTROL_POLICY_DRAFT not in permissions_for_role(UserRole.OPERATOR)
    assert PERMISSION_CONTROL_POLICY_DRAFT in permissions_for_role(UserRole.ADMIN)


_PROPOSAL = {
    "policy_id": "mcp:propose_action",
    "policy_name": "Agent drafted: lower office heating",
    "verdict": "notify",
    "value": "19.5",
}
_POLICY = {
    "display_name": "Agent: negative cashflow",
    "policy_kind": "threshold",
    "rule_document": {
        "rule_kind": "publication_value_comparison",
        "publication_key": "monthly_cashflow",
        "field_name": "net",
        "operator": "lt",
        "threshold": 0,
    },
}


class _Harness:
    def __init__(self, tmp: str) -> None:
        service = AccountTransactionService(
            landing_root=Path(tmp) / "landing",
            metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
        )
        repository = IngestionConfigRepository(Path(tmp) / "config.db")
        for user_id, username, role in (
            ("u-admin", "admin", UserRole.ADMIN),
            ("u-operator", "operator", UserRole.OPERATOR),
            ("u-reader", "reader", UserRole.READER),
        ):
            repository.create_local_user(
                LocalUserCreate(
                    user_id=user_id,
                    username=username,
                    password_hash=hash_password(f"{username}-password"),
                    role=role,
                )
            )
        self.app = create_app(
            service,
            config_repository=repository,
            auth_store=repository,
            identity_mode="local",
            session_manager=SessionManager("test-session-secret"),
            transformation_service=TransformationService(DuckDBStore.memory()),
        )
        self.admin = self.session("admin")

    def session(self, username: str) -> tuple[TestClient, dict[str, str]]:
        client = TestClient(self.app)
        login = client.post(
            "/auth/login",
            json={"username": username, "password": f"{username}-password"},
        )
        assert login.status_code == 200, login.text
        return client, {"x-csrf-token": client.cookies.get("homelab_analytics_csrf") or ""}

    def token(self, name: str, role: str, scopes: list[str]) -> tuple[TestClient, dict[str, str]]:
        client, csrf = self.admin
        created = client.post(
            "/auth/service-tokens",
            json={"token_name": name, "role": role, "scopes": scopes},
            headers=csrf,
        )
        assert created.status_code == 201, created.text
        return TestClient(self.app), {
            "authorization": f"Bearer {created.json()['token_value']}"
        }


def test_proposals_draft_token_drafts_on_both_families_but_never_resolves() -> None:
    with TemporaryDirectory() as tmp:
        harness = _Harness(tmp)
        agent, bearer = harness.token("drafter", "operator", ["reports:read", "proposals:draft"])

        drafted = agent.post("/api/actions/proposals", json=_PROPOSAL, headers=bearer)
        assert drafted.status_code == 200, drafted.text
        assert drafted.json()["created_by"] == "drafter"
        action_id = drafted.json()["action_id"]
        ha_drafted = agent.post("/api/ha/actions/proposals", json=_PROPOSAL, headers=bearer)
        assert ha_drafted.status_code == 200, ha_drafted.text
        assert agent.get("/api/actions/proposals", headers=bearer).status_code == 200

        for prefix in ("/api/actions/proposals", "/api/ha/actions/proposals"):
            for verb in ("approve", "dismiss"):
                denied = agent.post(f"{prefix}/{action_id}/{verb}", headers=bearer)
                assert denied.status_code == 403
        # Not a policy drafter, and no reach into the admin control plane.
        assert agent.post("/control/policies", json=_POLICY, headers=bearer).status_code == 403

        operator, csrf = harness.session("operator")
        approved = operator.post(
            f"/api/actions/proposals/{action_id}/approve",
            json={"reason": "checked"},
            headers=csrf,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["resolved_by"] == "operator"
        again = operator.post(f"/api/ha/actions/proposals/{action_id}/dismiss", headers=csrf)
        assert again.status_code == 409


def test_reader_role_cannot_draft_even_with_the_scope() -> None:
    with TemporaryDirectory() as tmp:
        harness = _Harness(tmp)
        agent, bearer = harness.token("reader-agent", "reader", ["proposals:draft"])
        assert agent.post("/api/actions/proposals", json=_PROPOSAL, headers=bearer).status_code == 403
        reader, csrf = harness.session("reader")
        assert reader.post("/api/actions/proposals", json=_PROPOSAL, headers=csrf).status_code == 403


def test_admin_write_token_still_drafts_and_is_still_refused_resolution() -> None:
    with TemporaryDirectory() as tmp:
        harness = _Harness(tmp)
        agent, bearer = harness.token("legacy", "admin", ["reports:read", "admin:write"])
        drafted = agent.post("/api/actions/proposals", json=_PROPOSAL, headers=bearer)
        assert drafted.status_code == 200
        denied = agent.post(
            f"/api/actions/proposals/{drafted.json()['action_id']}/approve", headers=bearer
        )
        assert denied.status_code == 403
        assert "Machine principals" in denied.json()["detail"]
        # admin:write does not imply policies:draft.
        assert agent.post("/control/policies", json=_POLICY, headers=bearer).status_code == 403


def test_policies_draft_token_creates_disabled_drafts_only() -> None:
    with TemporaryDirectory() as tmp:
        harness = _Harness(tmp)
        agent, bearer = harness.token("policy-drafter", "admin", ["policies:draft"])
        drafted = agent.post(
            "/control/policies", json=_POLICY, headers=bearer
        )
        assert drafted.status_code == 201, drafted.text
        policy = drafted.json()
        assert policy["enabled"] is False
        assert policy["source_kind"] == "agent"
        assert policy["creator"] == "policy-drafter"

        policy_path = f"/control/policies/{policy['policy_id']}"
        assert agent.patch(policy_path, json={"enabled": True}, headers=bearer).status_code == 403
        assert agent.patch(policy_path, json={"display_name": "x"}, headers=bearer).status_code == 403
        assert agent.delete(policy_path, headers=bearer).status_code in {403, 405}
        assert agent.get("/control/policies", headers=bearer).status_code == 403
        # Not a proposal drafter either.
        assert agent.post("/api/actions/proposals", json=_PROPOSAL, headers=bearer).status_code == 403

        # An operator-role token cannot hold the policy draft permission.
        weak, weak_bearer = harness.token("weak", "operator", ["policies:draft"])
        assert weak.post("/control/policies", json=_POLICY, headers=weak_bearer).status_code == 403

        admin, csrf = harness.admin
        enabled = admin.patch(policy_path, json={"enabled": True}, headers=csrf)
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is True
