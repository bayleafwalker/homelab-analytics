from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Callable, cast

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from apps.api.models import (
    LocalUserCreateRequest,
    LocalUserPasswordResetRequest,
    LocalUserUpdateRequest,
    LoginRequest,
    ServiceTokenCreateRequest,
)
from packages.shared.auth import (
    AuthenticatedPrincipal,
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcProvider,
    SessionManager,
    hash_password,
    issue_service_token,
    normalize_return_to,
    serialize_authenticated_user,
    serialize_principal,
    serialize_service_token,
    serialize_user,
    verify_password,
)
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import (
    AuthStore,
    LocalUserCreate,
    ServiceTokenCreate,
    UserRole,
    normalize_service_token_name,
    normalize_service_token_scopes,
    normalize_username,
)
from packages.storage.control_plane import AuthAuditStore


def register_auth_routes(
    app: FastAPI,
    *,
    resolved_auth_mode: str,
    resolved_auth_store: AuthStore,
    resolved_config_repository: AuthAuditStore,
    resolved_session_manager: SessionManager | None,
    resolved_oidc_provider: OidcProvider | None,
    require_unsafe_admin: Callable[[], None],
    cookie_secure_for_request: Callable[[Request], bool],
    record_auth_event: Callable[..., None],
    locked_out_until: Callable[[str, datetime], datetime | None],
    request_principal_from_user: Callable[..., AuthenticatedPrincipal],
    to_jsonable: Callable[[Any], Any],
) -> None:
    @app.post("/auth/login")
    async def login(request: Request, payload: LoginRequest) -> JSONResponse:
        if resolved_auth_mode != "local":
            raise HTTPException(
                status_code=400,
                detail="Local authentication is not enabled.",
            )
        normalized_username = normalize_username(payload.username)
        now = datetime.now(UTC)
        locked_until = locked_out_until(normalized_username, now)
        if locked_until is not None:
            metrics_registry.inc(
                "auth_lockouts_total",
                1,
                help_text="Total login lockouts observed by the API.",
            )
            record_auth_event(
                request,
                event_type="login_blocked",
                success=False,
                subject_username=normalized_username,
                detail=f"Locked out until {locked_until.isoformat()}",
            )
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Try again later.",
            )
        try:
            user = resolved_auth_store.get_local_user_by_username(normalized_username)
        except KeyError as exc:
            metrics_registry.inc(
                "auth_failures_total",
                1,
                help_text="Total failed login attempts observed by the API.",
            )
            record_auth_event(
                request,
                event_type="login_failed",
                success=False,
                subject_username=normalized_username,
                detail="Unknown username.",
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password.",
            ) from exc
        if not user.enabled or not verify_password(payload.password, user.password_hash):
            metrics_registry.inc(
                "auth_failures_total",
                1,
                help_text="Total failed login attempts observed by the API.",
            )
            record_auth_event(
                request,
                event_type="login_failed",
                success=False,
                subject_user_id=user.user_id,
                subject_username=user.username,
                detail="Invalid password or disabled user.",
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password.",
            )
        user = resolved_auth_store.record_local_user_login(user.user_id)
        assert resolved_session_manager is not None
        record_auth_event(
            request,
            event_type="login_succeeded",
            success=True,
            subject_user_id=user.user_id,
            subject_username=user.username,
        )
        issued_session = resolved_session_manager.issue_session(user)
        secure_cookie = cookie_secure_for_request(request)
        response = JSONResponse(
            {
                "auth_mode": "local",
                "authenticated": True,
                "user": serialize_user(user),
                "principal": serialize_principal(
                    request_principal_from_user(
                        user,
                        csrf_token=issued_session.csrf_token,
                    )
                ),
            }
        )
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(
            key=resolved_session_manager.cookie_name,
            value=issued_session.cookie_value,
            httponly=True,
            max_age=resolved_session_manager.max_age_seconds,
            expires=resolved_session_manager.max_age_seconds,
            path="/",
            samesite=resolved_session_manager.same_site,
            secure=secure_cookie,
        )
        response.set_cookie(
            key=resolved_session_manager.csrf_cookie_name,
            value=issued_session.csrf_token,
            httponly=False,
            max_age=resolved_session_manager.max_age_seconds,
            expires=resolved_session_manager.max_age_seconds,
            path="/",
            samesite=resolved_session_manager.same_site,
            secure=secure_cookie,
        )
        return response

    @app.get("/auth/login")
    async def start_oidc_login(request: Request) -> RedirectResponse:
        if resolved_auth_mode != "oidc":
            raise HTTPException(
                status_code=400,
                detail="OIDC authentication is not enabled.",
            )
        assert resolved_oidc_provider is not None
        try:
            redirect = resolved_oidc_provider.build_login_redirect(
                request.query_params.get("return_to")
            )
        except (OidcAuthenticationError, httpx.HTTPError) as exc:
            raise HTTPException(
                status_code=502,
                detail="OIDC discovery failed.",
            ) from exc
        secure_cookie = cookie_secure_for_request(request)
        response = RedirectResponse(redirect.authorization_url, status_code=303)
        response.set_cookie(
            key=resolved_oidc_provider.state_cookie_name,
            value=redirect.state_cookie_value,
            httponly=True,
            max_age=resolved_oidc_provider.state_max_age_seconds,
            expires=resolved_oidc_provider.state_max_age_seconds,
            path="/",
            samesite=resolved_oidc_provider.same_site,
            secure=secure_cookie,
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/auth/callback")
    async def oidc_callback(request: Request) -> RedirectResponse:
        if resolved_auth_mode != "oidc":
            raise HTTPException(
                status_code=400,
                detail="OIDC authentication is not enabled.",
            )
        assert resolved_session_manager is not None
        assert resolved_oidc_provider is not None
        provider_error = request.query_params.get("error")
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if provider_error or not code or not state:
            record_auth_event(
                request,
                event_type="login_failed",
                success=False,
                detail=provider_error or "OIDC callback missing code or state.",
            )
            response = RedirectResponse("/login?error=oidc-failed", status_code=303)
            response.delete_cookie(
                resolved_oidc_provider.state_cookie_name,
                path="/",
                httponly=True,
                samesite=resolved_oidc_provider.same_site,
                secure=cookie_secure_for_request(request),
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        try:
            principal, return_to = resolved_oidc_provider.authenticate_callback(
                code=code,
                state=state,
                cookie_value=request.cookies.get(resolved_oidc_provider.state_cookie_name),
            )
        except OidcAuthorizationError as exc:
            record_auth_event(
                request,
                event_type="login_failed",
                success=False,
                detail=str(exc),
            )
            response = RedirectResponse("/login?error=oidc-unmapped", status_code=303)
            response.delete_cookie(
                resolved_oidc_provider.state_cookie_name,
                path="/",
                httponly=True,
                samesite=resolved_oidc_provider.same_site,
                secure=cookie_secure_for_request(request),
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        except (OidcAuthenticationError, httpx.HTTPError) as exc:
            record_auth_event(
                request,
                event_type="login_failed",
                success=False,
                detail=str(exc),
            )
            response = RedirectResponse("/login?error=oidc-failed", status_code=303)
            response.delete_cookie(
                resolved_oidc_provider.state_cookie_name,
                path="/",
                httponly=True,
                samesite=resolved_oidc_provider.same_site,
                secure=cookie_secure_for_request(request),
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        record_auth_event(
            request,
            event_type="login_succeeded",
            success=True,
            subject_user_id=principal.user_id,
            subject_username=principal.username,
        )
        issued_session = resolved_session_manager.issue_session(principal)
        secure_cookie = cookie_secure_for_request(request)
        response = RedirectResponse(normalize_return_to(return_to), status_code=303)
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(
            key=resolved_session_manager.cookie_name,
            value=issued_session.cookie_value,
            httponly=True,
            max_age=resolved_session_manager.max_age_seconds,
            expires=resolved_session_manager.max_age_seconds,
            path="/",
            samesite=resolved_session_manager.same_site,
            secure=secure_cookie,
        )
        response.set_cookie(
            key=resolved_session_manager.csrf_cookie_name,
            value=issued_session.csrf_token,
            httponly=False,
            max_age=resolved_session_manager.max_age_seconds,
            expires=resolved_session_manager.max_age_seconds,
            path="/",
            samesite=resolved_session_manager.same_site,
            secure=secure_cookie,
        )
        response.delete_cookie(
            resolved_oidc_provider.state_cookie_name,
            path="/",
            httponly=True,
            samesite=resolved_oidc_provider.same_site,
            secure=secure_cookie,
        )
        return response

    @app.post("/auth/logout")
    async def logout(request: Request) -> JSONResponse:
        response = JSONResponse({"logged_out": True})
        if resolved_session_manager is not None:
            principal = cast(
                AuthenticatedPrincipal | None,
                getattr(request.state, "principal", None),
            )
            if principal is not None:
                record_auth_event(
                    request,
                    event_type="logout",
                    success=True,
                    actor=principal,
                    subject_user_id=principal.user_id,
                    subject_username=principal.username,
                )
            secure_cookie = cookie_secure_for_request(request)
            response.delete_cookie(
                resolved_session_manager.cookie_name,
                path="/",
                httponly=True,
                samesite=resolved_session_manager.same_site,
                secure=secure_cookie,
            )
            response.delete_cookie(
                resolved_session_manager.csrf_cookie_name,
                path="/",
                httponly=False,
                samesite=resolved_session_manager.same_site,
                secure=secure_cookie,
            )
        if resolved_oidc_provider is not None:
            response.delete_cookie(
                resolved_oidc_provider.state_cookie_name,
                path="/",
                httponly=True,
                samesite=resolved_oidc_provider.same_site,
                secure=cookie_secure_for_request(request),
            )
        return response

    @app.get("/auth/me")
    async def auth_me(request: Request) -> dict[str, Any]:
        if resolved_auth_mode == "disabled":
            return {"auth_mode": "disabled", "authenticated": False}
        principal = getattr(request.state, "principal", None)
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if principal.auth_provider == "local":
            user = resolved_auth_store.get_local_user(principal.user_id)
            serialized_user = serialize_user(user)
        else:
            serialized_user = serialize_authenticated_user(principal)
        return {
            "auth_mode": resolved_auth_mode,
            "authenticated": True,
            "user": serialized_user,
            "principal": serialize_principal(principal),
        }

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
