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

        me = client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["username"] == "reader"
        assert me.json()["principal"]["role"] == "reader"

        logout = client.post("/auth/logout")
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
