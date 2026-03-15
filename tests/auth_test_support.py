from __future__ import annotations

from datetime import UTC, datetime

from packages.shared.auth import hash_password, issue_service_token
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    AuthStore,
    LocalUserCreate,
    ServiceTokenCreate,
    UserRole,
)

FIXED_CREATED_AT = datetime(2026, 2, 1, tzinfo=UTC)
FIXED_LOGIN_AT = datetime(2026, 2, 2, tzinfo=UTC)


def assert_auth_store_round_trip(store: AuthStore) -> None:
    user = store.create_local_user(
        LocalUserCreate(
            user_id="user-reader-001",
            username="ReaderOne",
            password_hash=hash_password("reader-password"),
            role=UserRole.READER,
            created_at=FIXED_CREATED_AT,
        )
    )

    assert user.username == "readerone"
    assert user.role == UserRole.READER
    assert user.last_login_at is None

    assert store.get_local_user(user.user_id) == user
    assert store.get_local_user_by_username("READERONE") == user
    assert store.list_local_users(enabled_only=True) == [user]

    updated_user = store.update_local_user(
        user.user_id,
        role=UserRole.OPERATOR,
        enabled=False,
    )
    assert updated_user.role == UserRole.OPERATOR
    assert not updated_user.enabled
    assert store.list_local_users(enabled_only=True) == []

    updated_password_user = store.update_local_user_password(
        user.user_id,
        password_hash=hash_password("reader-password-rotated"),
    )
    assert updated_password_user.password_hash != user.password_hash

    logged_in_user = store.record_local_user_login(
        user.user_id,
        logged_in_at=FIXED_LOGIN_AT,
    )
    assert logged_in_user.last_login_at == FIXED_LOGIN_AT

    issued_token = issue_service_token("token-reader-001")
    token = store.create_service_token(
        ServiceTokenCreate(
            token_id=issued_token.token_id,
            token_name="dashboard-reader",
            token_secret_hash=issued_token.token_secret_hash,
            role=UserRole.READER,
            scopes=(SERVICE_TOKEN_SCOPE_REPORTS_READ,),
            created_at=FIXED_CREATED_AT,
        )
    )
    assert store.get_service_token(token.token_id) == token
    assert store.list_service_tokens() == [token]

    used_token = store.record_service_token_use(
        token.token_id,
        used_at=FIXED_LOGIN_AT,
    )
    assert used_token.last_used_at == FIXED_LOGIN_AT

    revoked_token = store.revoke_service_token(
        token.token_id,
        revoked_at=FIXED_LOGIN_AT,
    )
    assert revoked_token.revoked_at == FIXED_LOGIN_AT
    assert store.list_service_tokens() == []
    assert store.list_service_tokens(include_revoked=True)[0].token_id == token.token_id

    snapshot = store.export_snapshot()
    assert [record.user_id for record in snapshot.local_users] == [user.user_id]
    assert [record.token_id for record in snapshot.service_tokens] == [token.token_id]
