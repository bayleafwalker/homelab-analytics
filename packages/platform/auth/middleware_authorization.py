"""Request-level authorization evaluation for the API auth middleware."""
from __future__ import annotations

from fastapi.responses import JSONResponse

from packages.platform.auth.contracts import UserRole
from packages.platform.auth.permission_registry import (
    PrincipalAuthorizationContext,
    has_required_permission,
)
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal, has_required_role
from packages.platform.auth.crypto import has_required_service_token_scope


def authorize_request(
    *,
    principal: AuthenticatedPrincipal | None,
    required_role: UserRole | None,
    required_scope: str | None,
    required_permission: str | None,
    enable_unsafe_admin: bool,
    authentication_required_detail: str,
) -> JSONResponse | None:
    if required_role is None:
        return None
    admin_bypass = enable_unsafe_admin and required_role == UserRole.ADMIN
    if principal is None and not admin_bypass:
        return JSONResponse(
            status_code=401,
            content={"detail": authentication_required_detail},
        )
    principal_has_required_permission = (
        principal is not None
        and has_required_permission(
            PrincipalAuthorizationContext(
                role=principal.role,
                auth_provider=principal.auth_provider,
                scopes=principal.scopes,
                granted_permissions=principal.permissions,
                permission_bound=principal.permission_bound,
            ),
            required_permission,
        )
    )
    if (
        principal is not None
        and not has_required_role(principal.role, required_role)
        and not principal_has_required_permission
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": f"{required_role.value} role required."},
        )
    if (
        principal is not None
        and principal.auth_provider in {"service_token", "machine_jwt"}
        and not has_required_service_token_scope(principal.scopes, required_scope)
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": f"{required_scope or 'required'} scope required."},
        )
    if principal is not None and not principal_has_required_permission:
        return JSONResponse(
            status_code=403,
            content={"detail": f"{required_permission or 'required'} permission required."},
        )
    return None
