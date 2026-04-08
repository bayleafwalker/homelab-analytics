"""Auth middleware composer — wires platform/auth modules into a FastAPI middleware."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from logging import Logger

from fastapi import FastAPI, Request
from fastapi.responses import Response

from apps.api.support import log_request
from packages.platform.auth.audit_hooks import build_auth_event_recorder, build_lockout_checker
from packages.platform.auth.break_glass import BreakGlassController
from packages.platform.auth.credential_resolution import (
    bearer_token_from_request,
    cookie_secure_for_request,
    request_remote_addr,
)
from packages.platform.auth.middleware_authentication import authenticate_request
from packages.platform.auth.middleware_authorization import authorize_request
from packages.platform.auth.middleware_guards import (
    enforce_break_glass_access,
    enforce_csrf_protection,
)
from packages.platform.auth.middleware_metrics import record_ingestion_duration
from packages.platform.auth.machine_jwt_provider import MachineJwtProvider
from packages.platform.auth.oidc_provider import OidcProvider
from packages.platform.auth.proxy_provider import ProxyProvider
from packages.platform.auth.scope_authorization import (
    required_permission_for_path,
    required_permission_for_request,
    required_role_for_path,
    required_role_for_request,
    required_service_token_scope_for_path,
    required_service_token_scope_for_request,
)
from packages.platform.auth.session_manager import SessionManager
from packages.shared.auth_modes import is_cookie_auth_mode
from packages.storage.auth_store import (
    AuthStore,
)

# Re-export platform helpers so existing callers in auth_routes.py, app.py, etc.
# don't need to update their imports in this PR.
__all__ = [
    "bearer_token_from_request",
    "build_auth_event_recorder",
    "build_lockout_checker",
    "cookie_secure_for_request",
    "required_permission_for_request",
    "register_auth_middleware",
    "request_remote_addr",
    "required_permission_for_path",
    "required_role_for_path",
    "required_role_for_request",
    "required_service_token_scope_for_path",
    "required_service_token_scope_for_request",
]

AUTH_REQUIRED_DETAIL = "Authentication required."
CSRF_VALIDATION_FAILED_DETAIL = "CSRF validation failed."


def register_auth_middleware(
    app: FastAPI,
    *,
    logger: Logger,
    resolved_auth_mode: str,
    resolved_identity_mode: str,
    resolved_auth_store: AuthStore,
    resolved_session_manager: SessionManager | None,
    resolved_oidc_provider: OidcProvider | None,
    resolved_machine_jwt_provider: MachineJwtProvider | None,
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
        import time

        started = time.perf_counter()
        request.state.principal = None
        request.state.auth_via_cookie = False
        auth_error_response: Response | None = None
        if resolved_auth_mode != "disabled":
            if is_cookie_auth_mode(resolved_auth_mode):
                assert resolved_session_manager is not None
            required_role = required_role_for_request(
                request.url.path,
                request.method,
            )
            required_scope = required_service_token_scope_for_request(
                request.url.path,
                request.method,
            )
            required_permission = required_permission_for_request(
                request.url.path,
                request.query_params,
                method=request.method,
            )
            auth_result = authenticate_request(
                request,
                resolved_auth_mode=resolved_auth_mode,
                resolved_auth_store=resolved_auth_store,
                resolved_session_manager=resolved_session_manager,
                resolved_oidc_provider=resolved_oidc_provider,
                resolved_machine_jwt_provider=resolved_machine_jwt_provider,
                resolved_proxy_provider=resolved_proxy_provider,
                record_auth_event=record_auth_event,
            )
            request.state.principal = auth_result.principal
            request.state.auth_via_cookie = auth_result.auth_via_cookie
            auth_error_response = auth_result.response
            if auth_error_response is not None:
                log_request(
                    logger,
                    request.method,
                    request.url.path,
                    auth_error_response.status_code,
                    started,
                )
                return auth_error_response
            auth_error_response = enforce_break_glass_access(
                request,
                resolved_identity_mode=resolved_identity_mode,
                break_glass_controller=break_glass_controller,
                principal=request.state.principal,
                record_auth_event=record_auth_event,
            )
            if auth_error_response is None:
                auth_error_response = enforce_csrf_protection(
                    request,
                    principal=request.state.principal,
                    auth_via_cookie=bool(getattr(request.state, "auth_via_cookie", False)),
                    session_manager=resolved_session_manager,
                    csrf_failure_detail=CSRF_VALIDATION_FAILED_DETAIL,
                )
            if auth_error_response is None:
                auth_error_response = authorize_request(
                    principal=request.state.principal,
                    required_role=required_role,
                    required_scope=required_scope,
                    required_permission=required_permission,
                    enable_unsafe_admin=enable_unsafe_admin,
                    authentication_required_detail=AUTH_REQUIRED_DETAIL,
                )
            if auth_error_response is not None:
                log_request(
                    logger,
                    request.method,
                    request.url.path,
                    auth_error_response.status_code,
                    started,
                )
                return auth_error_response
        response = await call_next(request)
        if request.url.path.startswith("/ingest"):
            record_ingestion_duration(started)
        log_request(
            logger,
            request.method,
            request.url.path,
            response.status_code,
            started,
        )
        return response
