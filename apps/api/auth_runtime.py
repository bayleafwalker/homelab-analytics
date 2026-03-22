"""Auth middleware composer — wires platform/auth modules into a FastAPI middleware."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from logging import Logger

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from apps.api.support import log_request
from packages.platform.auth.audit_hooks import build_auth_event_recorder, build_lockout_checker
from packages.platform.auth.break_glass import BreakGlassController
from packages.platform.auth.credential_resolution import (
    bearer_token_from_request,
    cookie_secure_for_request,
    request_remote_addr,
)
from packages.platform.auth.crypto import has_required_service_token_scope, parse_service_token
from packages.platform.auth.oidc_provider import (
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcProvider,
)
from packages.platform.auth.permission_registry import (
    PrincipalAuthorizationContext,
    has_required_permission,
)
from packages.platform.auth.proxy_provider import (
    ProxyAuthenticationError,
    ProxyAuthorizationError,
    ProxyProvider,
)
from packages.platform.auth.role_hierarchy import (
    authenticate_service_token,
    has_required_role,
)
from packages.platform.auth.scope_authorization import (
    required_permission_for_path,
    required_role_for_path,
    required_service_token_scope_for_path,
)
from packages.platform.auth.session_manager import SessionManager
from packages.shared.auth_modes import is_cookie_auth_mode
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import (
    AuthStore,
    UserRole,
)

# Re-export platform helpers so existing callers in auth_routes.py, app.py, etc.
# don't need to update their imports in this PR.
__all__ = [
    "bearer_token_from_request",
    "build_auth_event_recorder",
    "build_lockout_checker",
    "cookie_secure_for_request",
    "register_auth_middleware",
    "request_remote_addr",
    "required_permission_for_path",
    "required_role_for_path",
    "required_service_token_scope_for_path",
]


def register_auth_middleware(
    app: FastAPI,
    *,
    logger: Logger,
    resolved_auth_mode: str,
    resolved_identity_mode: str,
    resolved_auth_store: AuthStore,
    resolved_session_manager: SessionManager | None,
    resolved_oidc_provider: OidcProvider | None,
    resolved_proxy_provider: ProxyProvider | None,
    enable_unsafe_admin: bool,
    break_glass_controller: BreakGlassController | None,
    record_auth_event: Callable[..., None],
) -> None:
    @app.middleware("http")
    async def authenticate_and_log_request(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        request.state.principal = None
        request.state.auth_via_cookie = False
        if resolved_auth_mode != "disabled":
            if is_cookie_auth_mode(resolved_auth_mode):
                assert resolved_session_manager is not None
            required_role = required_role_for_path(request.url.path)
            required_scope = required_service_token_scope_for_path(request.url.path)
            required_permission = required_permission_for_path(request.url.path)
            auth_error_response: JSONResponse | None = None
            bearer_token = bearer_token_from_request(request)
            if bearer_token is not None:
                parsed_service_token = parse_service_token(bearer_token)
                request.state.principal = authenticate_service_token(
                    bearer_token,
                    resolved_auth_store,
                )
                if (
                    request.state.principal is not None
                    and request.state.principal.auth_provider == "service_token"
                ):
                    metrics_registry.inc(
                        "auth_service_token_authenticated_requests_total",
                        1,
                        help_text="Total successfully authenticated service-token requests observed by this API process.",
                    )
                if request.state.principal is None and parsed_service_token is not None:
                    metrics_registry.inc(
                        "auth_service_token_failed_requests_total",
                        1,
                        help_text="Total rejected service-token bearer requests observed by this API process.",
                    )
                    record_auth_event(
                        request,
                        event_type="service_token_auth_failed",
                        success=False,
                        subject_user_id=parsed_service_token[0],
                        subject_username=parsed_service_token[0],
                        detail="Invalid, expired, or revoked service token.",
                    )
                    auth_error_response = JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid service token."},
                    )
                elif request.state.principal is None and resolved_auth_mode == "oidc":
                    assert resolved_oidc_provider is not None
                    try:
                        request.state.principal = (
                            resolved_oidc_provider.authenticate_bearer_token(
                                bearer_token
                            )
                        )
                    except OidcAuthorizationError as exc:
                        auth_error_response = JSONResponse(
                            status_code=403,
                            content={"detail": str(exc)},
                        )
                    except OidcAuthenticationError:
                        auth_error_response = JSONResponse(
                            status_code=401,
                            content={"detail": "Invalid bearer token."},
                        )
            else:
                if resolved_auth_mode == "proxy":
                    assert resolved_proxy_provider is not None
                    try:
                        request.state.principal = resolved_proxy_provider.authenticate_request(
                            request
                        )
                    except ProxyAuthorizationError as exc:
                        auth_error_response = JSONResponse(
                            status_code=403,
                            content={"detail": str(exc)},
                        )
                    except ProxyAuthenticationError as exc:
                        auth_error_response = JSONResponse(
                            status_code=401,
                            content={"detail": str(exc)},
                        )
                else:
                    assert resolved_session_manager is not None
                    request.state.principal = resolved_session_manager.authenticate(
                        request.cookies.get(resolved_session_manager.cookie_name),
                        resolved_auth_store,
                    )
                    request.state.auth_via_cookie = request.state.principal is not None
            if auth_error_response is not None:
                log_request(
                    logger,
                    request.method,
                    request.url.path,
                    auth_error_response.status_code,
                    started,
                )
                return auth_error_response
            if (
                break_glass_controller is not None
                and resolved_identity_mode == "local_single_user"
                and request.state.principal is not None
                and request.state.principal.auth_provider == "local"
            ):
                if not break_glass_controller.is_request_address_allowed(request):
                    record_auth_event(
                        request,
                        event_type="break_glass_request_blocked",
                        success=False,
                        actor=request.state.principal,
                        subject_user_id=request.state.principal.user_id,
                        subject_username=request.state.principal.username,
                        detail="Remote address is not allowed for break-glass access.",
                    )
                    denied_response = JSONResponse(
                        status_code=403,
                        content={"detail": "Break-glass access is limited to internal addresses."},
                    )
                    log_request(logger, request.method, request.url.path, 403, started)
                    return denied_response
                if not break_glass_controller.is_active():
                    record_auth_event(
                        request,
                        event_type="break_glass_window_expired",
                        success=False,
                        actor=request.state.principal,
                        subject_user_id=request.state.principal.user_id,
                        subject_username=request.state.principal.username,
                        detail="Break-glass window expired; new login required.",
                    )
                    denied_response = JSONResponse(
                        status_code=401,
                        content={"detail": "Break-glass session expired. Sign in again."},
                    )
                    log_request(logger, request.method, request.url.path, 401, started)
                    return denied_response
            if (
                request.state.principal is not None
                and bool(getattr(request.state, "auth_via_cookie", False))
                and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
            ):
                assert resolved_session_manager is not None
                csrf_header = request.headers.get("x-csrf-token")
                csrf_cookie = request.cookies.get(
                    resolved_session_manager.csrf_cookie_name
                )
                if (
                    request.state.principal.csrf_token is None
                    or csrf_cookie != request.state.principal.csrf_token
                    or csrf_header != request.state.principal.csrf_token
                ):
                    denied_response = JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF validation failed."},
                    )
                    log_request(logger, request.method, request.url.path, 403, started)
                    return denied_response
            if required_role is not None:
                admin_bypass = enable_unsafe_admin and required_role == UserRole.ADMIN
                if request.state.principal is None and not admin_bypass:
                    denied_response = JSONResponse(
                        status_code=401,
                        content={"detail": "Authentication required."},
                    )
                    log_request(logger, request.method, request.url.path, 401, started)
                    return denied_response
                principal_has_required_permission = (
                    request.state.principal is not None
                    and has_required_permission(
                        PrincipalAuthorizationContext(
                            role=request.state.principal.role,
                            auth_provider=request.state.principal.auth_provider,
                            scopes=request.state.principal.scopes,
                            granted_permissions=request.state.principal.permissions,
                            permission_bound=request.state.principal.permission_bound,
                        ),
                        required_permission,
                    )
                )
                if (
                    request.state.principal is not None
                    and not has_required_role(
                        request.state.principal.role,
                        required_role,
                    )
                    and not principal_has_required_permission
                ):
                    denied_response = JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"{required_role.value} role required.",
                        },
                    )
                    log_request(logger, request.method, request.url.path, 403, started)
                    return denied_response
                if (
                    request.state.principal is not None
                    and request.state.principal.auth_provider == "service_token"
                    and not has_required_service_token_scope(
                        request.state.principal.scopes,
                        required_scope,
                    )
                ):
                    denied_response = JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"{required_scope or 'required'} scope required.",
                        },
                    )
                    log_request(logger, request.method, request.url.path, 403, started)
                    return denied_response
                if (
                    request.state.principal is not None
                    and not principal_has_required_permission
                ):
                    denied_response = JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"{required_permission or 'required'} permission required.",
                        },
                    )
                    log_request(logger, request.method, request.url.path, 403, started)
                    return denied_response
        response = await call_next(request)
        if request.url.path.startswith("/ingest"):
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            metrics_registry.inc(
                "ingestion_duration_seconds",
                duration_ms / 1000,
                help_text="Cumulative ingestion handling duration in seconds.",
            )
        log_request(
            logger,
            request.method,
            request.url.path,
            response.status_code,
            started,
        )
        return response
