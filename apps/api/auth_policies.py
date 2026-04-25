"""App-owned authorization declarations for the API surface."""
from __future__ import annotations

from collections.abc import Callable, Mapping

from packages.platform.auth.contracts import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_HA_BRIDGE_INGEST,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    UserRole,
)
from packages.platform.auth.permission_registry import (
    PERMISSION_ADMIN_WRITE,
    PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE,
    PERMISSION_CONTROL_CONFIG_READ,
    PERMISSION_CONTROL_CONFIG_WRITE,
    PERMISSION_CONTROL_POLICY_READ,
    PERMISSION_CONTROL_POLICY_WRITE,
    PERMISSION_CONTROL_PUBLICATION_AUDIT_READ,
    PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ,
    PERMISSION_CONTROL_SCHEDULE_DISPATCHES_WRITE,
    PERMISSION_CONTROL_SOURCE_LINEAGE_READ,
    PERMISSION_INGEST_WRITE,
    PERMISSION_REPORTS_READ,
    PERMISSION_RUNS_READ,
    PERMISSION_RUNS_RETRY,
    PERMISSION_TRANSFORMATION_AUDIT_READ,
    config_read_resource_permission,
    config_write_resource_permission,
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
    RouteContext,
    RouteDecision,
    RoutePolicy,
)
from packages.platform.auth.route_policy_engine import (
    static_route_decision as _static_decision,
)


def _permission_from_suffix(
    *,
    prefix: str,
    factory: Callable[[str], str | None],
    fallback: str,
) -> Callable[[RouteContext], str | None]:
    def resolver(context: RouteContext) -> str | None:
        suffix = context.path.removeprefix(prefix).strip("/")
        if not suffix:
            return fallback
        return factory(suffix) or fallback

    return resolver


def _permission_from_query_param(
    *,
    parameter: str,
    factory: Callable[[str], str | None],
    fallback: str,
) -> Callable[[RouteContext], str | None]:
    def resolver(context: RouteContext) -> str | None:
        value = (context.query_params.get(parameter, "") or "").strip()
        if not value:
            return fallback
        return factory(value) or fallback

    return resolver


def _schedule_dispatches_request_permission(context: RouteContext) -> str | None:
    if context.method == "GET":
        schedule_id = (context.query_params.get("schedule_id", "") or "").strip()
        if schedule_id:
            return (
                schedule_dispatch_read_schedule_permission(schedule_id)
                or PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ
            )
        return PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ
    return PERMISSION_CONTROL_SCHEDULE_DISPATCHES_WRITE


def _schedule_dispatches_request_role(context: RouteContext) -> UserRole | None:
    return UserRole.READER if context.method == "GET" else UserRole.OPERATOR


def _schedule_dispatch_item_permission(context: RouteContext) -> str | None:
    dispatch_id = context.path.removeprefix("/control/schedule-dispatches/").strip("/")
    if not dispatch_id:
        return PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ
    if dispatch_id.endswith("/retry"):
        dispatch_id = dispatch_id.removesuffix("/retry").strip("/")
        return (
            schedule_dispatch_write_dispatch_permission(dispatch_id)
            or PERMISSION_CONTROL_SCHEDULE_DISPATCHES_WRITE
        )
    return (
        schedule_dispatch_read_dispatch_permission(dispatch_id)
        or PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ
    )


def _schedule_dispatch_item_role(context: RouteContext) -> UserRole | None:
    dispatch_id = context.path.removeprefix("/control/schedule-dispatches/").strip("/")
    if dispatch_id.endswith("/retry"):
        return UserRole.OPERATOR
    return UserRole.READER


def _categories_request_role(context: RouteContext) -> UserRole | None:
    return UserRole.READER if context.method == "GET" else UserRole.OPERATOR


def _categories_request_permission(context: RouteContext) -> str | None:
    return PERMISSION_REPORTS_READ if context.method == "GET" else PERMISSION_INGEST_WRITE


