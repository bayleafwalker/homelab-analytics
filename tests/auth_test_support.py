from __future__ import annotations

from datetime import UTC, datetime

from packages.shared.auth import hash_password
from packages.storage.auth_store import AuthStore, LocalUserCreate, UserRole

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

    snapshot = store.export_snapshot()
    assert [record.user_id for record in snapshot.local_users] == [user.user_id]
