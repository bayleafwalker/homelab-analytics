"""Guard checks for break-glass and CSRF policy enforcement."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from packages.platform.auth.break_glass import BreakGlassController
from packages.platform.auth.middleware_types import AuthEventRecorder
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.platform.auth.session_manager import SessionManager

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def enforce_break_glass_access(
    request: Request,
    *,
    resolved_identity_mode: str,
    break_glass_controller: BreakGlassController | None,
    principal: AuthenticatedPrincipal | None,
    record_auth_event: AuthEventRecorder,
) -> JSONResponse | None:
    if (
        break_glass_controller is None
        or resolved_identity_mode != "local_single_user"
        or principal is None
        or principal.auth_provider != "local"
    ):
        return None
    if not break_glass_controller.is_request_address_allowed(request):
        record_auth_event(
            request,
            event_type="break_glass_request_blocked",
            success=False,
            actor=principal,
            subject_user_id=principal.user_id,
            subject_username=principal.username,
            detail="Remote address is not allowed for break-glass access.",
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "Break-glass access is limited to internal addresses."},
        )
    if not break_glass_controller.is_active():
        record_auth_event(
            request,
            event_type="break_glass_window_expired",
            success=False,
            actor=principal,
            subject_user_id=principal.user_id,
            subject_username=principal.username,
            detail="Break-glass window expired; new login required.",
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "Break-glass session expired. Sign in again."},
        )
    return None


def enforce_csrf_protection(
    request: Request,
    *,
    principal: AuthenticatedPrincipal | None,
    auth_via_cookie: bool,
    session_manager: SessionManager | None,
    csrf_failure_detail: str,
) -> JSONResponse | None:
    if (
        principal is None
        or not auth_via_cookie
        or request.method.upper() in _SAFE_METHODS
    ):
        return None
    assert session_manager is not None
    csrf_header = request.headers.get("x-csrf-token")
    csrf_cookie = request.cookies.get(session_manager.csrf_cookie_name)
    if session_manager.validate_csrf_token(
        principal,
        csrf_header,
        csrf_cookie,
    ):
        return None
    return JSONResponse(
        status_code=403,
        content={"detail": csrf_failure_detail},
    )
