from __future__ import annotations

from packages.platform.auth.permission_registry import (
    PERMISSION_ADMIN_WRITE,
    PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_WILDCARD,
    PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_WILDCARD,
    PERMISSION_INGEST_WRITE,
    PERMISSION_REPORTS_READ,
    PERMISSION_REPORTS_READ_PUBLICATION_WILDCARD,
    PERMISSION_RUNS_READ,
    PERMISSION_RUNS_READ_RUN_WILDCARD,
    PERMISSION_RUNS_RETRY,
    PERMISSION_RUNS_RETRY_RUN_WILDCARD,
    PERMISSION_TRANSFORMATION_AUDIT_RUN_WILDCARD,
    PrincipalAuthorizationContext,
    has_required_permission,
    normalize_permission_grants,
    permissions_for_principal,
    permissions_for_role,
    permissions_for_service_token_scopes,
    publication_audit_publication_permission,
    publication_read_permission,
    run_read_permission,
    run_retry_permission,
    source_lineage_run_permission,
    transformation_audit_run_permission,
)
from packages.platform.auth.scope_authorization import (
    required_permission_for_path,
    required_permission_for_request,
)
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


def test_permission_normalization_accepts_publication_permissions_and_wildcards() -> None:
    normalized = normalize_permission_grants(
        [
            "reports.read.publication.monthly-cashflow",
            "reports.read.publication.finance.*",
            "reports.read.publication.*",
            "reports.read.publication.invalid key",
        ]
    )

    assert normalized == (
        "reports.read.publication.*",
        "reports.read.publication.finance.*",
        "reports.read.publication.monthly-cashflow",
    )


def test_permission_normalization_accepts_run_permissions_and_wildcards() -> None:
    normalized = normalize_permission_grants(
        [
            "runs.read.run.run-001",
            "runs.read.run.batch.*",
            "runs.read.run.*",
            "runs.retry.run.run-001",
            "runs.retry.run.ops.*",
            "runs.retry.run.*",
            "runs.read.run.invalid key",
        ]
    )

    assert normalized == (
        "runs.read.run.*",
        "runs.read.run.batch.*",
        "runs.read.run.run-001",
        "runs.retry.run.*",
        "runs.retry.run.ops.*",
        "runs.retry.run.run-001",
    )


def test_permission_normalization_accepts_control_asset_permissions_and_wildcards() -> None:
    normalized = normalize_permission_grants(
        [
            "control.source_lineage.read.run.run-001",
            "control.source_lineage.read.run.finance.*",
            "control.source_lineage.read.run.*",
            "control.publication_audit.read.publication.monthly-cashflow",
            "control.publication_audit.read.publication.reports.*",
            "control.publication_audit.read.publication.*",
            "control.publication_audit.read.publication.invalid key",
            "transformation.audit.read.run.run-001",
            "transformation.audit.read.run.finance.*",
            "transformation.audit.read.run.*",
        ]
    )

    assert normalized == (
        "control.publication_audit.read.publication.*",
        "control.publication_audit.read.publication.monthly-cashflow",
        "control.publication_audit.read.publication.reports.*",
        "control.source_lineage.read.run.*",
        "control.source_lineage.read.run.finance.*",
        "control.source_lineage.read.run.run-001",
        "transformation.audit.read.run.*",
        "transformation.audit.read.run.finance.*",
        "transformation.audit.read.run.run-001",
    )


def test_permission_bound_principal_uses_explicit_grants_only() -> None:
    ctx = PrincipalAuthorizationContext(
        role=UserRole.READER,
        auth_provider="oidc",
        granted_permissions=("reports.read.publication.monthly-cashflow",),
        permission_bound=True,
    )

    assert has_required_permission(
        ctx,
        publication_read_permission("monthly-cashflow"),
    )
    assert not has_required_permission(
        ctx,
        publication_read_permission("budget-variance"),
    )


def test_reader_role_implies_publication_read_permissions() -> None:
    reader_ctx = PrincipalAuthorizationContext(
        role=UserRole.READER,
        auth_provider="local",
    )

    assert has_required_permission(
        reader_ctx,
        publication_read_permission("monthly-cashflow"),
    )
    assert has_required_permission(reader_ctx, PERMISSION_REPORTS_READ_PUBLICATION_WILDCARD)


def test_operator_role_implies_run_asset_permissions() -> None:
    operator_ctx = PrincipalAuthorizationContext(
        role=UserRole.OPERATOR,
        auth_provider="local",
    )

    assert has_required_permission(
        operator_ctx,
        run_read_permission("run-001"),
    )
    assert has_required_permission(
        operator_ctx,
        run_retry_permission("run-001"),
    )
    assert has_required_permission(operator_ctx, PERMISSION_RUNS_READ_RUN_WILDCARD)
    assert has_required_permission(operator_ctx, PERMISSION_RUNS_RETRY_RUN_WILDCARD)


def test_reader_role_implies_control_asset_permissions() -> None:
    reader_ctx = PrincipalAuthorizationContext(
        role=UserRole.READER,
        auth_provider="local",
    )

    assert has_required_permission(
        reader_ctx,
        source_lineage_run_permission("run-001"),
    )
    assert has_required_permission(
        reader_ctx,
        publication_audit_publication_permission("monthly-cashflow"),
    )
    assert has_required_permission(
        reader_ctx,
        transformation_audit_run_permission("run-001"),
    )
    assert has_required_permission(
        reader_ctx,
        PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_WILDCARD,
    )
    assert has_required_permission(
        reader_ctx,
        PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_WILDCARD,
    )
    assert has_required_permission(
        reader_ctx,
        PERMISSION_TRANSFORMATION_AUDIT_RUN_WILDCARD,
    )


def test_path_permission_mapping_matches_current_auth_surfaces() -> None:
    assert required_permission_for_path("/health") is None
    assert required_permission_for_path("/reports/monthly-cashflow") == publication_read_permission(
        "monthly-cashflow"
    )
    assert required_permission_for_path("/reports/loan-schedule/loan-001") == publication_read_permission(
        "loan-schedule"
    )
    assert required_permission_for_path("/runs") == PERMISSION_RUNS_READ
    assert required_permission_for_path("/runs/run-1") == run_read_permission("run-1")
    assert required_permission_for_path("/runs/run-1/retry") == run_retry_permission("run-1")
    assert required_permission_for_path("/ingest") == PERMISSION_INGEST_WRITE
    assert required_permission_for_path("/config/source-systems") == PERMISSION_ADMIN_WRITE


def test_request_permission_mapping_supports_control_asset_scopes() -> None:
    assert required_permission_for_request(
        "/control/source-lineage",
        {"run_id": "run-001"},
    ) == source_lineage_run_permission("run-001")
    assert required_permission_for_request(
        "/control/publication-audit",
        {"publication_key": "monthly-cashflow"},
    ) == publication_audit_publication_permission("monthly-cashflow")
    assert (
        required_permission_for_request(
            "/control/source-lineage",
            {},
        )
        == "control.source_lineage.read"
    )
    assert (
        required_permission_for_request(
            "/control/publication-audit",
            {},
        )
        == "control.publication_audit.read"
    )
    assert required_permission_for_request(
        "/transformation-audit",
        {"run_id": "run-001"},
    ) == transformation_audit_run_permission("run-001")
    assert (
        required_permission_for_request(
            "/transformation-audit",
            {},
        )
        == "transformation.audit.read"
    )