def _categories_rules_request_role(context: RouteContext) -> UserRole | None:
    return UserRole.READER if context.method == "GET" else UserRole.ADMIN


def _categories_rules_request_permission(context: RouteContext) -> str | None:
    return PERMISSION_REPORTS_READ if context.method == "GET" else PERMISSION_ADMIN_WRITE


def _categories_overrides_request_role(context: RouteContext) -> UserRole | None:
    return UserRole.READER


def _categories_overrides_request_permission(context: RouteContext) -> str | None:
    return PERMISSION_REPORTS_READ


def _config_resource_key(path: str) -> str | None:
    suffix = path.removeprefix("/config/").strip("/")
    if not suffix:
        return None
    parts = [part.strip().lower() for part in suffix.split("/") if part.strip()]
    if not parts:
        return None
    return ".".join(parts)


def _config_request_role(context: RouteContext) -> UserRole | None:
    return UserRole.ADMIN


def _config_request_permission(context: RouteContext) -> str | None:
    resource_key = _config_resource_key(context.path)
    if context.method in {"GET", "HEAD", "OPTIONS"}:
        if resource_key is None:
            return PERMISSION_CONTROL_CONFIG_READ
        return config_read_resource_permission(resource_key) or PERMISSION_CONTROL_CONFIG_READ
    if resource_key is None:
        return PERMISSION_CONTROL_CONFIG_WRITE
    return config_write_resource_permission(resource_key) or PERMISSION_CONTROL_CONFIG_WRITE


def _scenarios_request_role(context: RouteContext) -> UserRole | None:
    if context.path == "/api/scenarios/compare-sets":
        return UserRole.READER if context.method == "GET" else UserRole.OPERATOR
    if context.path.startswith("/api/scenarios/compare-sets/"):
        if context.method in {"DELETE", "PATCH", "POST", "PUT"}:
            return UserRole.OPERATOR
        return UserRole.READER
    if context.path in {
        "/api/scenarios/loan-what-if",
        "/api/scenarios/income-change",
        "/api/scenarios/expense-shock",
    }:
        return UserRole.OPERATOR
    path_parts = [part for part in context.path.strip("/").split("/") if part]
    if len(path_parts) == 3 and context.method == "DELETE":
        return UserRole.OPERATOR
    return UserRole.READER


def _scenarios_request_permission(context: RouteContext) -> str | None:
    if context.path == "/api/scenarios/compare-sets":
        return (
            PERMISSION_REPORTS_READ
            if context.method == "GET"
            else PERMISSION_INGEST_WRITE
        )
    if context.path.startswith("/api/scenarios/compare-sets/"):
        if context.method in {"DELETE", "PATCH", "POST", "PUT"}:
            return PERMISSION_INGEST_WRITE
        return PERMISSION_REPORTS_READ
    if context.path in {
        "/api/scenarios/loan-what-if",
        "/api/scenarios/income-change",
        "/api/scenarios/expense-shock",
    }:
        return PERMISSION_INGEST_WRITE
    path_parts = [part for part in context.path.strip("/").split("/") if part]
    if len(path_parts) == 3 and context.method == "DELETE":
        return PERMISSION_INGEST_WRITE
    return PERMISSION_REPORTS_READ


def _api_ha_request_role(context: RouteContext) -> UserRole | None:
    if context.path in {"/api/ha/ingest", "/api/ha/policies/evaluate"}:
        return UserRole.OPERATOR
    if context.path == "/api/ha/actions/proposals":
        return UserRole.READER if context.method == "GET" else UserRole.OPERATOR
    if context.path.startswith("/api/ha/actions/proposals/"):
        return UserRole.READER if context.method == "GET" else UserRole.OPERATOR
    return UserRole.READER


