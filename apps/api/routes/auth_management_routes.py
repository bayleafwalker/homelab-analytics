"""User management, service token, and audit route handlers.

Covers: /auth/users, /auth/service-tokens, /control/auth-audit
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Callable, cast

from fastapi import FastAPI, HTTPException, Request

from apps.api.models import (
    LocalUserCreateRequest,
    LocalUserPasswordResetRequest,
    LocalUserUpdateRequest,
    ServiceTokenCreateRequest,
)
from packages.platform.auth.crypto import hash_password, issue_service_token
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.platform.auth.serialization import serialize_service_token, serialize_user
from packages.storage.auth_store import (
    AuthStore,
    LocalUserCreate,
    ServiceTokenCreate,
    UserRole,
    normalize_service_token_name,
    normalize_service_token_scopes,
)
from packages.storage.control_plane import AuthAuditStore


def register_auth_management_routes(
    app: FastAPI,
    *,
    resolved_auth_store: AuthStore,
    resolved_config_repository: AuthAuditStore,
    require_unsafe_admin: Callable[[], None],
    record_auth_event: Callable[..., None],
    to_jsonable: Callable[[Any], Any],
) -> None:
    @app.get("/auth/users")
    async def list_auth_users() -> dict[str, Any]:
        require_unsafe_admin()
        return {"users": to_jsonable(resolved_auth_store.list_local_users())}

    @app.post("/auth/users", status_code=201)
    async def create_auth_user(
        request: Request,
        payload: LocalUserCreateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        try:
            resolved_auth_store.get_local_user_by_username(payload.username)
        except KeyError:
            pass
        else:
            raise HTTPException(status_code=400, detail="Username already exists.")
        user = resolved_auth_store.create_local_user(
            LocalUserCreate(
                user_id=f"user-{uuid.uuid4().hex}",
                username=payload.username,
                password_hash=hash_password(payload.password),
                role=payload.role,
            )
        )
        record_auth_event(
            request,
            event_type="user_created",
            success=True,
            actor=principal,
            subject_user_id=user.user_id,
            subject_username=user.username,
            detail=f"Created role={user.role.value}",
        )
        return {"user": serialize_user(user)}

    @app.patch("/auth/users/{user_id}")
    async def update_auth_user(
        user_id: str,
        payload: LocalUserUpdateRequest,
        request: Request,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        if principal is not None and principal.user_id == user_id:
            if payload.enabled is False:
                raise HTTPException(
                    status_code=400,
                    detail="You cannot disable your current session user.",
                )
            if payload.role is not None and payload.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=400,
                    detail="You cannot remove the admin role from your current session user.",
                )
        user = resolved_auth_store.update_local_user(
            user_id,
            role=payload.role,
            enabled=payload.enabled,
        )
        record_auth_event(
            request,
            event_type="user_updated",
            success=True,
            actor=principal,
            subject_user_id=user.user_id,
            subject_username=user.username,
            detail=f"Updated role={user.role.value} enabled={str(user.enabled).lower()}",
        )
        return {"user": serialize_user(user)}

    @app.post("/auth/users/{user_id}/password")
    async def reset_auth_user_password(
        user_id: str,
        payload: LocalUserPasswordResetRequest,
        request: Request,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        user = resolved_auth_store.update_local_user_password(
            user_id,
            password_hash=hash_password(payload.password),
        )
        record_auth_event(
            request,
            event_type="password_reset",
            success=True,
            actor=principal,
            subject_user_id=user.user_id,
            subject_username=user.username,
        )
        return {"user": serialize_user(user)}

    @app.get("/auth/service-tokens")
    async def list_service_tokens(
        include_revoked: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "service_tokens": [
                serialize_service_token(token)
                for token in resolved_auth_store.list_service_tokens(
                    include_revoked=include_revoked
                )
            ]
        }

    @app.post("/auth/service-tokens", status_code=201)
    async def create_service_token_endpoint(
        request: Request,
        payload: ServiceTokenCreateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        if payload.expires_at is not None and payload.expires_at <= datetime.now(UTC):
            raise HTTPException(
                status_code=400,
                detail="Service-token expiry must be in the future.",
            )
        issued_token = issue_service_token(f"token-{uuid.uuid4().hex}")
        token = resolved_auth_store.create_service_token(
            ServiceTokenCreate(
                token_id=issued_token.token_id,
                token_name=normalize_service_token_name(payload.token_name),
                token_secret_hash=issued_token.token_secret_hash,
                role=payload.role,
                scopes=normalize_service_token_scopes(payload.scopes),
                expires_at=payload.expires_at,
            )
        )
        record_auth_event(
            request,
            event_type="service_token_created",
            success=True,
            actor=principal,
            subject_user_id=token.token_id,
            subject_username=token.token_name,
            detail=(
                f"role={token.role.value} scopes={','.join(token.scopes)} "
                f"expires_at={token.expires_at.isoformat() if token.expires_at else 'none'}"
            ),
        )
        return {
            "service_token": serialize_service_token(token),
            "token_value": issued_token.token_value,
        }

    @app.post("/auth/service-tokens/{token_id}/revoke")
    async def revoke_service_token_endpoint(
        token_id: str,
        request: Request,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        token = resolved_auth_store.revoke_service_token(token_id)
        record_auth_event(
            request,
            event_type="service_token_revoked",
            success=True,
            actor=principal,
            subject_user_id=token.token_id,
            subject_username=token.token_name,
            detail=f"revoked_at={token.revoked_at.isoformat() if token.revoked_at else 'unknown'}",
        )
        return {"service_token": serialize_service_token(token)}

    @app.get("/control/auth-audit")
    async def list_auth_audit(
        event_type: str | None = None,
        success: bool | None = None,
        subject_username: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "auth_audit_events": to_jsonable(
                resolved_config_repository.list_auth_audit_events(
                    event_type=event_type,
                    success=success,
                    subject_username=subject_username,
                    limit=limit,
                )
            )
        }
