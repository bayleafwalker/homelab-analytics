"""Path-level role and service-token scope requirements for the API."""
from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from packages.platform.auth.route_policy_catalog import lookup_route_policy_value
from packages.storage.auth_store import UserRole


def required_permission_for_path(path: str) -> str | None:
    return cast(
        str | None,
        lookup_route_policy_value(path, field="permission"),
    )


def required_permission_for_request(
    path: str,
    query_params: Mapping[str, str] | None = None,
    method: str | None = None,
) -> str | None:
    request_method = (method or "GET").upper()
    return cast(
        str | None,
        lookup_route_policy_value(
            path,
            field="permission",
            method=request_method,
            query_params=query_params,
        ),
    )


def required_role_for_request(
    path: str,
    method: str | None = None,
) -> UserRole | None:
    request_method = (method or "GET").upper()
    return cast(
        UserRole | None,
        lookup_route_policy_value(path, field="role", method=request_method),
    )


def required_service_token_scope_for_request(
    path: str,
    method: str | None = None,
) -> str | None:
    request_method = (method or "GET").upper()
    return cast(
        str | None,
        lookup_route_policy_value(path, field="scope", method=request_method),
    )


def required_role_for_path(path: str) -> UserRole | None:
    return cast(UserRole | None, lookup_route_policy_value(path, field="role"))


def required_service_token_scope_for_path(path: str) -> str | None:
    return cast(str | None, lookup_route_policy_value(path, field="scope"))
