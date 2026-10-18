"""Vuoro-aligned agent capability manifest: projection, gating, honesty."""
from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.agent.mcp_server import MCP_PROTOCOL_VERSION, SERVER_NAME, SERVER_VERSION
from apps.api.app import _agent_capability_manifest, create_app
from apps.api.routes.agent_routes import register_agent_routes
from packages.application.use_cases.agent_capability_manifest import (
    AGENT_CAPABILITY_MANIFEST_SCHEMA_VERSION,
    build_agent_capability_manifest,
    catalog_revision,
)
from packages.application.use_cases.agent_tool_catalog import (
    AGENT_TOOL_SPECS,
    VUORO_OPERATION_NAME_PATTERN,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

# vuoro-cloud RepositoryCreate.repo_id pattern.
VUORO_REPO_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,127}$")
VUORO_AUTHORITY = re.compile(r"^[a-z][a-z0-9-]*:[a-z][a-z0-9-]*$")


def _manifest(uuid: str | None = None) -> dict:
    return build_agent_capability_manifest(
        repo_id="homelab-analytics",
        authority_repo_uuid=uuid,
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        mcp_protocol_version=MCP_PROTOCOL_VERSION,
    )


def test_manifest_projects_every_catalog_tool_with_vuoro_conventions() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == AGENT_CAPABILITY_MANIFEST_SCHEMA_VERSION
    assert re.fullmatch(r"[a-z-]+/v\d+", manifest["schema_version"])
    assert VUORO_REPO_ID.match(manifest["repo_id"])
    operations = manifest["operations"]
    assert [op["mcp_tool"] for op in operations] == [spec.name for spec in AGENT_TOOL_SPECS]
    for operation in operations:
        assert VUORO_OPERATION_NAME_PATTERN.match(operation["name"])
        assert VUORO_AUTHORITY.match(operation["required_authority"])
        assert operation["execution_semantics"] in {"read", "write", "enqueue", "admin"}
        assert operation["idempotency"] in {"not-allowed", "optional", "required"}
        assert "json-schema-draft-2020-12" in operation["required_client_schema_features"]
        assert operation["input_schema"]["additionalProperties"] is False
        assert operation["approval_gated"] is (operation["required_authority"] == "hla:propose")
    assert len(manifest["catalog_revision"]) == 64
    assert manifest["catalog_revision"] == catalog_revision(operations)
    assert manifest["approval"]["vuoro_effect_state_map"] == {
        "pending": "proposed",
        "approved": "accepted",
        "dismissed": "rejected",
    }
    assert manifest["approval"]["resolution"] == "human-only"
    assert manifest["approval"]["changes_path"] == "/api/actions/proposals/changes"
    assert manifest["approval"]["changes_schema"] == "resource-changes/v1"


def test_manifest_never_claims_an_issued_identity() -> None:
    assert _manifest()["authority"]["status"] == "unassigned"
    minted = _manifest("11318b7d-69cb-4b26-9dfa-1be33d1ea39c")["authority"]
    assert minted["status"] == "self-asserted"
    assert minted["issuer"] is None


def test_manifest_is_off_by_default_and_served_when_enabled() -> None:
    with TemporaryDirectory() as tmp:
        service = AccountTransactionService(
            landing_root=Path(tmp) / "landing",
            metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
        )
        client = TestClient(
            create_app(service, transformation_service=TransformationService(DuckDBStore.memory()))
        )
        disabled = client.get("/api/agent/manifest")
        assert disabled.status_code == 404
        assert "HOMELAB_ANALYTICS_AGENT_MANIFEST_ENABLED" in disabled.json()["detail"]

    app = FastAPI()
    register_agent_routes(
        app,
        capability_packs=(),
        extension_registry=None,  # type: ignore[arg-type]
        publication_semantic_index=[],
        capability_manifest=_manifest(),
    )
    served = TestClient(app).get("/api/agent/manifest")
    assert served.status_code == 200
    assert served.json()["catalog_revision"] == _manifest()["catalog_revision"]


def test_settings_gate_the_manifest() -> None:
    assert AppSettings.from_env({}).agent_manifest_enabled is False
    assert _agent_capability_manifest(AppSettings.from_env({})) is None
    settings = AppSettings.from_env(
        {
            "HOMELAB_ANALYTICS_AGENT_MANIFEST_ENABLED": "true",
            "HOMELAB_ANALYTICS_AGENT_MANIFEST_REPO_ID": "hla-test",
            "HOMELAB_ANALYTICS_AGENT_AUTHORITY_REPO_UUID": "11318b7d-69cb-4b26-9dfa-1be33d1ea39c",
        }
    )
    manifest = _agent_capability_manifest(settings)
    assert manifest is not None
    assert manifest["repo_id"] == "hla-test"
    assert manifest["authority"]["status"] == "self-asserted"
