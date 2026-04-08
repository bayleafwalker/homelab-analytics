from __future__ import annotations

from apps.api.auth_policies import (
    API_ROUTE_AUTHORIZATION_LOOKUP,
    required_permission_for_path,
    required_permission_for_request,
    required_role_for_request,
    required_service_token_scope_for_request,
)
from packages.platform.auth.permission_registry import (
    PERMISSION_ADMIN_WRITE,
    PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE,
    PERMISSION_CONTROL_CONFIG_READ,
    PERMISSION_CONTROL_CONFIG_READ_RESOURCE_WILDCARD,
    PERMISSION_CONTROL_CONFIG_WRITE,
    PERMISSION_CONTROL_CONFIG_WRITE_RESOURCE_WILDCARD,
    PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_WILDCARD,
    PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ_DISPATCH_WILDCARD,
    PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ_SCHEDULE_WILDCARD,
    PERMISSION_CONTROL_SCHEDULE_DISPATCHES_WRITE_DISPATCH_WILDCARD,
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
    config_read_resource_permission,
    config_write_resource_permission,
    has_required_permission,
    normalize_permission_grants,
    permissions_for_principal,
    permissions_for_role,
    permissions_for_service_token_scopes,
    publication_audit_publication_permission,
    publication_read_permission,
    run_read_permission,
    run_retry_permission,
    schedule_dispatch_read_dispatch_permission,
    schedule_dispatch_read_schedule_permission,
    schedule_dispatch_write_dispatch_permission,
    source_lineage_run_permission,
    transformation_audit_run_permission,
)
from packages.platform.auth.route_policy_engine import (
    RouteAuthorizationLookup,
    RouteDecision,
    RoutePolicy,
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
    assert PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE in operator
    assert PERMISSION_ADMIN_WRITE in admin


def test_service_scope_permissions_map_to_canonical_permissions() -> None:
    report_scope = permissions_for_service_token_scopes(
        (SERVICE_TOKEN_SCOPE_REPORTS_READ,)
    )
    run_scope = permissions_for_service_token_scopes((SERVICE_TOKEN_SCOPE_RUNS_READ,))
    ingest_scope = permissions_for_service_token_scopes(
        (SERVICE_TOKEN_SCOPE_INGEST_WRITE,)
    )
    admin_scope = permissions_for_service_token_scopes(
        (SERVICE_TOKEN_SCOPE_ADMIN_WRITE,)
    )

    assert report_scope == {PERMISSION_REPORTS_READ}
    assert PERMISSION_RUNS_READ in run_scope
    assert PERMISSION_RUNS_RETRY in ingest_scope
    assert PERMISSION_CONTROL_CONFIG_READ in admin_scope
    assert PERMISSION_CONTROL_CONFIG_WRITE in admin_scope


def test_service_token_permissions_intersect_role_and_scope_grants() -> None:
    token_ctx = PrincipalAuthorizationContext(
        role=UserRole.READER,
        auth_provider="service_token",
        scopes=(SERVICE_TOKEN_SCOPE_ADMIN_WRITE,),
    )

    resolved_permissions = permissions_for_principal(token_ctx)

    assert PERMISSION_ADMIN_WRITE not in resolved_permissions
    assert not has_required_permission(token_ctx, PERMISSION_ADMIN_WRITE)


def test_machine_jwt_scope_permissions_match_service_token_semantics() -> None:
    machine_ctx = PrincipalAuthorizationContext(
        role=UserRole.READER,
        auth_provider="machine_jwt",
        scopes=(SERVICE_TOKEN_SCOPE_ADMIN_WRITE,),
    )

    resolved_permissions = permissions_for_principal(machine_ctx)

    assert PERMISSION_ADMIN_WRITE not in resolved_permissions
    assert not has_required_permission(machine_ctx, PERMISSION_ADMIN_WRITE)


def test_machine_jwt_direct_permissions_are_additive_when_present() -> None:
    machine_ctx = PrincipalAuthorizationContext(
        role=UserRole.READER,
        auth_provider="machine_jwt",
        scopes=(SERVICE_TOKEN_SCOPE_RUNS_READ,),
        granted_permissions=("ingest.write",),
    )

    assert has_required_permission(machine_ctx, PERMISSION_RUNS_READ)
    assert has_required_permission(machine_ctx, PERMISSION_INGEST_WRITE)


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
            "control.schedule_dispatches.read.dispatch.dispatch-001",
            "control.schedule_dispatches.read.dispatch.*",
            "control.schedule_dispatches.read.schedule.finance.*",
            "control.schedule_dispatches.read.schedule.*",
            "control.schedule_dispatches.write.dispatch.dispatch-001",
            "control.schedule_dispatches.write.dispatch.*",
            "control.config.read.resource.source-systems.source-001",
            "control.config.read.resource.source-systems.*",
            "control.config.write.resource.execution-schedules.schedule-001.archive",
            "control.config.write.resource.execution-schedules.*",
            "control.publication_audit.read.publication.invalid key",
            "transformation.audit.read.run.run-001",
            "transformation.audit.read.run.finance.*",
            "transformation.audit.read.run.*",
        ]
    )

    assert normalized == (
        "control.config.read.resource.source-systems.*",
        "control.config.read.resource.source-systems.source-001",
        "control.config.write.resource.execution-schedules.*",
        "control.config.write.resource.execution-schedules.schedule-001.archive",
        "control.publication_audit.read.publication.*",
        "control.publication_audit.read.publication.monthly-cashflow",
        "control.publication_audit.read.publication.reports.*",
        "control.schedule_dispatches.read.dispatch.*",
        "control.schedule_dispatches.read.dispatch.dispatch-001",
        "control.schedule_dispatches.read.schedule.*",
        "control.schedule_dispatches.read.schedule.finance.*",
        "control.schedule_dispatches.write.dispatch.*",
        "control.schedule_dispatches.write.dispatch.dispatch-001",
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
        schedule_dispatch_read_schedule_permission("sched-001"),
    )
    assert has_required_permission(
        reader_ctx,
        schedule_dispatch_read_dispatch_permission("dispatch-001"),
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
    assert has_required_permission(
        reader_ctx,
        PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ_SCHEDULE_WILDCARD,
    )
    assert has_required_permission(
        reader_ctx,
        PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ_DISPATCH_WILDCARD,
    )


def test_operator_role_implies_control_schedule_dispatch_write_permissions() -> None:
    operator_ctx = PrincipalAuthorizationContext(
        role=UserRole.OPERATOR,
        auth_provider="local",
    )

    assert has_required_permission(
        operator_ctx,
        schedule_dispatch_write_dispatch_permission("dispatch-001"),
    )
    assert has_required_permission(
        operator_ctx,
        PERMISSION_CONTROL_SCHEDULE_DISPATCHES_WRITE_DISPATCH_WILDCARD,
    )


def test_admin_role_implies_control_config_resource_permissions() -> None:
    admin_ctx = PrincipalAuthorizationContext(
        role=UserRole.ADMIN,
        auth_provider="local",
    )

    assert has_required_permission(
        admin_ctx,
        config_read_resource_permission("source-systems.source-001"),
    )
    assert has_required_permission(
        admin_ctx,
        config_write_resource_permission("execution-schedules.schedule-001.archive"),
    )
    assert has_required_permission(
        admin_ctx,
        PERMISSION_CONTROL_CONFIG_READ_RESOURCE_WILDCARD,
    )
    assert has_required_permission(
        admin_ctx,
        PERMISSION_CONTROL_CONFIG_WRITE_RESOURCE_WILDCARD,
    )
    assert has_required_permission(
        admin_ctx,
        PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE,
    )


def test_path_permission_mapping_matches_current_auth_surfaces() -> None:
    assert required_permission_for_path(API_ROUTE_AUTHORIZATION_LOOKUP, "/health") is None
    assert required_permission_for_path(API_ROUTE_AUTHORIZATION_LOOKUP, "/reports/monthly-cashflow") == publication_read_permission(
        "monthly-cashflow"
    )
    assert required_permission_for_path(API_ROUTE_AUTHORIZATION_LOOKUP, "/reports/loan-schedule/loan-001") == publication_read_permission(
        "loan-schedule"
    )
    assert required_permission_for_path(API_ROUTE_AUTHORIZATION_LOOKUP, "/runs") == PERMISSION_RUNS_READ
    assert required_permission_for_path(API_ROUTE_AUTHORIZATION_LOOKUP, "/runs/run-1") == run_read_permission("run-1")
    assert required_permission_for_path(API_ROUTE_AUTHORIZATION_LOOKUP, "/runs/run-1/retry") == run_retry_permission("run-1")
    assert required_permission_for_path(API_ROUTE_AUTHORIZATION_LOOKUP, "/ingest") == PERMISSION_INGEST_WRITE
    assert required_permission_for_path(API_ROUTE_AUTHORIZATION_LOOKUP, "/config/source-systems") == PERMISSION_ADMIN_WRITE


def test_request_permission_mapping_supports_control_asset_scopes() -> None:
    assert required_permission_for_request(
        API_ROUTE_AUTHORIZATION_LOOKUP,
        "/control/source-lineage",
        {"run_id": "run-001"},
    ) == source_lineage_run_permission("run-001")
    assert required_permission_for_request(
        API_ROUTE_AUTHORIZATION_LOOKUP,
        "/control/publication-audit",
        {"publication_key": "monthly-cashflow"},
    ) == publication_audit_publication_permission("monthly-cashflow")
    assert (
        required_permission_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/control/source-lineage",
            {},
        )
        == "control.source_lineage.read"
    )
    assert (
        required_permission_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/control/publication-audit",
            {},
        )
        == "control.publication_audit.read"
    )
    assert required_permission_for_request(
        API_ROUTE_AUTHORIZATION_LOOKUP,
        "/transformation-audit",
        {"run_id": "run-001"},
    ) == transformation_audit_run_permission("run-001")
    assert (
        required_permission_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/transformation-audit",
            {},
        )
        == "transformation.audit.read"
    )


