"""Path-level role and service-token scope requirements for the API."""
from __future__ import annotations

from collections.abc import Mapping

from packages.platform.auth.permission_registry import (
    PERMISSION_ADMIN_WRITE,
    PERMISSION_CONTROL_CONFIG_READ,
    PERMISSION_CONTROL_CONFIG_WRITE,
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
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    UserRole,
)


def _config_resource_key(path: str) -> str | None:
    suffix = path.removeprefix("/config/").strip("/")
    if not suffix:
        return None
    parts = [part.strip().lower() for part in suffix.split("/") if part.strip()]
    if not parts:
        return None
    return ".".join(parts)


def required_permission_for_path(path: str) -> str | None:
    if path in {
        "/health",
        "/ready",
        "/metrics",
        "/auth/login",
        "/auth/logout",
        "/auth/callback",
        "/auth/me",
        "/docs",
        "/redoc",
        "/openapi.json",
    }:
        return None
    if path.startswith("/runs/") and path.endswith("/retry"):
        run_id = path.removeprefix("/runs/").removesuffix("/retry").strip("/")
        return run_retry_permission(run_id) or PERMISSION_RUNS_RETRY
    if path == "/control/source-lineage":
        return PERMISSION_CONTROL_SOURCE_LINEAGE_READ
    if path == "/control/publication-audit":
        return PERMISSION_CONTROL_PUBLICATION_AUDIT_READ
    if path == "/transformation-audit":
        return PERMISSION_TRANSFORMATION_AUDIT_READ
    if (
        path.startswith("/auth/users")
        or path.startswith("/auth/service-tokens")
        or path == "/control/auth-audit"
        or path == "/control/schedule-dispatches"
        or path.startswith("/config/")
        or path.startswith("/control/")
        or path in {"/extensions", "/sources"}
        or path.startswith("/landing/")
        or path.startswith("/transformations/")
        or path.startswith("/ingest/ingestion-definitions/")
    ):
        return PERMISSION_ADMIN_WRITE
    if path.startswith("/ingest"):
        return PERMISSION_INGEST_WRITE
    if path.startswith("/runs"):
        suffix = path.removeprefix("/runs").strip("/")
        if not suffix:
            return PERMISSION_RUNS_READ
        run_id = suffix.split("/", 1)[0].strip()
        return run_read_permission(run_id) or PERMISSION_RUNS_READ
    if path.startswith("/reports"):
        suffix = path.removeprefix("/reports").strip("/")
        if not suffix:
            return PERMISSION_REPORTS_READ
        publication_key = suffix.split("/", 1)[0].strip()
        return publication_read_permission(publication_key) or PERMISSION_REPORTS_READ
    return None


