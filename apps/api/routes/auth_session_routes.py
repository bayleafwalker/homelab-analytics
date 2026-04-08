"""Session and OIDC authentication route handlers."""

from __future__ import annotations

from typing import Annotated, Any, Callable, cast
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from apps.api.models import LoginRequest
from packages.application.use_cases.auth_sessions import (
    build_auth_me_payload,
    complete_oidc_callback,
    perform_local_login,
    perform_logout,
    start_oidc_login as build_oidc_login_start_outcome,
)
from packages.platform.auth.break_glass import BreakGlassController
from packages.platform.auth.oidc_provider import OidcProvider
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.platform.auth.serialization import serialize_principal, serialize_user
from packages.platform.auth.session_manager import SessionManager
from packages.storage.auth_store import AuthStore


def register_auth_session_routes(
    app: FastAPI,
    *,
    resolved_auth_mode: str,
    resolved_identity_mode: str,
    resolved_auth_store: AuthStore,
    resolved_session_manager: SessionManager | None,
    resolved_oidc_provider: OidcProvider | None,
    cookie_secure_for_request: Callable[[Request], bool],
    break_glass_controller: BreakGlassController | None,
    record_auth_event: Callable[..., None],
    locked_out_until: Callable[[str, Any], Any],
    request_principal_from_user: Callable[..., AuthenticatedPrincipal],
) -> None:
    @app.post("/auth/login")
    async def login(request: Request, payload: LoginRequest) -> JSONResponse:
        outcome = perform_local_login(
            request,
            auth_mode=resolved_auth_mode,
            identity_mode=resolved_identity_mode,
            username=payload.username,
            password=payload.password,
            auth_store=resolved_auth_store,
            session_manager=resolved_session_manager,
            break_glass_controller=break_glass_controller,
            locked_out_until=locked_out_until,
            record_auth_event=record_auth_event,
            request_principal_from_user=request_principal_from_user,
        )
        if outcome.status != "success":
            raise HTTPException(
                status_code=_local_login_status_code(outcome.status),
                detail=_local_login_detail(outcome.status),
            )
        assert outcome.user is not None
        assert outcome.principal is not None
        assert outcome.issued_session is not None
        secure_cookie = cookie_secure_for_request(request)
        response = JSONResponse(
            {
                "auth_mode": resolved_identity_mode,
                "authenticated": True,
                "user": serialize_user(outcome.user),
                "principal": serialize_principal(outcome.principal),
            }
        )
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(
            key=resolved_session_manager.cookie_name,
            value=outcome.issued_session.cookie_value,
            httponly=True,
            max_age=resolved_session_manager.max_age_seconds,
            expires=resolved_session_manager.max_age_seconds,
            path="/",
            samesite=resolved_session_manager.same_site,
            secure=secure_cookie,
        )
        response.set_cookie(
            key=resolved_session_manager.csrf_cookie_name,
            value=outcome.issued_session.csrf_token,
            httponly=False,
            max_age=resolved_session_manager.max_age_seconds,
            expires=resolved_session_manager.max_age_seconds,
            path="/",
            samesite=resolved_session_manager.same_site,
            secure=secure_cookie,
        )
        return response

    @app.get("/auth/login")
    async def start_oidc_login(
        request: Request,
        return_to: Annotated[str | None, Query()] = None,
    ) -> RedirectResponse:
        outcome = build_oidc_login_start_outcome(
            auth_mode=resolved_auth_mode,
            return_to=return_to,
            oidc_provider=resolved_oidc_provider,
        )
        if outcome.status != "success":
            raise HTTPException(
                status_code=_oidc_start_status_code(outcome.status),
                detail=_oidc_start_detail(outcome.status),
            )
        assert outcome.redirect is not None
        secure_cookie = cookie_secure_for_request(request)
        response = RedirectResponse(outcome.redirect.authorization_url, status_code=303)
        response.set_cookie(
            key=resolved_oidc_provider.state_cookie_name,
            value=outcome.redirect.state_cookie_value,
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
    async def oidc_callback(
        request: Request,
        code: Annotated[str | None, Query()] = None,
        state: Annotated[str | None, Query()] = None,
        error: Annotated[str | None, Query()] = None,
    ) -> RedirectResponse:
        outcome = complete_oidc_callback(
            request,
            auth_mode=resolved_auth_mode,
            code=code,
            state=state,
            error=error,
            state_cookie_value=(
                request.cookies.get(resolved_oidc_provider.state_cookie_name)
                if resolved_oidc_provider is not None
                else None
            ),
            oidc_provider=resolved_oidc_provider,
            session_manager=resolved_session_manager,
            record_auth_event=record_auth_event,
        )
        if outcome.status == "auth_disabled":
            raise HTTPException(
                status_code=400,
                detail="OIDC authentication is not enabled.",
            )

        assert resolved_oidc_provider is not None
        assert resolved_session_manager is not None
        secure_cookie = cookie_secure_for_request(request)
        response = RedirectResponse(outcome.redirect_to, status_code=303)
        response.headers["Cache-Control"] = "no-store"
        response.delete_cookie(
            resolved_oidc_provider.state_cookie_name,
            path="/",
            httponly=True,
            samesite=resolved_oidc_provider.same_site,
            secure=secure_cookie,
        )
        if outcome.status == "success":
            assert outcome.principal is not None
            assert outcome.issued_session is not None
            response.set_cookie(
                key=resolved_session_manager.cookie_name,
                value=outcome.issued_session.cookie_value,
                httponly=True,
                max_age=resolved_session_manager.max_age_seconds,
                expires=resolved_session_manager.max_age_seconds,
                path="/",
                samesite=resolved_session_manager.same_site,
                secure=secure_cookie,
            )
            response.set_cookie(
                key=resolved_session_manager.csrf_cookie_name,
                value=outcome.issued_session.csrf_token,
                httponly=False,
                max_age=resolved_session_manager.max_age_seconds,
                expires=resolved_session_manager.max_age_seconds,
                path="/",
                samesite=resolved_session_manager.same_site,
                secure=secure_cookie,
            )
        return response

    @app.post("/auth/logout")
    async def logout(request: Request) -> JSONResponse:
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        perform_logout(
            identity_mode=resolved_identity_mode,
            principal=principal,
            break_glass_controller=break_glass_controller,
            record_auth_event=record_auth_event,
            request=request,
        )
        response = JSONResponse({"logged_out": True})
        if resolved_session_manager is not None:
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
        payload = build_auth_me_payload(
            auth_mode=resolved_auth_mode,
            identity_mode=resolved_identity_mode,
            principal=cast(AuthenticatedPrincipal | None, getattr(request.state, "principal", None)),
            auth_store=resolved_auth_store,
        )
        if payload is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        return payload


def _local_login_status_code(status: str) -> int:
    if status == "auth_disabled":
        return 400
    if status == "break_glass_disabled":
        return 403
    if status == "break_glass_internal_only":
        return 403
    if status == "locked_out":
        return 429
    return 401


def _local_login_detail(status: str) -> str:
    if status == "auth_disabled":
        return "Local authentication is not enabled."
    if status == "break_glass_disabled":
        return "Break-glass local access is disabled."
    if status == "break_glass_internal_only":
        return "Break-glass local access is limited to internal addresses."
    if status == "locked_out":
        return "Too many failed login attempts. Try again later."
    return "Invalid username or password."


def _oidc_start_status_code(status: str) -> int:
    if status == "auth_disabled":
        return 400
    return 502


def _oidc_start_detail(status: str) -> str:
    if status == "auth_disabled":
        return "OIDC authentication is not enabled."
    return "OIDC discovery failed."
