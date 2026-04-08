"""Platform auth package — policy, session, OIDC, and crypto for the shared runtime."""
from __future__ import annotations

from importlib import import_module

from packages.platform.auth.contracts import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_PERMISSION_MAP,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    SERVICE_TOKEN_SCOPES,
    UserRole,
    normalize_service_token_scopes,
)
from packages.platform.auth.crypto import (
    SERVICE_TOKEN_VALUE_PREFIX,
    IssuedServiceToken,
    has_required_service_token_scope,
    hash_password,
    issue_service_token,
    parse_service_token,
    verify_password,
    verify_service_token_secret,
)

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "maybe_bootstrap_local_admin": (
        "packages.platform.auth.configuration",
        "maybe_bootstrap_local_admin",
    ),
    "validate_auth_configuration": (
        "packages.platform.auth.configuration",
        "validate_auth_configuration",
    ),
    "OidcAuthenticationError": (
        "packages.platform.auth.oidc_provider",
        "OidcAuthenticationError",
    ),
    "OidcAuthorizationError": (
        "packages.platform.auth.oidc_provider",
        "OidcAuthorizationError",
    ),
    "OidcProvider": ("packages.platform.auth.oidc_provider", "OidcProvider"),
    "build_oidc_provider": (
        "packages.platform.auth.oidc_provider",
        "build_oidc_provider",
    ),
    "MachineJwtAuthenticationError": (
        "packages.platform.auth.machine_jwt_provider",
        "MachineJwtAuthenticationError",
    ),
    "MachineJwtAuthorizationError": (
        "packages.platform.auth.machine_jwt_provider",
        "MachineJwtAuthorizationError",
    ),
    "MachineJwtProvider": (
        "packages.platform.auth.machine_jwt_provider",
        "MachineJwtProvider",
    ),
    "build_machine_jwt_provider": (
        "packages.platform.auth.machine_jwt_provider",
        "build_machine_jwt_provider",
    ),
    "ProxyAuthenticationError": (
        "packages.platform.auth.proxy_provider",
        "ProxyAuthenticationError",
    ),
    "ProxyAuthorizationError": (
        "packages.platform.auth.proxy_provider",
        "ProxyAuthorizationError",
    ),
    "ProxyProvider": ("packages.platform.auth.proxy_provider", "ProxyProvider"),
    "build_proxy_provider": (
        "packages.platform.auth.proxy_provider",
        "build_proxy_provider",
    ),
    "AuthenticatedPrincipal": (
        "packages.platform.auth.role_hierarchy",
        "AuthenticatedPrincipal",
    ),
    "authenticate_service_token": (
        "packages.platform.auth.role_hierarchy",
        "authenticate_service_token",
    ),
    "has_required_role": ("packages.platform.auth.role_hierarchy", "has_required_role"),
    "principal_from_service_token": (
        "packages.platform.auth.role_hierarchy",
        "principal_from_service_token",
    ),
    "serialize_authenticated_user": (
        "packages.platform.auth.serialization",
        "serialize_authenticated_user",
    ),
    "serialize_principal": (
        "packages.platform.auth.serialization",
        "serialize_principal",
    ),
    "serialize_service_token": (
        "packages.platform.auth.serialization",
        "serialize_service_token",
    ),
    "serialize_user": ("packages.platform.auth.serialization", "serialize_user"),
    "IssuedSession": ("packages.platform.auth.session_manager", "IssuedSession"),
    "SessionManager": ("packages.platform.auth.session_manager", "SessionManager"),
    "build_session_manager": (
        "packages.platform.auth.session_manager",
        "build_session_manager",
    ),
}


def __getattr__(name: str) -> object:
    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "UserRole",
    "SERVICE_TOKEN_SCOPE_REPORTS_READ",
    "SERVICE_TOKEN_SCOPE_RUNS_READ",
    "SERVICE_TOKEN_SCOPE_INGEST_WRITE",
    "SERVICE_TOKEN_SCOPE_ADMIN_WRITE",
    "SERVICE_TOKEN_SCOPES",
    "SERVICE_TOKEN_SCOPE_PERMISSION_MAP",
    "normalize_service_token_scopes",
    "maybe_bootstrap_local_admin",
    "validate_auth_configuration",
    "SERVICE_TOKEN_VALUE_PREFIX",
    "IssuedServiceToken",
    "hash_password",
    "has_required_service_token_scope",
    "issue_service_token",
    "parse_service_token",
    "verify_password",
    "verify_service_token_secret",
    "OidcAuthenticationError",
    "OidcAuthorizationError",
    "OidcProvider",
    "build_oidc_provider",
    "MachineJwtAuthenticationError",
    "MachineJwtAuthorizationError",
    "MachineJwtProvider",
    "build_machine_jwt_provider",
    "ProxyAuthenticationError",
    "ProxyAuthorizationError",
    "ProxyProvider",
    "build_proxy_provider",
    "AuthenticatedPrincipal",
    "authenticate_service_token",
    "has_required_role",
    "principal_from_service_token",
    "serialize_authenticated_user",
    "serialize_principal",
    "serialize_service_token",
    "serialize_user",
    "IssuedSession",
    "SessionManager",
    "build_session_manager",
]
