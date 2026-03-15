from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol, runtime_checkable


class UserRole(str, Enum):
    READER = "reader"
    OPERATOR = "operator"
    ADMIN = "admin"


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized:
        raise ValueError("Username must not be empty.")
    return normalized


@dataclass(frozen=True)
class LocalUserCreate:
    user_id: str
    username: str
    password_hash: str
    role: UserRole
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_login_at: datetime | None = None


@dataclass(frozen=True)
class LocalUserRecord:
    user_id: str
    username: str
    password_hash: str
    role: UserRole
    enabled: bool
    created_at: datetime
    last_login_at: datetime | None


@runtime_checkable
class AuthStore(Protocol):
    def create_local_user(self, user: LocalUserCreate) -> LocalUserRecord:
        ...

    def get_local_user(self, user_id: str) -> LocalUserRecord:
        ...

    def get_local_user_by_username(self, username: str) -> LocalUserRecord:
        ...

    def list_local_users(self, *, enabled_only: bool = False) -> list[LocalUserRecord]:
        ...

    def update_local_user_password(
        self,
        user_id: str,
        *,
        password_hash: str,
    ) -> LocalUserRecord:
        ...

    def record_local_user_login(
        self,
        user_id: str,
        *,
        logged_in_at: datetime | None = None,
    ) -> LocalUserRecord:
        ...
