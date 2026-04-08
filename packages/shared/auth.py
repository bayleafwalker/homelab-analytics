"""Frozen compatibility shim re-exporting public auth symbols.
New runtime code should import platform/shared contracts directly. This module
exists only to preserve legacy call sites and the public export surface.
"""
from __future__ import annotations

from packages.platform.auth.configuration import (
    maybe_bootstrap_local_admin,
    validate_auth_configuration,
)
from packages.platform.auth.crypto import (
    SERVICE_TOKEN_VALUE_PREFIX,
    IssuedServiceToken,
    has_required_service_token_scope,
    hash_password,
    hash_service_token_secret,
    issue_service_token,
    parse_service_token,
    verify_password,
    verify_service_token_secret,
)
from packages.platform.auth.oidc_provider import (
    OIDC_STATE_COOKIE_NAME,
    OIDC_STATE_MAX_AGE_SECONDS,
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcLoginRedirect,
    OidcLoginState,
    OidcProvider,
    build_oidc_provider,
    normalize_return_to,
)
from packages.platform.auth.proxy_provider import (
    ProxyAuthenticationError,
    ProxyAuthorizationError,
    ProxyProvider,
    build_proxy_provider,
)
from packages.platform.auth.role_hierarchy import (
    AuthenticatedPrincipal,
    authenticate_service_token,
    has_required_role,
    principal_from_service_token,
)
from packages.platform.auth.serialization import (
    serialize_authenticated_user,
    serialize_principal,
    serialize_service_token,
    serialize_user,
)
from packages.platform.auth.session_manager import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    IssuedSession,
    SessionManager,
    build_session_manager,
)

__all__ = [
    "maybe_bootstrap_local_admin",
    "validate_auth_configuration",
    "SERVICE_TOKEN_VALUE_PREFIX",
    "IssuedServiceToken",
    "hash_password",
    "hash_service_token_secret",
    "has_required_service_token_scope",
    "issue_service_token",
    "parse_service_token",
    "verify_password",
    "verify_service_token_secret",
    "OIDC_STATE_COOKIE_NAME",
    "OIDC_STATE_MAX_AGE_SECONDS",
    "OidcAuthenticationError",
    "OidcAuthorizationError",
    "OidcLoginRedirect",
    "OidcLoginState",
    "OidcProvider",
    "build_oidc_provider",
    "normalize_return_to",
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
    "CSRF_COOKIE_NAME",
    "SESSION_COOKIE_NAME",
    "SESSION_MAX_AGE_SECONDS",
    "IssuedSession",
    "SessionManager",
    "build_session_manager",
]
