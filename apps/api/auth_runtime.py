from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from logging import Logger
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from apps.api.support import log_request
from packages.shared.auth import (
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcProvider,
    SessionManager,
    authenticate_service_token,
    has_required_role,
    has_required_service_token_scope,
    parse_service_token,
)
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    AuthStore,
    UserRole,
)
from packages.storage.control_plane import AuthAuditEventCreate, ControlPlaneStore


def request_remote_addr(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    if request.client is None:
        return None
    return request.client.host


def cookie_secure_for_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme.lower() == "https"


def build_auth_event_recorder(
    config_repository: ControlPlaneStore,
) -> Callable[..., None]:
    def record_auth_event(
        request: Request,
        *,
        event_type: str,
        success: bool,
        actor: Any = None,
        subject_user_id: str | None = None,
        subject_username: str | None = None,
        detail: str | None = None,
    ) -> None:
        config_repository.record_auth_audit_events(
            (
                AuthAuditEventCreate(
                    event_id=uuid.uuid4().hex,
                    event_type=event_type,
                    success=success,
                    actor_user_id=actor.user_id if actor else None,
                    actor_username=actor.username if actor else None,
                    subject_user_id=subject_user_id,
                    subject_username=subject_username,
                    remote_addr=request_remote_addr(request),
                    user_agent=request.headers.get("user-agent"),
                    detail=detail,
                ),
            )
        )

    return record_auth_event


def build_lockout_checker(
    config_repository: ControlPlaneStore,
    *,
    auth_failure_window_seconds: int,
    auth_failure_threshold: int,
    auth_lockout_seconds: int,
) -> Callable[[str, datetime], datetime | None]:
    def locked_out_until(username: str, now: datetime) -> datetime | None:
        recent_events = config_repository.list_auth_audit_events(
            subject_username=username,
            since=now - timedelta(seconds=auth_failure_window_seconds),
            limit=max(auth_failure_threshold * 4, 20),
        )
        consecutive_failures = 0
        latest_failure_at: datetime | None = None
        for event in recent_events:
            if event.event_type == "login_succeeded" and event.success:
                break
            if event.event_type not in {"login_failed", "login_blocked"}:
                continue
            if event.success:
                continue
            consecutive_failures += 1
            if latest_failure_at is None:
                latest_failure_at = event.occurred_at
        if latest_failure_at is None or consecutive_failures < auth_failure_threshold:
            return None
        candidate = latest_failure_at + timedelta(seconds=auth_lockout_seconds)
        if candidate <= now:
            return None
        return candidate

    return locked_out_until


def required_role_for_path(path: str) -> UserRole | None:
    if path in {
        "/health",
        "/ready",
        "/metrics",
        "/auth/login",
        "/auth/logout",
        "/auth/callback",
    }:
        return None
    if path.startswith("/runs/") and path.endswith("/retry"):
        return UserRole.OPERATOR
    if path in {
        "/control/source-lineage",
        "/control/publication-audit",
        "/transformation-audit",
    }:
        return UserRole.READER
    if (
        path.startswith("/auth/users")
        or path.startswith("/auth/service-tokens")
        or path == "/control/auth-audit"
        or path == "/control/schedule-dispatches"
        or path.startswith("/config/")
        or path.startswith("/control/")
        or path in {"/extensions", "/sources"}
        or path.startswith("/landing/")
        or path.startswith("/transformations/")
        or path.startswith("/ingest/ingestion-definitions/")
    ):
        return UserRole.ADMIN
    if path.startswith("/ingest"):
        return UserRole.OPERATOR
    if (
        path.startswith("/runs")
        or path.startswith("/reports")
        or path == "/auth/me"
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
    ):
        return UserRole.READER
    return None


def required_service_token_scope_for_path(path: str) -> str | None:
    if path in {
        "/health",
        "/ready",
        "/metrics",
        "/auth/login",
        "/auth/logout",
        "/auth/callback",
    }:
        return None
    if path.startswith("/ingest") or (
        path.startswith("/runs/") and path.endswith("/retry")
    ):
        return SERVICE_TOKEN_SCOPE_INGEST_WRITE
    if (
        path.startswith("/runs")
        or path == "/control/source-lineage"
        or path == "/control/publication-audit"
        or path == "/transformation-audit"
    ):
        return SERVICE_TOKEN_SCOPE_RUNS_READ
    if path.startswith("/reports"):
        return SERVICE_TOKEN_SCOPE_REPORTS_READ
    if (
        path.startswith("/auth/users")
        or path.startswith("/auth/service-tokens")
        or path == "/control/auth-audit"
        or path == "/control/schedule-dispatches"
        or path.startswith("/config/")
        or path.startswith("/control/")
        or path in {"/extensions", "/sources"}
        or path.startswith("/landing/")
        or path.startswith("/transformations/")
        or path.startswith("/ingest/ingestion-definitions/")
    ):
        return SERVICE_TOKEN_SCOPE_ADMIN_WRITE
    return None


def bearer_token_from_request(request: Request) -> str | None:
    header_value = request.headers.get("authorization", "").strip()
    if not header_value:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def register_auth_middleware(
    app: FastAPI,
    *,
    logger: Logger,
    resolved_auth_mode: str,
    resolved_auth_store: AuthStore,
    resolved_session_manager: SessionManager | None,
    resolved_oidc_provider: OidcProvider | None,
    enable_unsafe_admin: bool,
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
        if resolved_auth_mode in {"local", "oidc"}:
            assert resolved_session_manager is not None
            required_role = required_role_for_path(request.url.path)
            required_scope = required_service_token_scope_for_path(request.url.path)
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
                request.state.principal is not None
                and bool(getattr(request.state, "auth_via_cookie", False))
                and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
            ):
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
                if (
                    request.state.principal is not None
                    and not has_required_role(
                        request.state.principal.role,
                        required_role,
                    )
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
