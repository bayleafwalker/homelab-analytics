from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.platform.auth.machine_jwt_provider import build_machine_jwt_provider
from packages.shared.auth import SessionManager, issue_service_token
from packages.shared.metrics import metrics_registry
from packages.shared.settings import AppSettings
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    ServiceTokenCreate,
    UserRole,
)
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.oidc_test_support import MockOidcIssuer


def _build_machine_jwt_client(
    temp_dir: str,
    issuer: MockOidcIssuer,
) -> tuple[TestClient, IngestionConfigRepository]:
    settings = AppSettings.from_env(
        {
            "HOMELAB_ANALYTICS_DATA_DIR": temp_dir,
            "HOMELAB_ANALYTICS_IDENTITY_MODE": "local",
            "HOMELAB_ANALYTICS_SESSION_SECRET": "test-session-secret",
            "HOMELAB_ANALYTICS_MACHINE_JWT_ENABLED": "true",
            "HOMELAB_ANALYTICS_MACHINE_JWT_ISSUER_URL": issuer.issuer_url,
            "HOMELAB_ANALYTICS_MACHINE_JWT_AUDIENCE": "homelab-machine",
            "HOMELAB_ANALYTICS_MACHINE_JWT_ROLE_CLAIM": "role",
            "HOMELAB_ANALYTICS_MACHINE_JWT_SCOPES_CLAIM": "scope",
            "HOMELAB_ANALYTICS_MACHINE_JWT_USERNAME_CLAIM": "sub",
        }
    )
    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
    client = TestClient(
        create_app(
            service,
            config_repository=repository,
            auth_store=repository,
            identity_mode="local",
            session_manager=SessionManager("test-session-secret"),
            machine_jwt_provider=build_machine_jwt_provider(
                settings,
                http_client=issuer.http_client(),
            ),
        )
    )
    return client, repository


def test_machine_jwt_bearer_auth_builds_machine_principal() -> None:
    metrics_registry.clear()
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_machine_jwt_client(temp_dir, issuer)
        machine_token = issuer.issue_token(
            subject="machine-client-001",
            username="machine-client-001",
            audience="homelab-machine",
            extra_claims={
                "role": "operator",
                "scope": "reports:read runs:read ingest:write",
            },
        )

        me = client.get(
            "/auth/me",
            headers={"authorization": f"Bearer {machine_token}"},
        )

        assert me.status_code == 200
        payload = me.json()
        assert payload["principal"]["auth_provider"] == "machine_jwt"
        assert payload["user"]["auth_provider"] == "machine_jwt"
        assert "runs:read" in payload["principal"]["scopes"]
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "auth_machine_jwt_authenticated_requests_total 1" in metrics.text


def test_machine_jwt_invalid_bearer_increments_failure_metric() -> None:
    metrics_registry.clear()
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_machine_jwt_client(temp_dir, issuer)

        denied = client.get(
            "/runs",
            headers={"authorization": "Bearer invalid-machine-jwt"},
        )

        assert denied.status_code == 401
        assert denied.json()["detail"] == "Invalid bearer token."
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "auth_machine_jwt_failed_requests_total 1" in metrics.text


def test_machine_jwt_and_service_token_have_parity_for_equivalent_grants() -> None:
    metrics_registry.clear()
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client, repository = _build_machine_jwt_client(temp_dir, issuer)
        issued = issue_service_token("token-machine-parity-001")
        repository.create_service_token(
            ServiceTokenCreate(
                token_id=issued.token_id,
                token_name="parity-service-token",
                token_secret_hash=issued.token_secret_hash,
                role=UserRole.OPERATOR,
                scopes=(
                    SERVICE_TOKEN_SCOPE_REPORTS_READ,
                    SERVICE_TOKEN_SCOPE_RUNS_READ,
                    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
                ),
            )
        )
        machine_token = issuer.issue_token(
            subject="machine-parity-001",
            username="machine-parity-001",
            audience="homelab-machine",
            extra_claims={
                "role": "operator",
                "scope": "reports:read runs:read ingest:write",
            },
        )

        service_headers = {"authorization": f"Bearer {issued.token_value}"}
        machine_headers = {"authorization": f"Bearer {machine_token}"}

        service_runs = client.get("/runs", headers=service_headers)
        machine_runs = client.get("/runs", headers=machine_headers)
        assert service_runs.status_code == machine_runs.status_code == 200

        service_retry = client.post(
            "/runs/non-existent-parity-run/retry",
            headers=service_headers,
        )
        machine_retry = client.post(
            "/runs/non-existent-parity-run/retry",
            headers=machine_headers,
        )
        assert service_retry.status_code == machine_retry.status_code == 404

        service_admin = client.get("/config/source-systems", headers=service_headers)
        machine_admin = client.get("/config/source-systems", headers=machine_headers)
        assert service_admin.status_code == machine_admin.status_code == 403
