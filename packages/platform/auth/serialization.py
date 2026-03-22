"""Serialization helpers for user records and principals."""
from __future__ import annotations

from datetime import UTC, datetime

from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.storage.auth_store import LocalUserRecord, ServiceTokenRecord


def serialize_user(user: LocalUserRecord) -> dict[str, object]:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "enabled": user.enabled,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "auth_provider": "local",
    }


def serialize_authenticated_user(principal: AuthenticatedPrincipal) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role.value,
        "enabled": True,
        "created_at": None,
        "last_login_at": None,
        "auth_provider": principal.auth_provider,
    }
    if principal.auth_provider == "service_token":
        payload["scopes"] = list(principal.scopes)
        payload["token_id"] = principal.user_id
    if principal.permissions:
        payload["permissions"] = list(principal.permissions)
    return payload


def serialize_service_token(
    token: ServiceTokenRecord,
) -> dict[str, object]:
    return {
        "token_id": token.token_id,
        "token_name": token.token_name,
        "role": token.role.value,
        "scopes": list(token.scopes),
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        "created_at": token.created_at.isoformat(),
        "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
        "revoked_at": token.revoked_at.isoformat() if token.revoked_at else None,
        "revoked": token.revoked_at is not None,
        "expired": token.expires_at is not None and token.expires_at <= datetime.now(UTC),
    }


def serialize_principal(principal: AuthenticatedPrincipal) -> dict[str, str]:
    payload: dict[str, str] = {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role.value,
        "auth_provider": principal.auth_provider,
    }
    if principal.auth_provider == "service_token":
        payload["scopes"] = ",".join(principal.scopes)
    if principal.permissions:
        payload["permissions"] = ",".join(principal.permissions)
    return payload