def test_route_authorization_lookup_supports_injected_policy_catalogs() -> None:
    lookup = RouteAuthorizationLookup(
        (
            RoutePolicy(
                exact_paths=("/custom/report",),
                request_decision=RouteDecision(
                    role=UserRole.READER,
                    permission=PERMISSION_REPORTS_READ,
                    scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
                ),
            ),
        )
    )

    assert lookup.required_role_for_request("/custom/report", "GET") == UserRole.READER
    assert lookup.required_permission_for_request("/custom/report", method="GET") == PERMISSION_REPORTS_READ
    assert (
        lookup.required_service_token_scope_for_request("/custom/report", "GET")
        == SERVICE_TOKEN_SCOPE_REPORTS_READ
    )


def test_request_policy_mapping_covers_previously_unmapped_api_surfaces() -> None:
    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/config/source-systems", "GET") == UserRole.ADMIN
    assert required_permission_for_request(
        API_ROUTE_AUTHORIZATION_LOOKUP,
        "/config/source-systems",
        method="GET",
    ) == "control.config.read.resource.source-systems"
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/config/source-systems", "GET")
        == "admin:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/config/source-systems/source-001", "PATCH") == UserRole.ADMIN
    assert required_permission_for_request(
        API_ROUTE_AUTHORIZATION_LOOKUP,
        "/config/source-systems/source-001",
        method="PATCH",
    ) == "control.config.write.resource.source-systems.source-001"
    assert (
        required_service_token_scope_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/config/source-systems/source-001",
            "PATCH",
        )
        == "admin:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/control/schedule-dispatches", "GET") == UserRole.READER
    assert required_permission_for_request(
        API_ROUTE_AUTHORIZATION_LOOKUP,
        "/control/schedule-dispatches",
        {"schedule_id": "sched-001"},
        method="GET",
    ) == schedule_dispatch_read_schedule_permission("sched-001")
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/control/schedule-dispatches", "GET")
        == "runs:read"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/control/schedule-dispatches", "POST") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/control/schedule-dispatches", method="POST")
        == "control.schedule_dispatches.write"
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/control/schedule-dispatches", "POST")
        == "ingest:write"
    )

    assert (
        required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/control/schedule-dispatches/dispatch-001", "GET")
        == UserRole.READER
    )
    assert required_permission_for_request(
        API_ROUTE_AUTHORIZATION_LOOKUP,
        "/control/schedule-dispatches/dispatch-001",
        method="GET",
    ) == schedule_dispatch_read_dispatch_permission("dispatch-001")
    assert (
        required_service_token_scope_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/control/schedule-dispatches/dispatch-001",
            "GET",
        )
        == "runs:read"
    )

    assert (
        required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/control/schedule-dispatches/dispatch-001/retry", "POST")
        == UserRole.OPERATOR
    )
    assert required_permission_for_request(
        API_ROUTE_AUTHORIZATION_LOOKUP,
        "/control/schedule-dispatches/dispatch-001/retry",
        method="POST",
    ) == schedule_dispatch_write_dispatch_permission("dispatch-001")
    assert (
        required_service_token_scope_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/control/schedule-dispatches/dispatch-001/retry",
            "POST",
        )
        == "ingest:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/contracts/publications", "GET") == UserRole.READER
    assert required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/contracts/publications", method="GET") == "reports.read"
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/contracts/publications", "GET")
        == "reports:read"
    )
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/contracts/publication-index", method="GET")
        == "reports.read"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios", "GET") == UserRole.READER
    assert required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios", method="GET") == "reports.read"
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios", "GET")
        == "reports:read"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets", "GET") == UserRole.READER
    assert required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets", method="GET") == "reports.read"
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets", "GET")
        == "reports:read"
    )
    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets", "POST") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets", method="POST")
        == "ingest.write"
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets", "POST")
        == "ingest:write"
    )
    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001", "PATCH") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001", method="PATCH")
        == "ingest.write"
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001", "PATCH")
        == "ingest:write"
    )
    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001/restore", "POST") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001/restore", method="POST")
        == "ingest.write"
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001/restore", "POST")
        == "ingest:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/income-change", "POST") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/income-change", method="POST")
        == "ingest.write"
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/income-change", "POST")
        == "ingest:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/tariff-shock", "POST") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/tariff-shock", method="POST")
        == "ingest.write"
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/tariff-shock", "POST")
        == "ingest:write"
    )

    assert (
        required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/homelab-cost-benefit", "POST")
        == UserRole.OPERATOR
    )
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/homelab-cost-benefit", method="POST")
        == "ingest.write"
    )
    assert (
        required_service_token_scope_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/api/scenarios/homelab-cost-benefit",
            "POST",
        )
        == "ingest:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/scn-001", "DELETE") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/scn-001", method="DELETE")
        == "ingest.write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001", "DELETE") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001", method="DELETE")
        == "ingest.write"
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/scenarios/compare-sets/cs-001", "DELETE")
        == "ingest:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/assistant/answer", "GET") == UserRole.READER
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/assistant/answer", method="GET")
        == PERMISSION_REPORTS_READ
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/assistant/answer", "GET")
        == "reports:read"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/entities", "GET") == UserRole.READER
    assert required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/entities", method="GET") == "runs.read"
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/entities", "GET")
        == "runs:read"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/actions/proposals", "GET") == UserRole.READER
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/actions/proposals", method="GET")
        == "runs.read"
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/actions/proposals", "GET")
        == "runs:read"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/actions/proposals", "POST") == UserRole.OPERATOR
    assert (
        required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/actions/proposals", method="POST")
        == PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE
    )
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/actions/proposals", "POST")
        == "admin:write"
    )

    assert (
        required_role_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/api/ha/actions/proposals/approval_device_control/approve",
            "POST",
        )
        == UserRole.OPERATOR
    )
    assert (
        required_permission_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/api/ha/actions/proposals/approval_device_control/approve",
            method="POST",
        )
        == PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE
    )
    assert (
        required_service_token_scope_for_request(
            API_ROUTE_AUTHORIZATION_LOOKUP,
            "/api/ha/actions/proposals/approval_device_control/approve",
            "POST",
        )
        == "admin:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/ingest", "POST") == UserRole.OPERATOR
    assert required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/ingest", method="POST") == "ingest.write"
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/ha/ingest", "POST")
        == "ingest:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/categories", "GET") == UserRole.READER
    assert required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/categories", method="GET") == "reports.read"
    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/categories", "POST") == UserRole.ADMIN
    assert required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/categories", method="POST") == "admin.write"
    assert (
        required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/api/categories", "POST")
        == "admin:write"
    )

    assert required_role_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/functions", "GET") == UserRole.ADMIN
    assert required_permission_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/functions", method="GET") == "admin.write"
    assert required_service_token_scope_for_request(API_ROUTE_AUTHORIZATION_LOOKUP, "/functions", "GET") == "admin:write"
