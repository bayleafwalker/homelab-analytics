"""SQLite auth coverage is intentionally limited to local bootstrap smoke paths."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from packages.shared.auth import hash_password, issue_service_token
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    LocalUserCreate,
    ServiceTokenCreate,
    UserRole,
)
from packages.storage.ingestion_config import IngestionConfigRepository


def test_sqlite_auth_store_supports_local_bootstrap_smoke() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        created_user = repository.create_local_user(
            LocalUserCreate(
                user_id="user-reader-001",
                username="ReaderOne",
                password_hash=hash_password("reader-password"),
                role=UserRole.READER,
            )
        )
        issued_token = issue_service_token("token-reader-001")
        created_token = repository.create_service_token(
            ServiceTokenCreate(
                token_id=issued_token.token_id,
                token_name="dashboard-reader",
                token_secret_hash=issued_token.token_secret_hash,
                role=UserRole.READER,
                scopes=(SERVICE_TOKEN_SCOPE_REPORTS_READ,),
            )
        )

        assert repository.get_local_user_by_username("readerone").user_id == created_user.user_id
        assert repository.get_service_token(created_token.token_id).token_name == "dashboard-reader"
