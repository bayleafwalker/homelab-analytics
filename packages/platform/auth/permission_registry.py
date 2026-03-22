"""Authorization permission registry and principal permission resolution.

This module introduces a canonical permission vocabulary behind the existing
reader/operator/admin role ladder and service-token scopes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet

from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    UserRole,
)

# Canonical app permissions.
PERMISSION_RUNS_READ = "runs.read"
PERMISSION_RUNS_RETRY = "runs.retry"
PERMISSION_REPORTS_READ = "reports.read"
PERMISSION_INGEST_WRITE = "ingest.write"
PERMISSION_CONTROL_SOURCE_LINEAGE_READ = "control.source_lineage.read"
PERMISSION_CONTROL_PUBLICATION_AUDIT_READ = "control.publication_audit.read"
PERMISSION_TRANSFORMATION_AUDIT_READ = "transformation.audit.read"
PERMISSION_ADMIN_WRITE = "admin.write"
PERMISSION_RUNS_READ_RUN_PREFIX = f"{PERMISSION_RUNS_READ}.run."
PERMISSION_RUNS_RETRY_RUN_PREFIX = f"{PERMISSION_RUNS_RETRY}.run."
PERMISSION_RUNS_READ_RUN_WILDCARD = f"{PERMISSION_RUNS_READ_RUN_PREFIX}*"
PERMISSION_RUNS_RETRY_RUN_WILDCARD = f"{PERMISSION_RUNS_RETRY_RUN_PREFIX}*"
PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_PREFIX = (
    f"{PERMISSION_CONTROL_SOURCE_LINEAGE_READ}.run."
)
PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_PREFIX = (
    f"{PERMISSION_CONTROL_PUBLICATION_AUDIT_READ}.publication."
)
PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_WILDCARD = (
    f"{PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_PREFIX}*"
)
PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_WILDCARD = (
    f"{PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_PREFIX}*"
)
PERMISSION_REPORTS_READ_PUBLICATION_PREFIX = f"{PERMISSION_REPORTS_READ}.publication."
PERMISSION_REPORTS_READ_PUBLICATION_WILDCARD = (
    f"{PERMISSION_REPORTS_READ_PUBLICATION_PREFIX}*"
)


_DYNAMIC_PERMISSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


_READER_PERMISSIONS: frozenset[str] = frozenset(
    {
        PERMISSION_RUNS_READ,
        PERMISSION_REPORTS_READ,
        PERMISSION_CONTROL_SOURCE_LINEAGE_READ,
        PERMISSION_CONTROL_PUBLICATION_AUDIT_READ,
        PERMISSION_TRANSFORMATION_AUDIT_READ,
    }
)
_OPERATOR_PERMISSIONS: frozenset[str] = _READER_PERMISSIONS.union(
    {
        PERMISSION_INGEST_WRITE,
        PERMISSION_RUNS_RETRY,
    }
)
_ADMIN_PERMISSIONS: frozenset[str] = _OPERATOR_PERMISSIONS.union(
    {
        PERMISSION_ADMIN_WRITE,
    }
)

_ROLE_PERMISSION_BUNDLES: dict[UserRole, frozenset[str]] = {
    UserRole.READER: _READER_PERMISSIONS,
    UserRole.OPERATOR: _OPERATOR_PERMISSIONS,
    UserRole.ADMIN: _ADMIN_PERMISSIONS,
}

_SERVICE_SCOPE_PERMISSIONS: dict[str, frozenset[str]] = {
    SERVICE_TOKEN_SCOPE_REPORTS_READ: frozenset({PERMISSION_REPORTS_READ}),
    SERVICE_TOKEN_SCOPE_RUNS_READ: frozenset(
        {
            PERMISSION_RUNS_READ,
            PERMISSION_CONTROL_SOURCE_LINEAGE_READ,
            PERMISSION_CONTROL_PUBLICATION_AUDIT_READ,
            PERMISSION_TRANSFORMATION_AUDIT_READ,
        }
    ),
    SERVICE_TOKEN_SCOPE_INGEST_WRITE: frozenset(
        {
            PERMISSION_INGEST_WRITE,
            PERMISSION_RUNS_RETRY,
        }
    ),
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE: frozenset({PERMISSION_ADMIN_WRITE}),
}

KNOWN_PERMISSIONS: frozenset[str] = frozenset(
    {
        PERMISSION_RUNS_READ,
        PERMISSION_RUNS_RETRY,
        PERMISSION_REPORTS_READ,
        PERMISSION_INGEST_WRITE,
        PERMISSION_CONTROL_SOURCE_LINEAGE_READ,
        PERMISSION_CONTROL_PUBLICATION_AUDIT_READ,
        PERMISSION_TRANSFORMATION_AUDIT_READ,
        PERMISSION_ADMIN_WRITE,
    }
)


@dataclass(frozen=True)
class PrincipalAuthorizationContext:
    role: UserRole
    auth_provider: str
    scopes: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    permission_bound: bool = False


def permissions_for_role(role: UserRole) -> FrozenSet[str]:
    return _ROLE_PERMISSION_BUNDLES[role]


def permissions_for_service_token_scopes(scopes: tuple[str, ...]) -> FrozenSet[str]:
    resolved: set[str] = set()
    for scope in scopes:
        resolved.update(_SERVICE_SCOPE_PERMISSIONS.get(scope, frozenset()))
    return frozenset(resolved)


def normalize_permission_grants(
    permissions: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    normalized = {permission.strip().lower() for permission in permissions if permission.strip()}
    recognized = set(normalized.intersection(KNOWN_PERMISSIONS))
    for permission in normalized:
        dynamic_permission = _normalize_dynamic_permission(permission)
        if dynamic_permission is not None:
            recognized.add(dynamic_permission)
    resolved = sorted(recognized)
    return tuple(resolved)


def publication_read_permission(publication_key: str) -> str | None:
    normalized = publication_key.strip().lower()
    if not normalized:
        return None
    if not _DYNAMIC_PERMISSION_PATTERN.fullmatch(normalized):
        return None
    return f"{PERMISSION_REPORTS_READ_PUBLICATION_PREFIX}{normalized}"


def run_read_permission(run_id: str) -> str | None:
    normalized = run_id.strip().lower()
    if not normalized:
        return None
    if not _DYNAMIC_PERMISSION_PATTERN.fullmatch(normalized):
        return None
    return f"{PERMISSION_RUNS_READ_RUN_PREFIX}{normalized}"


def run_retry_permission(run_id: str) -> str | None:
    normalized = run_id.strip().lower()
    if not normalized:
        return None
    if not _DYNAMIC_PERMISSION_PATTERN.fullmatch(normalized):
        return None
    return f"{PERMISSION_RUNS_RETRY_RUN_PREFIX}{normalized}"


def source_lineage_run_permission(run_id: str) -> str | None:
    normalized = run_id.strip().lower()
    if not normalized:
        return None
    if not _DYNAMIC_PERMISSION_PATTERN.fullmatch(normalized):
        return None
    return f"{PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_PREFIX}{normalized}"


def publication_audit_publication_permission(publication_key: str) -> str | None:
    normalized = publication_key.strip().lower()
    if not normalized:
        return None
    if not _DYNAMIC_PERMISSION_PATTERN.fullmatch(normalized):
        return None
    return f"{PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_PREFIX}{normalized}"


def _normalize_dynamic_permission(permission: str) -> str | None:
    if permission in {
        PERMISSION_RUNS_READ_RUN_WILDCARD,
        PERMISSION_RUNS_RETRY_RUN_WILDCARD,
        PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_WILDCARD,
        PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_WILDCARD,
        PERMISSION_REPORTS_READ_PUBLICATION_WILDCARD,
    }:
        return permission
    for prefix in (
        PERMISSION_RUNS_READ_RUN_PREFIX,
        PERMISSION_RUNS_RETRY_RUN_PREFIX,
        PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_PREFIX,
        PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_PREFIX,
        PERMISSION_REPORTS_READ_PUBLICATION_PREFIX,
    ):
        if permission.startswith(prefix):
            suffix = permission.removeprefix(prefix)
            if suffix.endswith(".*"):
                wildcard_prefix = suffix[:-2]
                if wildcard_prefix and _DYNAMIC_PERMISSION_PATTERN.fullmatch(
                    wildcard_prefix
                ):
                    return f"{prefix}{wildcard_prefix}.*"
                return None
            if _DYNAMIC_PERMISSION_PATTERN.fullmatch(suffix):
                return f"{prefix}{suffix}"
            return None
    return None


def _normalize_required_permission(required_permission: str) -> str:
    normalized = normalize_permission_grants([required_permission])
    if normalized:
        return normalized[0]
    return required_permission.strip().lower()


def _granted_permission_satisfies_required(granted: str, required: str) -> bool:
    if granted == required:
        return True
    if (
        granted == PERMISSION_REPORTS_READ
        and required.startswith(PERMISSION_REPORTS_READ_PUBLICATION_PREFIX)
    ):
        return True
    if granted == PERMISSION_RUNS_READ and required.startswith(PERMISSION_RUNS_READ_RUN_PREFIX):
        return True
    if granted == PERMISSION_RUNS_RETRY and required.startswith(PERMISSION_RUNS_RETRY_RUN_PREFIX):
        return True
    if (
        granted == PERMISSION_CONTROL_SOURCE_LINEAGE_READ
        and required.startswith(PERMISSION_CONTROL_SOURCE_LINEAGE_RUN_PREFIX)
    ):
        return True
    if (
        granted == PERMISSION_CONTROL_PUBLICATION_AUDIT_READ
        and required.startswith(PERMISSION_CONTROL_PUBLICATION_AUDIT_PUBLICATION_PREFIX)
    ):
        return True
    if granted.endswith(".*"):
        prefix = granted[:-2]
        return required == prefix or required.startswith(f"{prefix}.")
    return False


def permissions_for_principal(context: PrincipalAuthorizationContext) -> FrozenSet[str]:
    role_permissions = (
        frozenset()
        if context.permission_bound
        else permissions_for_role(context.role)
    )
    direct_permissions = frozenset(
        permission
        for permission in normalize_permission_grants(context.granted_permissions)
    )
    if context.auth_provider != "service_token":
        return role_permissions.union(direct_permissions)
    scope_permissions = permissions_for_service_token_scopes(context.scopes)
    # Service tokens keep role ceilings and explicit scope grants.
    return frozenset(permission for permission in role_permissions if permission in scope_permissions)


def has_required_permission(
    context: PrincipalAuthorizationContext,
    required_permission: str | None,
) -> bool:
    if required_permission is None:
        return True
    normalized_required = _normalize_required_permission(required_permission)
    return any(
        _granted_permission_satisfies_required(granted, normalized_required)
        for granted in permissions_for_principal(context)
    )
