"""Path-level role and service-token scope requirements for the API."""
from __future__ import annotations

from collections.abc import Mapping

from packages.platform.auth.permission_registry import (
    PERMISSION_ADMIN_WRITE,
    PERMISSION_CONTROL_PUBLICATION_AUDIT_READ,
    PERMISSION_CONTROL_SOURCE_LINEAGE_READ,
    PERMISSION_INGEST_WRITE,
    PERMISSION_REPORTS_READ,
    PERMISSION_RUNS_READ,
    PERMISSION_RUNS_RETRY,
    PERMISSION_TRANSFORMATION_AUDIT_READ,
    publication_audit_publication_permission,
    publication_read_permission,
    run_read_permission,
    run_retry_permission,
    source_lineage_run_permission,
)
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    UserRole,
)


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
) -> str | None:
    required_permission = required_permission_for_path(path)
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
    return required_permission


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
