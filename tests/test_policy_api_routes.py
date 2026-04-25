"""Tests for /control/policies CRUD routes and control.policy.read/write permissions."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.platform.auth.contracts import UserRole
from packages.platform.auth.permission_registry import (
    PERMISSION_CONTROL_POLICY_READ,
    PERMISSION_CONTROL_POLICY_WRITE,
    KNOWN_PERMISSIONS,
    permissions_for_role,
)
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


def _build_client(temp_dir: str) -> TestClient:
    temp_root = Path(temp_dir)
    service = AccountTransactionService(
        landing_root=temp_root / "landing",
        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
    )
    config_repository = IngestionConfigRepository(temp_root / "config.db")
    app = create_app(service, config_repository=config_repository, enable_unsafe_admin=True)
    return TestClient(app)


_VALID_RULE = {
    "rule_kind": "publication_value_comparison",
    "publication_key": "monthly_cashflow",
    "field_name": "net",
    "operator": "lt",
    "threshold": 0,
    "unit": "currency",
}


class PolicyPermissionTests(unittest.TestCase):
    def test_policy_permissions_in_known_permissions(self) -> None:
        assert PERMISSION_CONTROL_POLICY_READ in KNOWN_PERMISSIONS
        assert PERMISSION_CONTROL_POLICY_WRITE in KNOWN_PERMISSIONS

    def test_admin_has_policy_read_and_write(self) -> None:
        admin_perms = permissions_for_role(UserRole.ADMIN)
        assert PERMISSION_CONTROL_POLICY_READ in admin_perms
        assert PERMISSION_CONTROL_POLICY_WRITE in admin_perms

    def test_reader_does_not_have_policy_permissions(self) -> None:
        reader_perms = permissions_for_role(UserRole.READER)
        assert PERMISSION_CONTROL_POLICY_READ not in reader_perms
        assert PERMISSION_CONTROL_POLICY_WRITE not in reader_perms

    def test_operator_does_not_have_policy_permissions(self) -> None:
        operator_perms = permissions_for_role(UserRole.OPERATOR)
        assert PERMISSION_CONTROL_POLICY_READ not in operator_perms
        assert PERMISSION_CONTROL_POLICY_WRITE not in operator_perms


class PolicyCrudRouteTests(unittest.TestCase):
    def test_list_policies_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.get("/control/policies")
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json()["policies"])

    def test_create_policy_returns_201(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.post(
                "/control/policies",
                json={
                    "display_name": "Net cashflow alert",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                    "creator": "test-user",
                },
            )
        self.assertEqual(201, response.status_code)
        data = response.json()
        self.assertEqual("Net cashflow alert", data["display_name"])
        self.assertEqual("operator", data["source_kind"])
        self.assertEqual(True, data["enabled"])
        self.assertIn("policy_id", data)
        self.assertEqual(_VALID_RULE["rule_kind"], data["rule_document"]["rule_kind"])

    def test_create_policy_rejects_unknown_rule_kind(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.post(
                "/control/policies",
                json={
                    "display_name": "Evil policy",
                    "policy_kind": "exec",
                    "rule_document": {"rule_kind": "exec_python", "code": "os.system('whoami')"},
                },
            )
        self.assertEqual(422, response.status_code)

    def test_create_policy_rejects_extra_rule_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            bad_rule = dict(_VALID_RULE, injected="malicious")
            response = client.post(
                "/control/policies",
                json={
                    "display_name": "Bad policy",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": bad_rule,
                },
            )
        self.assertEqual(422, response.status_code)

    def test_get_policy(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "My policy",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            get_resp = client.get(f"/control/policies/{policy_id}")
        self.assertEqual(200, get_resp.status_code)
        self.assertEqual(policy_id, get_resp.json()["policy_id"])

    def test_get_policy_not_found(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.get("/control/policies/nonexistent-id")
        self.assertEqual(404, response.status_code)

    def test_list_policies_after_create(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            client.post(
                "/control/policies",
                json={
                    "display_name": "P1",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            client.post(
                "/control/policies",
                json={
                    "display_name": "P2",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            response = client.get("/control/policies")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json()["policies"]))

    def test_update_policy_enabled_state(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "Disable me",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            patch_resp = client.patch(
                f"/control/policies/{policy_id}",
                json={"enabled": False},
            )
        self.assertEqual(200, patch_resp.status_code)
        self.assertFalse(patch_resp.json()["enabled"])

    def test_update_policy_rule_document_validated(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "My policy",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            patch_resp = client.patch(
                f"/control/policies/{policy_id}",
                json={"rule_document": {"rule_kind": "exec_python", "code": "bad"}},
            )
        self.assertEqual(422, patch_resp.status_code)

    def test_update_policy_not_found(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.patch(
                "/control/policies/ghost",
                json={"display_name": "New name"},
            )
        self.assertEqual(404, response.status_code)

    def test_delete_policy(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "Delete me",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            del_resp = client.delete(f"/control/policies/{policy_id}")
            self.assertEqual(204, del_resp.status_code)
            get_resp = client.get(f"/control/policies/{policy_id}")
        self.assertEqual(404, get_resp.status_code)

    def test_delete_policy_not_found(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            response = client.delete("/control/policies/ghost")
        self.assertEqual(404, response.status_code)

    def test_list_policies_enabled_only_filter(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            create_resp = client.post(
                "/control/policies",
                json={
                    "display_name": "Active",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            policy_id = create_resp.json()["policy_id"]
            client.patch(f"/control/policies/{policy_id}", json={"enabled": False})
            client.post(
                "/control/policies",
                json={
                    "display_name": "Also Active",
                    "policy_kind": "publication_value_comparison",
                    "rule_document": _VALID_RULE,
                },
            )
            response = client.get("/control/policies?enabled_only=true")
        self.assertEqual(200, response.status_code)
        results = response.json()["policies"]
        self.assertEqual(1, len(results))
        self.assertEqual("Also Active", results[0]["display_name"])
