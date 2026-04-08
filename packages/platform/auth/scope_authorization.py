"""Generic route authorization lookup helpers."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from packages.platform.auth.contracts import UserRole
from packages.platform.auth.route_policy_engine import (
    RouteAuthorizationLookup,
    RoutePolicy,
)


def build_route_authorization_lookup(
    route_policies: Iterable[RoutePolicy],
) -> RouteAuthorizationLookup:
    return RouteAuthorizationLookup(tuple(route_policies))


def required_permission_for_path(
    lookup: RouteAuthorizationLookup,
    path: str,
) -> str | None:
    return lookup.required_permission_for_path(path)


def required_permission_for_request(
    lookup: RouteAuthorizationLookup,
    path: str,
    query_params: Mapping[str, str] | None = None,
    method: str | None = None,
) -> str | None:
    return lookup.required_permission_for_request(
        path,
        query_params=query_params,
        method=method,
    )


def required_role_for_request(
    lookup: RouteAuthorizationLookup,
    path: str,
    method: str | None = None,
) -> UserRole | None:
    return lookup.required_role_for_request(path, method)


def required_service_token_scope_for_request(
    lookup: RouteAuthorizationLookup,
    path: str,
    method: str | None = None,
) -> str | None:
    return lookup.required_service_token_scope_for_request(path, method)


def required_role_for_path(
    lookup: RouteAuthorizationLookup,
    path: str,
) -> UserRole | None:
    return lookup.required_role_for_path(path)


def required_service_token_scope_for_path(
    lookup: RouteAuthorizationLookup,
    path: str,
) -> str | None:
    return lookup.required_service_token_scope_for_path(path)