def _api_ha_request_permission(context: RouteContext) -> str | None:
    if context.path in {"/api/ha/ingest", "/api/ha/policies/evaluate"}:
        return PERMISSION_INGEST_WRITE
    if context.path == "/api/ha/actions/proposals":
        return (
            PERMISSION_RUNS_READ
            if context.method == "GET"
            else PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE
        )
    if context.path.startswith("/api/ha/actions/proposals/"):
        return (
            PERMISSION_RUNS_READ
            if context.method == "GET"
            else PERMISSION_CONTROL_ACTION_PROPOSALS_WRITE
        )
    return PERMISSION_RUNS_READ


def _api_ha_request_scope(context: RouteContext) -> str | None:
    if context.path in {"/api/ha/ingest", "/api/ha/policies/evaluate"}:
        return SERVICE_TOKEN_SCOPE_INGEST_WRITE
    if context.path == "/api/ha/actions/proposals":
        return (
            SERVICE_TOKEN_SCOPE_RUNS_READ
            if context.method == "GET"
            else SERVICE_TOKEN_SCOPE_ADMIN_WRITE
        )
    if context.path.startswith("/api/ha/actions/proposals/"):
        return (
            SERVICE_TOKEN_SCOPE_RUNS_READ
            if context.method == "GET"
            else SERVICE_TOKEN_SCOPE_ADMIN_WRITE
        )
    return SERVICE_TOKEN_SCOPE_RUNS_READ


def _control_source_lineage_permission(context: RouteContext) -> str | None:
    return _permission_from_query_param(
        parameter="run_id",
        factory=source_lineage_run_permission,
        fallback=PERMISSION_CONTROL_SOURCE_LINEAGE_READ,
    )(context)


def _control_publication_audit_permission(context: RouteContext) -> str | None:
    return _permission_from_query_param(
        parameter="publication_key",
        factory=publication_audit_publication_permission,
        fallback=PERMISSION_CONTROL_PUBLICATION_AUDIT_READ,
    )(context)


def _transformation_audit_permission(context: RouteContext) -> str | None:
    return _permission_from_query_param(
        parameter="run_id",
        factory=transformation_audit_run_permission,
        fallback=PERMISSION_TRANSFORMATION_AUDIT_READ,
    )(context)


def _runs_retry_role(context: RouteContext) -> UserRole | None:
    suffix = context.path.removeprefix("/runs/").strip("/")
    if not suffix.endswith("/retry"):
        return None
    return UserRole.OPERATOR


def _runs_retry_permission(context: RouteContext) -> str | None:
    suffix = context.path.removeprefix("/runs/").strip("/")
    if not suffix.endswith("/retry"):
        return None
    run_id = suffix.removesuffix("/retry").strip("/")
    return run_retry_permission(run_id) or PERMISSION_RUNS_RETRY


def _runs_read_role(context: RouteContext) -> UserRole | None:
    if context.path == "/runs":
        return UserRole.READER
    suffix = context.path.removeprefix("/runs/").strip("/")
    if suffix.endswith("/retry"):
        return None
    return UserRole.READER


def _runs_read_permission(context: RouteContext) -> str | None:
    if context.path == "/runs":
        return PERMISSION_RUNS_READ
    suffix = context.path.removeprefix("/runs/").strip("/")
    if suffix.endswith("/retry"):
        return None
    if not suffix:
        return PERMISSION_RUNS_READ
    first_segment = suffix.split("/", 1)[0].strip()
    if not first_segment:
        return PERMISSION_RUNS_READ
    return run_read_permission(first_segment) or PERMISSION_RUNS_READ


def _runs_read_scope(context: RouteContext) -> str | None:
    if context.path == "/runs":
        return SERVICE_TOKEN_SCOPE_RUNS_READ
    suffix = context.path.removeprefix("/runs/").strip("/")
    if suffix.endswith("/retry"):
        return None
    return SERVICE_TOKEN_SCOPE_RUNS_READ


def _reports_read_role(context: RouteContext) -> UserRole | None:
    if context.path == "/reports":
        return UserRole.READER
    return UserRole.READER


