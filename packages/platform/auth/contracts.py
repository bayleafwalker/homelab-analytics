"""Shared auth vocabulary owned by the platform auth layer."""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    READER = "reader"
    OPERATOR = "operator"
    ADMIN = "admin"


SERVICE_TOKEN_SCOPE_REPORTS_READ = "reports:read"
SERVICE_TOKEN_SCOPE_RUNS_READ = "runs:read"
SERVICE_TOKEN_SCOPE_INGEST_WRITE = "ingest:write"
SERVICE_TOKEN_SCOPE_ADMIN_WRITE = "admin:write"
SERVICE_TOKEN_SCOPES = (
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
)


# Legacy scope-to-permission compatibility mapping.
# New authorization code should prefer canonical permissions directly.
SERVICE_TOKEN_SCOPE_PERMISSION_MAP = {
    SERVICE_TOKEN_SCOPE_REPORTS_READ: "reports.read",
    SERVICE_TOKEN_SCOPE_RUNS_READ: "runs.read",
    SERVICE_TOKEN_SCOPE_INGEST_WRITE: "ingest.write",
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE: "admin.write",
}


def normalize_service_token_scopes(scopes: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized = {scope.strip().lower() for scope in scopes if scope.strip()}
    if not normalized:
        raise ValueError("Service token must include at least one scope.")
    unknown = normalized.difference(SERVICE_TOKEN_SCOPES)
    if unknown:
        raise ValueError(
            f"Unknown service-token scope(s): {', '.join(sorted(unknown))}."
        )
    return tuple(scope for scope in SERVICE_TOKEN_SCOPES if scope in normalized)

