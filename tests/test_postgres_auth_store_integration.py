from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from packages.shared.auth import hash_password, issue_service_token
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    LocalUserCreate,
    ServiceTokenCreate,
    UserRole,
)
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.postgres_ingestion_config import PostgresIngestionConfigRepository
from tests.auth_test_support import assert_auth_store_round_trip
from tests.postgres_test_support import running_postgres_container

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_postgres_auth_store_round_trips_local_users() -> None:
    with running_postgres_container() as dsn:
        repository = PostgresIngestionConfigRepository(dsn, schema="control")

        assert_auth_store_round_trip(repository)


def test_sqlite_auth_snapshot_imports_into_postgres() -> None:
    with TemporaryDirectory() as temp_dir:
        sqlite_repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        sqlite_repository.create_local_user(
            LocalUserCreate(
                user_id="user-admin-001",
                username="AdminOne",
                password_hash=hash_password("admin-password"),
                role=UserRole.ADMIN,
            )
        )
        issued_token = issue_service_token("token-reader-001")
        sqlite_repository.create_service_token(
            ServiceTokenCreate(
                token_id=issued_token.token_id,
                token_name="dashboard-reader",
                token_secret_hash=issued_token.token_secret_hash,
                role=UserRole.READER,
                scopes=(SERVICE_TOKEN_SCOPE_REPORTS_READ,),
            )
        )
        snapshot = sqlite_repository.export_snapshot()

        with running_postgres_container() as dsn:
            postgres_repository = PostgresIngestionConfigRepository(
                dsn,
                schema="control",
            )
            postgres_repository.import_snapshot(snapshot)

            user = postgres_repository.get_local_user_by_username("adminone")
            assert user.user_id == "user-admin-001"
            assert user.role == UserRole.ADMIN
            token = postgres_repository.get_service_token("token-reader-001")
            assert token.token_name == "dashboard-reader"
