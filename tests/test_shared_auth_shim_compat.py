"""Compatibility canary for packages.shared.auth shim.

This file exists to assert that the shim's public surface remains intact.
It is the deliberate canary: if the shim is broken, renamed, or has symbols
removed, these tests fail loudly before any consumers notice.

Do not migrate these imports to platform.auth.* — that would defeat the purpose.
All other tests may migrate opportunistically; this file must not.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.architecture]

EXPECTED_NAMES = [
    # configuration
    "maybe_bootstrap_local_admin",
    "validate_auth_configuration",
    # crypto
    "SERVICE_TOKEN_VALUE_PREFIX",
    "IssuedServiceToken",
    "hash_password",
    "hash_service_token_secret",
    "has_required_service_token_scope",
    "issue_service_token",
    "parse_service_token",
    "verify_password",
    "verify_service_token_secret",
    # oidc
    "OIDC_STATE_COOKIE_NAME",
    "OIDC_STATE_MAX_AGE_SECONDS",
    "OidcAuthenticationError",
    "OidcAuthorizationError",
    "OidcLoginRedirect",
    "OidcLoginState",
    "OidcProvider",
    "build_oidc_provider",
    "normalize_return_to",
    # role hierarchy
    "AuthenticatedPrincipal",
    "authenticate_service_token",
    "has_required_role",
    "principal_from_service_token",
    # serialization
    "serialize_authenticated_user",
    "serialize_principal",
    "serialize_service_token",
    "serialize_user",
    # session
    "CSRF_COOKIE_NAME",
    "SESSION_COOKIE_NAME",
    "SESSION_MAX_AGE_SECONDS",
    "IssuedSession",
    "SessionManager",
    "build_session_manager",
]


@pytest.mark.parametrize("name", EXPECTED_NAMES)
def test_shim_exports_expected_name(name: str) -> None:
    import packages.shared.auth as shim

    assert hasattr(shim, name), (
        f"packages.shared.auth no longer exports '{name}'. "
        f"Update the shim or migrate consumers before removing it."
    )


def test_shim_all_is_complete() -> None:
    import packages.shared.auth as shim

    missing_from_all = [n for n in EXPECTED_NAMES if n not in shim.__all__]
    assert not missing_from_all, (
        f"These names are exported but missing from __all__: {missing_from_all}"
    )
