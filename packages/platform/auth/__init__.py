"""Platform auth package — policy, session, OIDC, and crypto for the shared runtime."""
from packages.platform.auth.configuration import (
    maybe_bootstrap_local_admin,
    validate_auth_configuration,
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
from packages.platform.auth.machine_jwt_provider import (
    MachineJwtAuthenticationError,
    MachineJwtAuthorizationError,
    MachineJwtProvider,
    build_machine_jwt_provider,
)
from packages.platform.auth.oidc_provider import (
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcProvider,
    build_oidc_provider,
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
