"""Path-level role and service-token scope requirements for the API."""
from __future__ import annotations

from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    UserRole,
)


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