def required_permission_for_request(
    path: str,
    query_params: Mapping[str, str] | None = None,
    method: str | None = None,
) -> str | None:
    request_method = (method or "GET").upper()
    required_permission = required_permission_for_path(path)
    if path.startswith("/config/"):
        resource_key = _config_resource_key(path)
        if request_method in {"GET", "HEAD", "OPTIONS"}:
            if resource_key:
                return (
                    config_read_resource_permission(resource_key)
                    or PERMISSION_CONTROL_CONFIG_READ
                )
            return PERMISSION_CONTROL_CONFIG_READ
        if resource_key:
            return (
                config_write_resource_permission(resource_key)
                or PERMISSION_CONTROL_CONFIG_WRITE
            )
        return PERMISSION_CONTROL_CONFIG_WRITE
    if path == "/control/schedule-dispatches":
        if request_method == "GET":
            schedule_id = (query_params or {}).get("schedule_id", "").strip()
            if schedule_id:
                return (
                    schedule_dispatch_read_schedule_permission(schedule_id)
                    or PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ
                )
            return PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ
        return PERMISSION_CONTROL_SCHEDULE_DISPATCHES_WRITE
    if path.startswith("/control/schedule-dispatches/") and path.endswith("/retry"):
        dispatch_id = (
            path.removeprefix("/control/schedule-dispatches/")
            .removesuffix("/retry")
            .strip("/")
        )
        return (
            schedule_dispatch_write_dispatch_permission(dispatch_id)
            or PERMISSION_CONTROL_SCHEDULE_DISPATCHES_WRITE
        )
    if path.startswith("/control/schedule-dispatches/"):
        dispatch_id = path.removeprefix("/control/schedule-dispatches/").strip("/")
        return (
            schedule_dispatch_read_dispatch_permission(dispatch_id)
            or PERMISSION_CONTROL_SCHEDULE_DISPATCHES_READ
        )
    if path == "/functions":
        return PERMISSION_ADMIN_WRITE
    if path.startswith("/contracts/publications/"):
        publication_key = path.removeprefix("/contracts/publications/").strip("/")
        return publication_read_permission(publication_key) or PERMISSION_REPORTS_READ
    if path.startswith("/contracts/"):
        return PERMISSION_REPORTS_READ
    if path == "/api/categories":
        return PERMISSION_REPORTS_READ if request_method == "GET" else PERMISSION_ADMIN_WRITE
    if path == "/categories/rules":
        return PERMISSION_REPORTS_READ if request_method == "GET" else PERMISSION_ADMIN_WRITE
    if path.startswith("/categories/rules/"):
        return PERMISSION_ADMIN_WRITE
    if path == "/categories/overrides":
        return PERMISSION_REPORTS_READ
    if path.startswith("/categories/overrides/"):
        return PERMISSION_ADMIN_WRITE
    if path.startswith("/api/scenarios"):
        if path == "/api/scenarios/compare-sets":
            return (
                PERMISSION_REPORTS_READ
                if request_method == "GET"
                else PERMISSION_INGEST_WRITE
            )
        if path.startswith("/api/scenarios/compare-sets/"):
            return PERMISSION_INGEST_WRITE if request_method == "DELETE" else PERMISSION_REPORTS_READ
        if path in {
            "/api/scenarios/loan-what-if",
            "/api/scenarios/income-change",
            "/api/scenarios/expense-shock",
        }:
            return PERMISSION_INGEST_WRITE
        path_parts = [part for part in path.strip("/").split("/") if part]
        if len(path_parts) == 3 and request_method == "DELETE":
            return PERMISSION_INGEST_WRITE
        return PERMISSION_REPORTS_READ
    if path.startswith("/api/ha"):
        if path in {"/api/ha/ingest", "/api/ha/policies/evaluate"}:
            return PERMISSION_INGEST_WRITE
        return PERMISSION_RUNS_READ
    if path.startswith("/api/homelab/"):
        return PERMISSION_REPORTS_READ
    if path == "/control/source-lineage":
        run_id = (query_params or {}).get("run_id", "").strip()
        if run_id:
            return (
                source_lineage_run_permission(run_id)
                or PERMISSION_CONTROL_SOURCE_LINEAGE_READ
            )
    if path == "/control/publication-audit":
        publication_key = (query_params or {}).get("publication_key", "").strip()
        if publication_key:
            return (
                publication_audit_publication_permission(publication_key)
                or PERMISSION_CONTROL_PUBLICATION_AUDIT_READ
            )
    if path == "/transformation-audit":
        run_id = (query_params or {}).get("run_id", "").strip()
        if run_id:
            return (
                transformation_audit_run_permission(run_id)
                or PERMISSION_TRANSFORMATION_AUDIT_READ
            )
    return required_permission


def required_role_for_request(
    path: str,
    method: str | None = None,
) -> UserRole | None:
    request_method = (method or "GET").upper()
    required_role = required_role_for_path(path)
    if path == "/control/schedule-dispatches":
        return UserRole.READER if request_method == "GET" else UserRole.OPERATOR
    if path.startswith("/control/schedule-dispatches/") and path.endswith("/retry"):
        return UserRole.OPERATOR
    if path.startswith("/control/schedule-dispatches/"):
        return UserRole.READER
    if path == "/functions":
        return UserRole.ADMIN
    if path.startswith("/contracts/"):
        return UserRole.READER
    if path == "/api/categories":
        return UserRole.READER if request_method == "GET" else UserRole.ADMIN
    if path == "/categories/rules":
        return UserRole.READER if request_method == "GET" else UserRole.ADMIN
    if path.startswith("/categories/rules/"):
        return UserRole.ADMIN
    if path == "/categories/overrides":
        return UserRole.READER
    if path.startswith("/categories/overrides/"):
        return UserRole.ADMIN
    if path.startswith("/api/scenarios"):
        if path == "/api/scenarios/compare-sets":
            return UserRole.READER if request_method == "GET" else UserRole.OPERATOR
        if path.startswith("/api/scenarios/compare-sets/"):
            return UserRole.OPERATOR if request_method == "DELETE" else UserRole.READER
        if path in {
            "/api/scenarios/loan-what-if",
            "/api/scenarios/income-change",
            "/api/scenarios/expense-shock",
        }:
            return UserRole.OPERATOR
        path_parts = [part for part in path.strip("/").split("/") if part]
        if len(path_parts) == 3 and request_method == "DELETE":
            return UserRole.OPERATOR
        return UserRole.READER
    if path.startswith("/api/ha"):
        if path in {"/api/ha/ingest", "/api/ha/policies/evaluate"}:
            return UserRole.OPERATOR
        return UserRole.READER
    if path.startswith("/api/homelab/"):
        return UserRole.READER
    return required_role


