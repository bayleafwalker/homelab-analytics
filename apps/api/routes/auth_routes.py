"""Auth route coordinator — delegates to focused sub-modules.

Sub-modules:
- auth_session_routes: session/OIDC login, callback, logout, /auth/me
- auth_management_routes: user CRUD, service tokens, /control/auth-audit
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from fastapi import FastAPI, Request

from apps.api.routes.auth_management_routes import register_auth_management_routes
from apps.api.routes.auth_session_routes import register_auth_session_routes
from packages.platform.auth.oidc_provider import OidcProvider
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.platform.auth.session_manager import SessionManager
from packages.storage.auth_store import AuthStore
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
    register_auth_session_routes(
        app,
        resolved_auth_mode=resolved_auth_mode,
        resolved_auth_store=resolved_auth_store,
        resolved_session_manager=resolved_session_manager,
        resolved_oidc_provider=resolved_oidc_provider,
        cookie_secure_for_request=cookie_secure_for_request,
        record_auth_event=record_auth_event,
        locked_out_until=locked_out_until,
        request_principal_from_user=request_principal_from_user,
    )
    register_auth_management_routes(
        app,
        resolved_auth_store=resolved_auth_store,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        record_auth_event=record_auth_event,
        to_jsonable=to_jsonable,
    )
