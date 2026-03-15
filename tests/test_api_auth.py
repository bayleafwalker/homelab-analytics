from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.auth import SessionManager, hash_password
from packages.storage.auth_store import LocalUserCreate, UserRole
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import seed_source_asset_graph


def _build_client(
    temp_dir: str,
    *,
    users: tuple[tuple[str, str, UserRole], ...],
) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
    for index, (username, password, role) in enumerate(users, start=1):
        repository.create_local_user(
            LocalUserCreate(
                user_id=f"user-{index}",
                username=username,
                password_hash=hash_password(password),
                role=role,
            )
        )
    return TestClient(
        create_app(
            service,
            config_repository=repository,
            auth_store=repository,
            auth_mode="local",
            session_manager=SessionManager("test-session-secret"),
        )
    )


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("homelab_analytics_csrf")
    assert token
    return {"x-csrf-token": token}


def test_api_local_auth_login_logout_and_me() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("reader", "reader-password", UserRole.READER),),
        )

        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 200
        assert client.get("/runs").status_code == 401

        invalid_login = client.post(
            "/auth/login",
            json={"username": "reader", "password": "wrong-password"},
        )
        assert invalid_login.status_code == 401

        login = client.post(
            "/auth/login",
            json={"username": "reader", "password": "reader-password"},
        )
        assert login.status_code == 200
        assert "homelab_analytics_session" in login.headers["set-cookie"]
        assert client.cookies.get("homelab_analytics_csrf")

        me = client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["username"] == "reader"
        assert me.json()["principal"]["role"] == "reader"

        logout = client.post("/auth/logout", headers=_csrf_headers(client))
        assert logout.status_code == 200
        assert client.get("/auth/me").status_code == 401


def test_api_local_auth_enforces_reader_operator_and_admin_roles() -> None:
    with TemporaryDirectory() as temp_dir:
        reader_client = _build_client(
            temp_dir,
            users=(
                ("reader", "reader-password", UserRole.READER),
                ("operator", "operator-password", UserRole.OPERATOR),
                ("admin", "admin-password", UserRole.ADMIN),
            ),
        )

        assert (
            reader_client.post(
                "/auth/login",
                json={"username": "reader", "password": "reader-password"},
            ).status_code
            == 200
        )
        assert reader_client.get("/runs").status_code == 200
        assert (
            reader_client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
                headers=_csrf_headers(reader_client),
            ).status_code
            == 403
        )
        assert reader_client.get("/config/source-systems").status_code == 403

    with TemporaryDirectory() as temp_dir:
        operator_client = _build_client(
            temp_dir,
            users=(("operator", "operator-password", UserRole.OPERATOR),),
        )

        assert (
            operator_client.post(
                "/auth/login",
                json={"username": "operator", "password": "operator-password"},
            ).status_code
            == 200
        )
        ingest = operator_client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "manual-upload",
            },
            headers=_csrf_headers(operator_client),
        )
        assert ingest.status_code == 201
        assert operator_client.get("/config/source-systems").status_code == 403

    with TemporaryDirectory() as temp_dir:
        admin_client = _build_client(
            temp_dir,
            users=(("admin", "admin-password", UserRole.ADMIN),),
        )

        assert (
            admin_client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
            ).status_code
            == 200
        )
        config_response = admin_client.get("/config/source-systems")
        assert config_response.status_code == 200
        assert config_response.json()["source_systems"] == []


def test_api_local_auth_rejects_state_changing_requests_without_csrf_token() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("operator", "operator-password", UserRole.OPERATOR),),
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "operator", "password": "operator-password"},
            ).status_code
            == 200
        )
        ingest = client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "manual-upload",
            },
        )
        assert ingest.status_code == 403
        assert ingest.json()["detail"] == "CSRF validation failed."


def test_api_local_auth_supports_admin_user_management_and_audit() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("admin", "admin-password", UserRole.ADMIN),),
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
            ).status_code
            == 200
        )
        headers = _csrf_headers(client)

        created = client.post(
            "/auth/users",
            json={
                "username": "reader-two",
                "password": "reader-password",
                "role": "reader",
            },
            headers=headers,
        )
        assert created.status_code == 201
        created_user = created.json()["user"]
        assert created_user["username"] == "reader-two"
        assert created_user["role"] == "reader"

        updated = client.patch(
            f"/auth/users/{created_user['user_id']}",
            json={"role": "operator", "enabled": False},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["user"]["role"] == "operator"
        assert updated.json()["user"]["enabled"] is False

        reset = client.post(
            f"/auth/users/{created_user['user_id']}/password",
            json={"password": "rotated-password"},
            headers=headers,
        )
        assert reset.status_code == 200

        users_response = client.get("/auth/users")
        assert users_response.status_code == 200
        assert any(
            user["username"] == "reader-two" and user["enabled"] is False
            for user in users_response.json()["users"]
        )

        audit_response = client.get("/control/auth-audit?limit=10")
        assert audit_response.status_code == 200
        event_types = [
            event["event_type"] for event in audit_response.json()["auth_audit_events"]
        ]
        assert "password_reset" in event_types
        assert "user_updated" in event_types
        assert "user_created" in event_types


def test_api_local_auth_locks_out_repeated_failed_logins() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("reader", "reader-password", UserRole.READER),),
        )

        for _ in range(5):
            failed = client.post(
                "/auth/login",
                json={"username": "reader", "password": "wrong-password"},
            )
            assert failed.status_code == 401

        locked = client.post(
            "/auth/login",
            json={"username": "reader", "password": "reader-password"},
        )
        assert locked.status_code == 429
        assert locked.json()["detail"] == "Too many failed login attempts. Try again later."


def test_api_local_auth_allows_reader_run_lineage_and_publication_visibility() -> None:
    with TemporaryDirectory() as temp_dir:
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seed_source_asset_graph(repository)
        repository.create_local_user(
            LocalUserCreate(
                user_id="user-reader",
                username="reader",
                password_hash=hash_password("reader-password"),
                role=UserRole.READER,
            )
        )
        client = TestClient(
            create_app(
                service,
                config_repository=repository,
                auth_store=repository,
                auth_mode="local",
                session_manager=SessionManager("test-session-secret"),
            )
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "reader", "password": "reader-password"},
            ).status_code
            == 200
        )
        assert client.get("/control/source-lineage", params={"run_id": "run-001"}).status_code == 200
        assert client.get("/control/publication-audit", params={"run_id": "run-001"}).status_code == 200