def required_service_token_scope_for_request(
    path: str,
    method: str | None = None,
) -> str | None:
    request_method = (method or "GET").upper()
    required_scope = required_service_token_scope_for_path(path)
    if path == "/control/schedule-dispatches":
        return (
            SERVICE_TOKEN_SCOPE_RUNS_READ
            if request_method == "GET"
            else SERVICE_TOKEN_SCOPE_INGEST_WRITE
        )
    if path.startswith("/control/schedule-dispatches/") and path.endswith("/retry"):
        return SERVICE_TOKEN_SCOPE_INGEST_WRITE
    if path.startswith("/control/schedule-dispatches/"):
        return SERVICE_TOKEN_SCOPE_RUNS_READ
    if path == "/functions":
        return SERVICE_TOKEN_SCOPE_ADMIN_WRITE
    if path.startswith("/contracts/"):
        return SERVICE_TOKEN_SCOPE_REPORTS_READ
    if path == "/api/categories":
        return (
            SERVICE_TOKEN_SCOPE_REPORTS_READ
            if request_method == "GET"
            else SERVICE_TOKEN_SCOPE_ADMIN_WRITE
        )
    if path == "/categories/rules":
        return (
            SERVICE_TOKEN_SCOPE_REPORTS_READ
            if request_method == "GET"
            else SERVICE_TOKEN_SCOPE_ADMIN_WRITE
        )
    if path.startswith("/categories/rules/"):
        return SERVICE_TOKEN_SCOPE_ADMIN_WRITE
    if path == "/categories/overrides":
        return SERVICE_TOKEN_SCOPE_REPORTS_READ
    if path.startswith("/categories/overrides/"):
        return SERVICE_TOKEN_SCOPE_ADMIN_WRITE
    if path.startswith("/api/scenarios"):
        if path == "/api/scenarios/compare-sets":
            return (
                SERVICE_TOKEN_SCOPE_REPORTS_READ
                if request_method == "GET"
                else SERVICE_TOKEN_SCOPE_INGEST_WRITE
            )
        if path.startswith("/api/scenarios/compare-sets/"):
            return (
                SERVICE_TOKEN_SCOPE_INGEST_WRITE
                if request_method == "DELETE"
                else SERVICE_TOKEN_SCOPE_REPORTS_READ
            )
        if path in {
            "/api/scenarios/loan-what-if",
            "/api/scenarios/income-change",
            "/api/scenarios/expense-shock",
        }:
            return SERVICE_TOKEN_SCOPE_INGEST_WRITE
        path_parts = [part for part in path.strip("/").split("/") if part]
        if len(path_parts) == 3 and request_method == "DELETE":
            return SERVICE_TOKEN_SCOPE_INGEST_WRITE
        return SERVICE_TOKEN_SCOPE_REPORTS_READ
    if path.startswith("/api/ha"):
        if path in {"/api/ha/ingest", "/api/ha/policies/evaluate"}:
            return SERVICE_TOKEN_SCOPE_INGEST_WRITE
        return SERVICE_TOKEN_SCOPE_RUNS_READ
    if path.startswith("/api/homelab/"):
        return SERVICE_TOKEN_SCOPE_REPORTS_READ
    return required_scope


def required_role_for_path(path: str) -> UserRole | None:
    if path in {
        "/health",
        "/ready",
        "/metrics",
        "/auth/login",
        "/auth/logout",
        "/auth/callback",
    }:
        return None
    if path.startswith("/runs/") and path.endswith("/retry"):
        return UserRole.OPERATOR
    if path in {
        "/control/source-lineage",
        "/control/publication-audit",
        "/transformation-audit",
    }:
        return UserRole.READER
    if (
        path.startswith("/auth/users")
        or path.startswith("/auth/service-tokens")
        or path == "/control/auth-audit"
        or path == "/control/schedule-dispatches"
        or path.startswith("/config/")
        or path.startswith("/control/")
        or path in {"/extensions", "/sources"}
        or path.startswith("/landing/")
        or path.startswith("/transformations/")
        or path.startswith("/ingest/ingestion-definitions/")
    ):
        return UserRole.ADMIN
    if path.startswith("/ingest"):
        return UserRole.OPERATOR
    if (
        path.startswith("/runs")
        or path.startswith("/reports")
        or path == "/auth/me"
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
    ):
        return UserRole.READER
    return None


def required_service_token_scope_for_path(path: str) -> str | None:
    if path in {
        "/health",
        "/ready",
        "/metrics",
        "/auth/login",
        "/auth/logout",
        "/auth/callback",
    }:
        return None
    if path.startswith("/ingest") or (
        path.startswith("/runs/") and path.endswith("/retry")
    ):
        return SERVICE_TOKEN_SCOPE_INGEST_WRITE
    if (
        path.startswith("/runs")
        or path == "/control/source-lineage"
        or path == "/control/publication-audit"
        or path == "/transformation-audit"
    ):
        return SERVICE_TOKEN_SCOPE_RUNS_READ
    if path.startswith("/reports"):
        return SERVICE_TOKEN_SCOPE_REPORTS_READ
    if (
        path.startswith("/auth/users")
        or path.startswith("/auth/service-tokens")
        or path == "/control/auth-audit"
        or path == "/control/schedule-dispatches"
        or path.startswith("/config/")
        or path.startswith("/control/")
        or path in {"/extensions", "/sources"}
        or path.startswith("/landing/")
        or path.startswith("/transformations/")
        or path.startswith("/ingest/ingestion-definitions/")
    ):
        return SERVICE_TOKEN_SCOPE_ADMIN_WRITE
    return None
