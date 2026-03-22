from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.auth import (
    build_oidc_provider,
    build_session_manager,
    issue_service_token,
)
from packages.shared.settings import AppSettings
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    ServiceTokenCreate,
    UserRole,
)
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
    permissions_claim: str | None = None,
    permission_group_mappings: tuple[str, ...] = (),
) -> AppSettings:
    env = {
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
    if permissions_claim:
        env["HOMELAB_ANALYTICS_OIDC_PERMISSIONS_CLAIM"] = permissions_claim
    if permission_group_mappings:
        env["HOMELAB_ANALYTICS_OIDC_PERMISSION_GROUP_MAPPINGS"] = ";".join(
            permission_group_mappings
        )
    return AppSettings.from_env(env)


def _build_oidc_client(
    temp_dir: str,
    issuer: MockOidcIssuer,
    *,
    reader_groups: tuple[str, ...] = (),
    operator_groups: tuple[str, ...] = (),
    admin_groups: tuple[str, ...] = (),
    permissions_claim: str | None = None,
    permission_group_mappings: tuple[str, ...] = (),
) -> TestClient:
    settings = _oidc_settings(
        temp_dir,
        issuer,
        reader_groups=reader_groups,
        operator_groups=operator_groups,
        admin_groups=admin_groups,
        permissions_claim=permissions_claim,
        permission_group_mappings=permission_group_mappings,
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


def test_api_oidc_login_callback_preserves_permission_claims_in_session() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client = _build_oidc_client(
            temp_dir,
            issuer,
            reader_groups=("readers",),
            permissions_claim="hla_permissions",
        )

        start = client.get("/auth/login?return_to=/reports", follow_redirects=False)
        assert start.status_code == 303
        redirect = urlparse(start.headers["location"])
        query = parse_qs(redirect.query)
        nonce = query["nonce"][0]
        state = query["state"][0]
        issuer.register_code(
            "oidc-permissions-callback-code",
            subject="user-oidc-permissions",
            username="reader-plus@example.test",
            nonce=nonce,
            groups=("readers",),
            extra_claims={"hla_permissions": ["ingest.write"]},
        )

        callback = client.get(
            f"/auth/callback?code=oidc-permissions-callback-code&state={state}",
            follow_redirects=False,
        )
        assert callback.status_code == 303

        me = client.get("/auth/me")
        assert me.status_code == 200
        assert "ingest.write" in me.json()["user"]["permissions"]


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


def test_api_oidc_accepts_service_tokens_before_oidc_jwt_validation() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        settings = _oidc_settings(temp_dir, issuer, admin_groups=("admins",))
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        issued_token = issue_service_token("token-oidc-001")
        repository.create_service_token(
            ServiceTokenCreate(
                token_id=issued_token.token_id,
                token_name="automation-reader",
                token_secret_hash=issued_token.token_secret_hash,
                role=UserRole.READER,
                scopes=(SERVICE_TOKEN_SCOPE_RUNS_READ,),
            )
        )
        client = TestClient(
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

        response = client.get(
            "/runs",
            headers={"authorization": f"Bearer {issued_token.token_value}"},
        )

        assert response.status_code == 200


def test_api_oidc_permission_claim_grants_ingest_without_operator_group() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client = _build_oidc_client(
            temp_dir,
            issuer,
            reader_groups=("readers",),
            permissions_claim="hla_permissions",
        )
        token = issuer.issue_token(
            subject="reader-plus-ingest",
            username="reader-plus@example.test",
            audience=issuer.api_audience,
            groups=("readers",),
            extra_claims={"hla_permissions": ["ingest.write"]},
        )

        response = client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "claim-granted-ingest",
            },
            headers={"authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        me = client.get(
            "/auth/me",
            headers={"authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200
        assert "ingest.write" in me.json()["user"]["permissions"]


def test_api_oidc_unknown_permission_claim_values_are_ignored() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client = _build_oidc_client(
            temp_dir,
            issuer,
            reader_groups=("readers",),
            permissions_claim="hla_permissions",
        )
        token = issuer.issue_token(
            subject="reader-unknown-claim",
            username="reader-unknown@example.test",
            audience=issuer.api_audience,
            groups=("readers",),
            extra_claims={"hla_permissions": ["unknown.permission"]},
        )

        response = client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "unknown-claim-ingest",
            },
            headers={"authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403


def test_api_oidc_permission_bound_principal_enforces_publication_permissions() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client = _build_oidc_client(
            temp_dir,
            issuer,
            reader_groups=("readers",),
            permissions_claim="hla_permissions",
        )
        token = issuer.issue_token(
            subject="permission-only-reader",
            username="permission-only@example.test",
            audience=issuer.api_audience,
            groups=(),
            extra_claims={
                "hla_permissions": ["reports.read.publication.finance-only"],
            },
        )
        headers = {"authorization": f"Bearer {token}"}

        allowed = client.get("/reports/finance-only", headers=headers)
        assert allowed.status_code == 400

        denied_report = client.get("/reports/budget-variance", headers=headers)
        assert denied_report.status_code == 403
        assert denied_report.json()["detail"] == "reports.read.publication.budget-variance permission required."

        denied_runs = client.get("/runs", headers=headers)
        assert denied_runs.status_code == 403
        assert denied_runs.json()["detail"] == "runs.read permission required."


def test_api_oidc_group_to_permission_mapping_grants_ingest() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        client = _build_oidc_client(
            temp_dir,
            issuer,
            reader_groups=("readers",),
            permission_group_mappings=("automation-operators=ingest.write,runs.retry",),
        )
        token = issuer.issue_token(
            subject="group-granted-ingest",
            username="group-granted@example.test",
            audience=issuer.api_audience,
            groups=("automation-operators",),
        )

        response = client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "group-granted-ingest",
            },
            headers={"authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201


def test_oidc_invalid_permission_group_mapping_is_rejected() -> None:
    issuer = MockOidcIssuer()
    with TemporaryDirectory() as temp_dir:
        settings = _oidc_settings(
            temp_dir,
            issuer,
            permission_group_mappings=("broken-entry-without-equals",),
        )
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

        try:
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
        except ValueError as exc:
            assert "permission-group mappings" in str(exc)
        else:
            raise AssertionError("Expected invalid permission-group mapping to raise ValueError.")
