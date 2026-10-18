"""Pack lifecycle API: admin-only policies, catalog, dry-run, actions, history."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.auth_policies import API_ROUTE_AUTHORIZATION_LOOKUP
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.platform.auth.contracts import SERVICE_TOKEN_SCOPE_ADMIN_WRITE, UserRole
from packages.platform.auth.permission_registry import PERMISSION_ADMIN_WRITE
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.pack_lifecycle_test_support import pack_entry, write_registry_revision


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/control/packs"),
        ("GET", "/control/packs/history"),
        ("POST", "/control/packs/energy/plan"),
        ("POST", "/control/packs/energy/actions"),
    ],
)
def test_pack_routes_are_admin_only(method: str, path: str) -> None:
    lookup = API_ROUTE_AUTHORIZATION_LOOKUP
    assert lookup.required_role_for_request(path, method=method) == UserRole.ADMIN
    assert lookup.required_permission_for_request(path, method=method) == PERMISSION_ADMIN_WRITE
    assert (
        lookup.required_service_token_scope_for_request(path, method)
        == SERVICE_TOKEN_SCOPE_ADMIN_WRITE
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    repository = IngestionConfigRepository(tmp_path / "config.db")
    write_registry_revision(
        repository,
        tmp_path / "registry",
        source_id="acme",
        revision_id="rev-1",
        packs=[
            pack_entry("energy", "1.0.0", publications={"energy_tariffs": "1.0.0"}),
            pack_entry("energy", "1.1.0", publications={"energy_tariffs": "1.1.0"}),
            pack_entry("solar", "1.0.0", requires_platform_version=">=99.0"),
        ],
    )
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    return TestClient(create_app(service, config_repository=repository))


def test_catalog_lists_cached_packs_with_compatibility_badges(client: TestClient) -> None:
    response = client.get("/control/packs")
    assert response.status_code == 200, response.text
    payload = response.json()
    packs = {pack["pack_key"]: pack for pack in payload["packs"]}
    assert packs["energy"]["state"] == "not_installed"
    assert packs["energy"]["latest_version"] == "1.1.0"
    assert [row["version"] for row in packs["energy"]["versions"]] == ["1.1.0", "1.0.0"]
    assert packs["solar"]["versions"][0]["compatibility_status"] == "incompatible"
    assert payload["registry"]["sources_scanned"] == 1
    assert payload["platform_packs"], "built-in capability packs are listed"


def test_plan_is_a_dry_run(client: TestClient) -> None:
    response = client.post("/control/packs/energy/plan", json={"action": "install"})
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["allowed"] is True
    assert plan["to_version"] == "1.1.0"
    assert plan["contracts_affected"] == ["energy_tariffs@1.1.0"]
    assert client.get("/control/packs/history").json() == {"events": []}


def test_actions_apply_refuse_and_record_history(client: TestClient) -> None:
    missing_reason = client.post(
        "/control/packs/energy/actions", json={"action": "install", "version": "1.0.0"}
    )
    assert missing_reason.status_code == 422

    installed = client.post(
        "/control/packs/energy/actions",
        json={"action": "install", "version": "1.0.0", "reason": "household tariffs"},
    )
    assert installed.status_code == 200, installed.text
    assert installed.json()["installation"]["installed_version"] == "1.0.0"

    upgraded = client.post(
        "/control/packs/energy/actions",
        json={"action": "upgrade", "reason": "new tariff schema"},
    )
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["plan"]["publication_changes"][0]["change"] == "schema_changed"

    rolled_back = client.post(
        "/control/packs/energy/actions",
        json={"action": "rollback", "reason": "1.1.0 misreads night tariffs"},
    )
    assert rolled_back.status_code == 200, rolled_back.text
    assert rolled_back.json()["installation"]["previous_version"] == "1.1.0"

    refused = client.post(
        "/control/packs/solar/actions",
        json={"action": "install", "reason": "try it"},
    )
    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail["plan"]["allowed"] is False
    assert detail["plan"]["diagnostics"][0]["code"] == "compatibility"

    unknown_action = client.post(
        "/control/packs/energy/actions", json={"action": "uninstall", "reason": "x"}
    )
    assert unknown_action.status_code == 422

    history = client.get("/control/packs/history").json()["events"]
    assert [(e["pack_key"], e["action"], e["outcome"]) for e in history] == [
        ("solar", "install", "refused"),
        ("energy", "rollback", "applied"),
        ("energy", "upgrade", "applied"),
        ("energy", "install", "applied"),
    ]
    assert history[1]["reason"] == "1.1.0 misreads night tariffs"
    energy_only = client.get("/control/packs/history", params={"pack_key": "energy"})
    assert len(energy_only.json()["events"]) == 3

    catalog = {p["pack_key"]: p for p in client.get("/control/packs").json()["packs"]}
    assert catalog["energy"]["state"] == "enabled"
    assert catalog["energy"]["upgrade_available"] is True
