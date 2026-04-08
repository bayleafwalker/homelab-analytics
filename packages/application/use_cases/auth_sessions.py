from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from packages.platform.auth.break_glass import BreakGlassController
from packages.platform.auth.crypto import verify_password
from packages.platform.auth.oidc_provider import (
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcLoginRedirect,
    OidcProvider,
    normalize_return_to,
)
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.platform.auth.serialization import (
    serialize_authenticated_user,
    serialize_principal,
    serialize_user,
)
from packages.platform.auth.session_manager import IssuedSession, SessionManager
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import AuthStore, LocalUserRecord, normalize_username

LocalLoginStatus = Literal[
    "success",
    "auth_disabled",
    "break_glass_disabled",
    "break_glass_internal_only",
    "locked_out",
    "unknown_user",
    "invalid_credentials",
]
OidcLoginStartStatus = Literal["success", "auth_disabled", "discovery_failed"]
OidcCallbackStatus = Literal[
    "success",
    "auth_disabled",
    "missing_code_or_state",
    "unmapped",
    "failed",
]


@dataclass(frozen=True)
class LocalLoginOutcome:
    status: LocalLoginStatus
    user: LocalUserRecord | None = None
    principal: AuthenticatedPrincipal | None = None
    issued_session: IssuedSession | None = None
    break_glass_active_until: datetime | None = None


@dataclass(frozen=True)
class OidcLoginStartOutcome:
    status: OidcLoginStartStatus
    redirect: OidcLoginRedirect | None = None


@dataclass(frozen=True)
class OidcCallbackOutcome:
    status: OidcCallbackStatus
    redirect_to: str
    principal: AuthenticatedPrincipal | None = None
    issued_session: IssuedSession | None = None


@dataclass(frozen=True)
class LogoutOutcome:
    logged_out: bool = True
    break_glass_cleared: bool = False


def perform_local_login(
    request: Any,
    *,
    auth_mode: str,
    identity_mode: str,
    username: str,
    password: str,
    auth_store: AuthStore,
    session_manager: SessionManager | None,
    break_glass_controller: BreakGlassController | None,
    locked_out_until: Callable[[str, datetime], datetime | None],
    record_auth_event: Callable[..., None],
    request_principal_from_user: Callable[..., AuthenticatedPrincipal],
) -> LocalLoginOutcome:
    if auth_mode != "local":
        return LocalLoginOutcome(status="auth_disabled")

    if identity_mode == "local_single_user":
        if break_glass_controller is None or not break_glass_controller.enabled:
            record_auth_event(
                request,
                event_type="break_glass_login_blocked",
                success=False,
                subject_username=username.strip().lower() or None,
                detail="Break-glass local login is disabled by configuration.",
            )
            return LocalLoginOutcome(status="break_glass_disabled")
        if not break_glass_controller.is_request_address_allowed(request):
            record_auth_event(
                request,
                event_type="break_glass_login_blocked",
                success=False,
                subject_username=username.strip().lower() or None,
                detail="Break-glass local login requires an internal address.",
            )
            return LocalLoginOutcome(status="break_glass_internal_only")

    normalized_username = normalize_username(username)
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
        return LocalLoginOutcome(status="locked_out")

    try:
        user = auth_store.get_local_user_by_username(normalized_username)
    except KeyError:
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
        return LocalLoginOutcome(status="unknown_user")

    if not user.enabled or not verify_password(password, user.password_hash):
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
        return LocalLoginOutcome(status="invalid_credentials", user=user)

    user = auth_store.record_local_user_login(user.user_id)
    assert session_manager is not None

    break_glass_active_until: datetime | None = None
    if identity_mode == "local_single_user" and break_glass_controller is not None:
        break_glass_active_until = break_glass_controller.activate(now=now)
        record_auth_event(
            request,
            event_type="break_glass_activated",
            success=True,
            subject_user_id=user.user_id,
            subject_username=user.username,
            detail=f"Break-glass active until {break_glass_active_until.isoformat()}",
        )

    record_auth_event(
        request,
        event_type="login_succeeded",
        success=True,
        subject_user_id=user.user_id,
        subject_username=user.username,
        detail=(
            f"break_glass_active_until={break_glass_active_until.isoformat()}"
            if break_glass_active_until is not None
            else None
        ),
    )
    issued_session = session_manager.issue_session(user)
    principal = request_principal_from_user(
        user,
        csrf_token=issued_session.csrf_token,
    )
    return LocalLoginOutcome(
        status="success",
        user=user,
        principal=principal,
        issued_session=issued_session,
        break_glass_active_until=break_glass_active_until,
    )


