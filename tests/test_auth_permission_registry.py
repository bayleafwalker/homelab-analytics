from __future__ import annotations

from packages.platform.auth.permission_registry import (
    PERMISSION_ADMIN_WRITE,
    PERMISSION_INGEST_WRITE,
    PERMISSION_REPORTS_READ,
    PERMISSION_RUNS_READ,
    PERMISSION_RUNS_RETRY,
    PrincipalAuthorizationContext,
    has_required_permission,
    normalize_permission_grants,
    permissions_for_principal,
    permissions_for_role,
    permissions_for_service_token_scopes,
)
from packages.platform.auth.scope_authorization import required_permission_for_path
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    UserRole,
)


def test_role_permission_bundles_follow_reader_operator_admin_hierarchy() -> None:
    reader = permissions_for_role(UserRole.READER)
    operator = permissions_for_role(UserRole.OPERATOR)
    admin = permissions_for_role(UserRole.ADMIN)

    assert reader.issubset(operator)
    assert operator.issubset(admin)
    assert PERMISSION_REPORTS_READ in reader
    assert PERMISSION_INGEST_WRITE not in reader
    assert PERMISSION_INGEST_WRITE in operator
    assert PERMISSION_ADMIN_WRITE in admin


def test_service_scope_permissions_map_to_canonical_permissions() -> None:
    report_scope = permissions_for_service_token_scopes(
        (SERVICE_TOKEN_SCOPE_REPORTS_READ,)
    )
    run_scope = permissions_for_service_token_scopes((SERVICE_TOKEN_SCOPE_RUNS_READ,))
    ingest_scope = permissions_for_service_token_scopes(
        (SERVICE_TOKEN_SCOPE_INGEST_WRITE,)
    )

    assert report_scope == {PERMISSION_REPORTS_READ}
    assert PERMISSION_RUNS_READ in run_scope
    assert PERMISSION_RUNS_RETRY in ingest_scope


def test_service_token_permissions_intersect_role_and_scope_grants() -> None:
    token_ctx = PrincipalAuthorizationContext(
        role=UserRole.READER,
        auth_provider="service_token",
        scopes=(SERVICE_TOKEN_SCOPE_ADMIN_WRITE,),
    )

    resolved_permissions = permissions_for_principal(token_ctx)

    assert PERMISSION_ADMIN_WRITE not in resolved_permissions
    assert not has_required_permission(token_ctx, PERMISSION_ADMIN_WRITE)


def test_local_principal_permissions_follow_role_bundle_only() -> None:
    local_ctx = PrincipalAuthorizationContext(
        role=UserRole.OPERATOR,
        auth_provider="local",
    )

    assert has_required_permission(local_ctx, PERMISSION_INGEST_WRITE)
    assert not has_required_permission(local_ctx, PERMISSION_ADMIN_WRITE)


def test_explicit_principal_permission_grants_are_normalized_and_additive() -> None:
    oidc_ctx = PrincipalAuthorizationContext(
        role=UserRole.READER,
        auth_provider="oidc",
        granted_permissions=(" ingest.write ", "UNKNOWN.PERMISSION", "runs.read"),
    )

    normalized = normalize_permission_grants(
        [" ingest.write ", "UNKNOWN.PERMISSION", "runs.read"]
    )

    assert normalized == (PERMISSION_INGEST_WRITE, PERMISSION_RUNS_READ)
    assert has_required_permission(oidc_ctx, PERMISSION_INGEST_WRITE)


def test_path_permission_mapping_matches_current_auth_surfaces() -> None:
    assert required_permission_for_path("/health") is None
    assert required_permission_for_path("/reports/monthly-cashflow") == PERMISSION_REPORTS_READ
    assert required_permission_for_path("/runs") == PERMISSION_RUNS_READ
    assert required_permission_for_path("/runs/run-1/retry") == PERMISSION_RUNS_RETRY
    assert required_permission_for_path("/ingest") == PERMISSION_INGEST_WRITE
    assert required_permission_for_path("/config/source-systems") == PERMISSION_ADMIN_WRITE
