from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol, runtime_checkable


class UserRole(str, Enum):
    READER = "reader"
    OPERATOR = "operator"
    ADMIN = "admin"


SERVICE_TOKEN_SCOPE_REPORTS_READ = "reports:read"
SERVICE_TOKEN_SCOPE_RUNS_READ = "runs:read"
SERVICE_TOKEN_SCOPE_INGEST_WRITE = "ingest:write"
SERVICE_TOKEN_SCOPE_ADMIN_WRITE = "admin:write"
SERVICE_TOKEN_SCOPES = (
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
)


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized:
        raise ValueError("Username must not be empty.")
    return normalized


def normalize_service_token_name(token_name: str) -> str:
    normalized = token_name.strip()
    if not normalized:
        raise ValueError("Service-token name must not be empty.")
    return normalized


def normalize_service_token_scopes(scopes: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized = {scope.strip().lower() for scope in scopes if scope.strip()}
    if not normalized:
        raise ValueError("Service token must include at least one scope.")
    unknown = normalized.difference(SERVICE_TOKEN_SCOPES)
    if unknown:
        raise ValueError(
            f"Unknown service-token scope(s): {', '.join(sorted(unknown))}."
        )
    return tuple(scope for scope in SERVICE_TOKEN_SCOPES if scope in normalized)


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


@dataclass(frozen=True)
class ServiceTokenCreate:
    token_id: str
    token_name: str
    token_secret_hash: str
    role: UserRole
    scopes: tuple[str, ...]
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class ServiceTokenRecord:
    token_id: str
    token_name: str
    token_secret_hash: str
    role: UserRole
    scopes: tuple[str, ...]
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


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

    def update_local_user(
        self,
        user_id: str,
        *,
        role: UserRole | None = None,
        enabled: bool | None = None,
    ) -> LocalUserRecord:
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

    def create_service_token(self, token: ServiceTokenCreate) -> ServiceTokenRecord:
        ...

    def get_service_token(self, token_id: str) -> ServiceTokenRecord:
        ...

    def list_service_tokens(
        self,
        *,
        include_revoked: bool = False,
    ) -> list[ServiceTokenRecord]:
        ...

    def revoke_service_token(
        self,
        token_id: str,
        *,
        revoked_at: datetime | None = None,
    ) -> ServiceTokenRecord:
        ...

    def record_service_token_use(
        self,
        token_id: str,
        *,
        used_at: datetime | None = None,
    ) -> ServiceTokenRecord:
        ...