def _reports_read_permission(context: RouteContext) -> str | None:
    if context.path == "/reports":
        return PERMISSION_REPORTS_READ
    suffix = context.path.removeprefix("/reports/").strip("/")
    if not suffix:
        return PERMISSION_REPORTS_READ
    first_segment = suffix.split("/", 1)[0].strip()
    if not first_segment:
        return PERMISSION_REPORTS_READ
    return publication_read_permission(first_segment) or PERMISSION_REPORTS_READ


def _reports_read_scope(context: RouteContext) -> str | None:
    if context.path == "/reports":
        return SERVICE_TOKEN_SCOPE_REPORTS_READ
    return SERVICE_TOKEN_SCOPE_REPORTS_READ


API_ROUTE_POLICY_CATALOG: tuple[RoutePolicy, ...] = (
    RoutePolicy(
        exact_paths=(
            "/health",
            "/ready",
            "/metrics",
            "/auth/login",
            "/auth/logout",
            "/auth/callback",
        ),
    ),
    RoutePolicy(
        exact_paths=(
            "/auth/me",
            "/docs",
            "/redoc",
            "/openapi.json",
        ),
        path_decision=_static_decision(role=UserRole.READER),
        request_decision=_static_decision(role=UserRole.READER),
    ),
    RoutePolicy(
        exact_paths=("/control/source-lineage",),
        path_decision=RouteDecision(
            role=UserRole.READER,
            permission=_control_source_lineage_permission,
            scope=SERVICE_TOKEN_SCOPE_RUNS_READ,
        ),
    ),
    RoutePolicy(
        exact_paths=("/control/publication-audit",),
        path_decision=RouteDecision(
            role=UserRole.READER,
            permission=_control_publication_audit_permission,
            scope=SERVICE_TOKEN_SCOPE_RUNS_READ,
        ),
    ),
    RoutePolicy(
        exact_paths=("/transformation-audit",),
        path_decision=RouteDecision(
            role=UserRole.READER,
            permission=_transformation_audit_permission,
            scope=SERVICE_TOKEN_SCOPE_RUNS_READ,
        ),
    ),
    RoutePolicy(
        exact_paths=("/control/schedule-dispatches",),
        path_decision=RouteDecision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=RouteDecision(
            role=_schedule_dispatches_request_role,
            permission=_schedule_dispatches_request_permission,
            scope=lambda context: (
                SERVICE_TOKEN_SCOPE_RUNS_READ
                if context.method == "GET"
                else SERVICE_TOKEN_SCOPE_INGEST_WRITE
            ),
        ),
    ),
    RoutePolicy(
        prefix_paths=("/control/schedule-dispatches/",),
        path_decision=RouteDecision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=RouteDecision(
            role=_schedule_dispatch_item_role,
            permission=_schedule_dispatch_item_permission,
            scope=lambda context: (
                SERVICE_TOKEN_SCOPE_INGEST_WRITE
                if context.path.endswith("/retry")
                else SERVICE_TOKEN_SCOPE_RUNS_READ
            ),
        ),
    ),
    RoutePolicy(
        exact_paths=("/functions",),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/api/categories",),
        request_decision=RouteDecision(
            role=_categories_request_role,
            permission=_categories_request_permission,
            scope=lambda context: (
                SERVICE_TOKEN_SCOPE_REPORTS_READ
                if context.method == "GET"
                else SERVICE_TOKEN_SCOPE_INGEST_WRITE
            ),
        ),
    ),
    RoutePolicy(
        exact_paths=("/categories/rules",),
        request_decision=RouteDecision(
            role=_categories_rules_request_role,
            permission=_categories_rules_request_permission,
            scope=lambda context: (
                SERVICE_TOKEN_SCOPE_REPORTS_READ
                if context.method == "GET"
                else SERVICE_TOKEN_SCOPE_ADMIN_WRITE
            ),
        ),
    ),
    RoutePolicy(
        prefix_paths=("/categories/rules/",),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/categories/overrides",),
        request_decision=RouteDecision(
            role=_categories_overrides_request_role,
            permission=_categories_overrides_request_permission,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/categories/overrides/",),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/api/scenarios",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
    ),
    RoutePolicy(
        exact_paths=("/api/scenarios/compare-sets",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=RouteDecision(
            role=_scenarios_request_role,
            permission=_scenarios_request_permission,
            scope=lambda context: (
                SERVICE_TOKEN_SCOPE_REPORTS_READ
                if context.method == "GET"
                else SERVICE_TOKEN_SCOPE_INGEST_WRITE
            ),
        ),
    ),
    RoutePolicy(
        prefix_paths=("/api/scenarios/compare-sets/",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=RouteDecision(
            role=_scenarios_request_role,
            permission=_scenarios_request_permission,
            scope=lambda context: (
                SERVICE_TOKEN_SCOPE_REPORTS_READ
                if context.method == "GET"
                else SERVICE_TOKEN_SCOPE_INGEST_WRITE
            ),
        ),
    ),
    RoutePolicy(
        exact_paths=(
            "/api/scenarios/loan-what-if",
            "/api/scenarios/income-change",
            "/api/scenarios/expense-shock",
            "/api/scenarios/tariff-shock",
            "/api/scenarios/homelab-cost-benefit",
        ),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=_static_decision(
            role=UserRole.OPERATOR,
            permission=PERMISSION_INGEST_WRITE,
            scope=SERVICE_TOKEN_SCOPE_INGEST_WRITE,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/api/scenarios/",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=RouteDecision(
            role=_scenarios_request_role,
            permission=_scenarios_request_permission,
            scope=lambda context: (
                SERVICE_TOKEN_SCOPE_REPORTS_READ
                if context.method != "DELETE"
                else SERVICE_TOKEN_SCOPE_INGEST_WRITE
            ),
        ),
    ),
    RoutePolicy(
        prefix_paths=("/api/assistant",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/api/ingest/ha-bridge/",),
        path_decision=_static_decision(
            role=UserRole.OPERATOR,
            permission=PERMISSION_INGEST_WRITE,
            scope=SERVICE_TOKEN_SCOPE_HA_BRIDGE_INGEST,
        ),
        request_decision=_static_decision(
            role=UserRole.OPERATOR,
            permission=PERMISSION_INGEST_WRITE,
            scope=SERVICE_TOKEN_SCOPE_HA_BRIDGE_INGEST,
        ),
    ),
    RoutePolicy(
        exact_paths=("/api/ha/ingest", "/api/ha/policies/evaluate"),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_RUNS_READ,
            scope=SERVICE_TOKEN_SCOPE_RUNS_READ,
        ),
        request_decision=_static_decision(
            role=UserRole.OPERATOR,
            permission=PERMISSION_INGEST_WRITE,
            scope=SERVICE_TOKEN_SCOPE_INGEST_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/api/ha/actions/proposals",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_RUNS_READ,
            scope=SERVICE_TOKEN_SCOPE_RUNS_READ,
        ),
        request_decision=RouteDecision(
            role=_api_ha_request_role,
            permission=_api_ha_request_permission,
            scope=_api_ha_request_scope,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/api/ha/actions/proposals/",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_RUNS_READ,
            scope=SERVICE_TOKEN_SCOPE_RUNS_READ,
        ),
        request_decision=RouteDecision(
            role=_api_ha_request_role,
            permission=_api_ha_request_permission,
            scope=_api_ha_request_scope,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/api/ha/metrics",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/api/ha",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_RUNS_READ,
            scope=SERVICE_TOKEN_SCOPE_RUNS_READ,
        ),
        request_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_RUNS_READ,
            scope=SERVICE_TOKEN_SCOPE_RUNS_READ,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/api/homelab/",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/adapters/",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=RouteDecision(
            role=lambda context: (
                UserRole.READER if context.method == "GET" else UserRole.OPERATOR
            ),
            permission=lambda context: (
                PERMISSION_REPORTS_READ
                if context.method == "GET"
                else PERMISSION_ADMIN_WRITE
            ),
            scope=lambda context: (
                SERVICE_TOKEN_SCOPE_REPORTS_READ
                if context.method == "GET"
                else SERVICE_TOKEN_SCOPE_ADMIN_WRITE
            ),
        ),
    ),
    RoutePolicy(
        prefix_paths=("/contracts/publications/",),
        path_decision=RouteDecision(
            role=UserRole.READER,
            permission=_permission_from_suffix(
                prefix="/contracts/publications/",
                factory=publication_read_permission,
                fallback=PERMISSION_REPORTS_READ,
            ),
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=RouteDecision(
            role=UserRole.READER,
            permission=_permission_from_suffix(
                prefix="/contracts/publications/",
                factory=publication_read_permission,
                fallback=PERMISSION_REPORTS_READ,
            ),
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/contracts/",),
        path_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
        request_decision=_static_decision(
            role=UserRole.READER,
            permission=PERMISSION_REPORTS_READ,
            scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/auth/users", "/auth/service-tokens"),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/control/auth-audit",),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/config/",),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=RouteDecision(
            role=_config_request_role,
            permission=_config_request_permission,
            scope=lambda context: SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/control/policies",),
        prefix_paths=("/control/policies/",),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_CONTROL_POLICY_READ,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=lambda context: (
            PERMISSION_CONTROL_POLICY_READ
            if context.method in ("GET", "HEAD")
            else PERMISSION_CONTROL_POLICY_WRITE
        ),
    ),
    RoutePolicy(
        prefix_paths=("/control/",),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/extensions", "/sources"),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/landing/", "/transformations/", "/ingest/ingestion-definitions/"),
        path_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
        request_decision=_static_decision(
            role=UserRole.ADMIN,
            permission=PERMISSION_ADMIN_WRITE,
            scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/ingest",),
        prefix_paths=("/ingest/",),
        path_decision=_static_decision(
            role=UserRole.OPERATOR,
            permission=PERMISSION_INGEST_WRITE,
            scope=SERVICE_TOKEN_SCOPE_INGEST_WRITE,
        ),
        request_decision=_static_decision(
            role=UserRole.OPERATOR,
            permission=PERMISSION_INGEST_WRITE,
            scope=SERVICE_TOKEN_SCOPE_INGEST_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/runs",),
        prefix_paths=("/runs/",),
        path_decision=RouteDecision(
            role=_runs_read_role,
            permission=_runs_read_permission,
            scope=_runs_read_scope,
        ),
        request_decision=RouteDecision(
            role=_runs_read_role,
            permission=_runs_read_permission,
            scope=_runs_read_scope,
        ),
    ),
    RoutePolicy(
        prefix_paths=("/runs/",),
        path_decision=RouteDecision(
            role=UserRole.OPERATOR,
            permission=_runs_retry_permission,
            scope=SERVICE_TOKEN_SCOPE_INGEST_WRITE,
        ),
        request_decision=RouteDecision(
            role=UserRole.OPERATOR,
            permission=_runs_retry_permission,
            scope=SERVICE_TOKEN_SCOPE_INGEST_WRITE,
        ),
    ),
    RoutePolicy(
        exact_paths=("/reports",),
        prefix_paths=("/reports/",),
        path_decision=RouteDecision(
            role=_reports_read_role,
            permission=_reports_read_permission,
            scope=_reports_read_scope,
        ),
        request_decision=RouteDecision(
            role=_reports_read_role,
            permission=_reports_read_permission,
            scope=_reports_read_scope,
        ),
    ),
)

API_ROUTE_AUTHORIZATION_LOOKUP = RouteAuthorizationLookup(API_ROUTE_POLICY_CATALOG)


def required_permission_for_path(
    lookup_or_path: RouteAuthorizationLookup | str,
    path: str | None = None,
) -> str | None:
    if isinstance(lookup_or_path, RouteAuthorizationLookup):
        lookup = lookup_or_path
        resolved_path = path
    else:
        lookup = API_ROUTE_AUTHORIZATION_LOOKUP
        resolved_path = lookup_or_path
    if resolved_path is None:
        raise TypeError("required_permission_for_path() missing path argument")
    return lookup.required_permission_for_path(resolved_path)


def required_permission_for_request(
    lookup_or_path: RouteAuthorizationLookup | str,
    path_or_query_params: str | Mapping[str, str] | None = None,
    query_params: Mapping[str, str] | None = None,
    method: str | None = None,
) -> str | None:
    if isinstance(lookup_or_path, RouteAuthorizationLookup):
        lookup = lookup_or_path
        resolved_path = path_or_query_params if isinstance(path_or_query_params, str) else None
        resolved_query_params = query_params
    else:
        lookup = API_ROUTE_AUTHORIZATION_LOOKUP
        resolved_path = lookup_or_path
        resolved_query_params = (
            path_or_query_params if isinstance(path_or_query_params, Mapping) else query_params
        )
    if resolved_path is None:
        raise TypeError("required_permission_for_request() missing path argument")
    return lookup.required_permission_for_request(
        resolved_path,
        query_params=resolved_query_params,
        method=method,
    )


def required_role_for_request(
    lookup_or_path: RouteAuthorizationLookup | str,
    path_or_method: str | None = None,
    method: str | None = None,
) -> UserRole | None:
    if isinstance(lookup_or_path, RouteAuthorizationLookup):
        lookup = lookup_or_path
        resolved_path = path_or_method
        resolved_method = method
    else:
        lookup = API_ROUTE_AUTHORIZATION_LOOKUP
        resolved_path = lookup_or_path
        resolved_method = path_or_method if path_or_method is not None else method
    if resolved_path is None:
        raise TypeError("required_role_for_request() missing path argument")
    return lookup.required_role_for_request(resolved_path, resolved_method)


def required_service_token_scope_for_request(
    lookup_or_path: RouteAuthorizationLookup | str,
    path_or_method: str | None = None,
    method: str | None = None,
) -> str | None:
    if isinstance(lookup_or_path, RouteAuthorizationLookup):
        lookup = lookup_or_path
        resolved_path = path_or_method
        resolved_method = method
    else:
        lookup = API_ROUTE_AUTHORIZATION_LOOKUP
        resolved_path = lookup_or_path
        resolved_method = path_or_method if path_or_method is not None else method
    if resolved_path is None:
        raise TypeError("required_service_token_scope_for_request() missing path argument")
    return lookup.required_service_token_scope_for_request(resolved_path, resolved_method)


def required_role_for_path(
    lookup_or_path: RouteAuthorizationLookup | str,
    path: str | None = None,
) -> UserRole | None:
    if isinstance(lookup_or_path, RouteAuthorizationLookup):
        lookup = lookup_or_path
        resolved_path = path
    else:
        lookup = API_ROUTE_AUTHORIZATION_LOOKUP
        resolved_path = lookup_or_path
    if resolved_path is None:
        raise TypeError("required_role_for_path() missing path argument")
    return lookup.required_role_for_path(resolved_path)


def required_service_token_scope_for_path(
    lookup_or_path: RouteAuthorizationLookup | str,
    path: str | None = None,
) -> str | None:
    if isinstance(lookup_or_path, RouteAuthorizationLookup):
        lookup = lookup_or_path
        resolved_path = path
    else:
        lookup = API_ROUTE_AUTHORIZATION_LOOKUP
        resolved_path = lookup_or_path
    if resolved_path is None:
        raise TypeError("required_service_token_scope_for_path() missing path argument")
    return lookup.required_service_token_scope_for_path(resolved_path)
