from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.auth import build_oidc_provider, build_session_manager
from packages.shared.settings import AppSettings
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.oidc_test_support import MockOidcIssuer


def _oidc_settings(
    temp_dir: str,
    issuer: MockOidcIssuer,
    *,
    reader_groups: tuple[str, ...] = (),
    operator_groups: tuple[str, ...] = (),
    admin_groups: tuple[str, ...] = (),
) -> AppSettings:
    return AppSettings.from_env(
        {
            "HOMELAB_ANALYTICS_DATA_DIR": temp_dir,
            "HOMELAB_ANALYTICS_AUTH_MODE": "oidc",
            "HOMELAB_ANALYTICS_SESSION_SECRET": "test-session-secret",
            "HOMELAB_ANALYTICS_OIDC_ISSUER_URL": issuer.issuer_url,
            "HOMELAB_ANALYTICS_OIDC_CLIENT_ID": issuer.client_id,
            "HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET": issuer.client_secret,
            "HOMELAB_ANALYTICS_OIDC_REDIRECT_URI": "http://testserver/auth/callback",
            "HOMELAB_ANALYTICS_OIDC_API_AUDIENCE": issuer.api_audience,
            "HOMELAB_ANALYTICS_OIDC_READER_GROUPS": ",".join(reader_groups),
            "HOMELAB_ANALYTICS_OIDC_OPERATOR_GROUPS": ",".join(operator_groups),
            "HOMELAB_ANALYTICS_OIDC_ADMIN_GROUPS": ",".join(admin_groups),
        }
    )


def _build_oidc_client(
    temp_dir: str,
    issuer: MockOidcIssuer,
    *,
    reader_groups: tuple[str, ...] = (),
    operator_groups: tuple[str, ...] = (),
    admin_groups: tuple[str, ...] = (),
) -> TestClient:
    settings = _oidc_settings(
        temp_dir,
        issuer,
        reader_groups=reader_groups,
        operator_groups=operator_groups,
        admin_groups=admin_groups,
    )
    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
    return TestClient(
        create_app(
            service,
            config_repository=repository,
            auth_store=repository,
            auth_mode="oidc",
            session_manager=build_session_manager(settings),
            oidc_provider=build_oidc_provider(
                settings,
                http_client=issuer.http_client(),
            ),
        )
    )


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("homelab_analytics_csrf")
    assert token
    return {"x-csrf-token": token}


def test_api_oidc_login_callback_and_me() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client = _build_oidc_client(
            temp_dir,
            issuer,
            admin_groups=("admins",),
        )

        assert client.get("/runs").status_code == 401

        start = client.get("/auth/login?return_to=/reports", follow_redirects=False)
        assert start.status_code == 303
        redirect = urlparse(start.headers["location"])
        assert redirect.geturl().startswith(issuer.authorization_endpoint)
        query = parse_qs(redirect.query)
        nonce = query["nonce"][0]
        state = query["state"][0]
        issuer.register_code(
            "oidc-callback-code",
            subject="user-oidc-1",
            username="alice@example.test",
            nonce=nonce,
            groups=("admins",),
        )

        callback = client.get(
            f"/auth/callback?code=oidc-callback-code&state={state}",
            follow_redirects=False,
        )
        assert callback.status_code == 303
        assert callback.headers["location"] == "/reports"
        assert client.cookies.get("homelab_analytics_session")
        assert client.cookies.get("homelab_analytics_csrf")
        assert client.cookies.get("homelab_analytics_oidc_state") is None

        me = client.get("/auth/me")
        assert me.status_code == 200
        payload = me.json()
        assert payload["auth_mode"] == "oidc"
        assert payload["user"]["username"] == "alice@example.test"
        assert payload["user"]["role"] == "admin"
        assert payload["user"]["auth_provider"] == "oidc"
        assert payload["principal"]["auth_provider"] == "oidc"

        logout = client.post("/auth/logout", headers=_csrf_headers(client))
        assert logout.status_code == 200
        assert client.get("/auth/me").status_code == 401


def test_api_oidc_bearer_tokens_enforce_reader_operator_and_admin_roles() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client = _build_oidc_client(
            temp_dir,
            issuer,
            reader_groups=("readers",),
            operator_groups=("operators",),
            admin_groups=("admins",),
        )

        reader_token = issuer.issue_token(
            subject="reader-1",
            username="reader@example.test",
            audience=issuer.api_audience,
            groups=("readers",),
        )
        operator_token = issuer.issue_token(
            subject="operator-1",
            username="operator@example.test",
            audience=issuer.api_audience,
            groups=("operators",),
        )
        admin_token = issuer.issue_token(
            subject="admin-1",
            username="admin@example.test",
            audience=issuer.api_audience,
            groups=("admins",),
        )

        assert (
            client.get(
                "/runs",
                headers={"authorization": f"Bearer {reader_token}"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "bearer-reader-upload",
                },
                headers={"authorization": f"Bearer {reader_token}"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "bearer-operator-upload",
                },
                headers={"authorization": f"Bearer {operator_token}"},
            ).status_code
            == 201
        )
        assert (
            client.get(
                "/config/source-systems",
                headers={"authorization": f"Bearer {operator_token}"},
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/config/source-systems",
                headers={"authorization": f"Bearer {admin_token}"},
            ).status_code
            == 200
        )


def test_api_oidc_rejects_valid_bearer_token_without_role_mapping() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client = _build_oidc_client(
            temp_dir,
            issuer,
            reader_groups=("readers",),
        )
        token = issuer.issue_token(
            subject="unknown-1",
            username="unknown@example.test",
            audience=issuer.api_audience,
            groups=("mystery",),
        )

        response = client.get(
            "/runs",
            headers={"authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "not mapped" in response.json()["detail"]
