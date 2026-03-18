"""Session and OIDC authentication route handlers.

Covers: POST/GET /auth/login, GET /auth/callback, POST /auth/logout, GET /auth/me

ADR LOC exception: this file exceeds the 250-line review threshold (~354 lines) and is
accepted as a justified single-concern exception. It handles one logical flow — session
lifecycle — with local and OIDC variants that share session issuance and cookie management.
Splitting by auth mechanism would scatter related setup/teardown across files with no
readability gain. Revisit if a third auth variant is added.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable, cast

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from apps.api.models import LoginRequest
from packages.platform.auth.crypto import verify_password
from packages.platform.auth.oidc_provider import (
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcProvider,
    normalize_return_to,
)
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.platform.auth.serialization import (
    serialize_authenticated_user,
    serialize_principal,
    serialize_user,
)
from packages.platform.auth.session_manager import SessionManager
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import AuthStore, normalize_username


def register_auth_session_routes(
    app: FastAPI,
    *,
    resolved_auth_mode: str,
    resolved_auth_store: AuthStore,
    resolved_session_manager: SessionManager | None,
    resolved_oidc_provider: OidcProvider | None,
    cookie_secure_for_request: Callable[[Request], bool],
    record_auth_event: Callable[..., None],
    locked_out_until: Callable[[str, datetime], datetime | None],
    request_principal_from_user: Callable[..., AuthenticatedPrincipal],
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