def start_oidc_login(
    *,
    auth_mode: str,
    return_to: str | None,
    oidc_provider: OidcProvider | None,
) -> OidcLoginStartOutcome:
    if auth_mode != "oidc" or oidc_provider is None:
        return OidcLoginStartOutcome(status="auth_disabled")
    try:
        redirect = oidc_provider.build_login_redirect(return_to)
    except (OidcAuthenticationError, httpx.HTTPError):
        return OidcLoginStartOutcome(status="discovery_failed")
    return OidcLoginStartOutcome(status="success", redirect=redirect)


def complete_oidc_callback(
    request: Any,
    *,
    auth_mode: str,
    code: str | None,
    state: str | None,
    error: str | None,
    state_cookie_value: str | None,
    oidc_provider: OidcProvider | None,
    session_manager: SessionManager | None,
    record_auth_event: Callable[..., None],
) -> OidcCallbackOutcome:
    if auth_mode != "oidc" or oidc_provider is None or session_manager is None:
        return OidcCallbackOutcome(
            status="auth_disabled",
            redirect_to="/login?error=oidc-failed",
        )

    if error or not code or not state:
        record_auth_event(
            request,
            event_type="login_failed",
            success=False,
            detail=error or "OIDC callback missing code or state.",
        )
        return OidcCallbackOutcome(
            status="missing_code_or_state",
            redirect_to="/login?error=oidc-failed",
        )

    try:
        principal, return_to = oidc_provider.authenticate_callback(
            code=code,
            state=state,
            cookie_value=state_cookie_value,
        )
    except OidcAuthorizationError as exc:
        record_auth_event(
            request,
            event_type="login_failed",
            success=False,
            detail=str(exc),
        )
        return OidcCallbackOutcome(
            status="unmapped",
            redirect_to="/login?error=oidc-unmapped",
        )
    except (OidcAuthenticationError, httpx.HTTPError) as exc:
        record_auth_event(
            request,
            event_type="login_failed",
            success=False,
            detail=str(exc),
        )
        return OidcCallbackOutcome(
            status="failed",
            redirect_to="/login?error=oidc-failed",
        )

    record_auth_event(
        request,
        event_type="login_succeeded",
        success=True,
        subject_user_id=principal.user_id,
        subject_username=principal.username,
    )
    issued_session = session_manager.issue_session(principal)
    return OidcCallbackOutcome(
        status="success",
        redirect_to=normalize_return_to(return_to),
        principal=principal,
        issued_session=issued_session,
    )


def perform_logout(
    *,
    identity_mode: str,
    principal: AuthenticatedPrincipal | None,
    break_glass_controller: BreakGlassController | None,
    record_auth_event: Callable[..., None],
    request: Any,
) -> LogoutOutcome:
    break_glass_cleared = False
    if principal is not None:
        record_auth_event(
            request,
            event_type="logout",
            success=True,
            actor=principal,
            subject_user_id=principal.user_id,
            subject_username=principal.username,
        )
        if (
            identity_mode == "local_single_user"
            and principal.auth_provider == "local"
            and break_glass_controller is not None
        ):
            break_glass_controller.clear()
            break_glass_cleared = True
            record_auth_event(
                request,
                event_type="break_glass_cleared",
                success=True,
                actor=principal,
                subject_user_id=principal.user_id,
                subject_username=principal.username,
                detail="Break-glass window cleared by logout.",
            )
    return LogoutOutcome(break_glass_cleared=break_glass_cleared)


def build_auth_me_payload(
    *,
    auth_mode: str,
    identity_mode: str,
    principal: AuthenticatedPrincipal | None,
    auth_store: AuthStore,
) -> dict[str, Any] | None:
    if auth_mode == "disabled":
        return {"auth_mode": "disabled", "authenticated": False}
    if principal is None:
        return None
    if principal.auth_provider == "local":
        user = auth_store.get_local_user(principal.user_id)
        serialized_user = serialize_user(user)
    else:
        serialized_user = serialize_authenticated_user(principal)
    return {
        "auth_mode": identity_mode,
        "authenticated": True,
        "user": serialized_user,
        "principal": serialize_principal(principal),
    }
