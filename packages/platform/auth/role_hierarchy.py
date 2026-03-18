"""Role hierarchy, principal dataclass, and service token authentication."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from packages.platform.auth.crypto import parse_service_token, verify_service_token_secret
from packages.storage.auth_store import AuthStore, ServiceTokenRecord, UserRole

_ROLE_ORDER = {
    UserRole.READER: 0,
    UserRole.OPERATOR: 1,
    UserRole.ADMIN: 2,
}


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: str
    username: str
    role: UserRole
    auth_provider: Literal["local", "oidc", "service_token"] = "local"
    csrf_token: str | None = None
    scopes: tuple[str, ...] = ()


def has_required_role(role: UserRole, required_role: UserRole) -> bool:
    return _ROLE_ORDER[role] >= _ROLE_ORDER[required_role]


def principal_from_service_token(token: ServiceTokenRecord) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=token.token_id,
        username=token.token_name,
        role=token.role,
        auth_provider="service_token",
        scopes=token.scopes,
    )


def authenticate_service_token(
    token_value: str | None,
    auth_store: AuthStore,
) -> AuthenticatedPrincipal | None:
    parsed = parse_service_token(token_value)
    if parsed is None:
        return None
    token_id, token_secret = parsed
    try:
        token = auth_store.get_service_token(token_id)
    except KeyError:
        return None
    if token.revoked_at is not None:
        return None
    if token.expires_at is not None and token.expires_at <= datetime.now(UTC):
        return None
    if not verify_service_token_secret(token_secret, token.token_secret_hash):
        return None
    token = auth_store.record_service_token_use(token.token_id)
    return principal_from_service_token(token)
