"""Path-level role and service-token scope requirements for the API."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from packages.platform.auth.contracts import UserRole
from packages.platform.auth.route_policy_catalog import ROUTE_POLICY_CATALOG
from packages.platform.auth.route_policy_engine import (
    RouteAuthorizationLookup,
    RoutePolicy,
)

DEFAULT_ROUTE_AUTHORIZATION_LOOKUP = RouteAuthorizationLookup(ROUTE_POLICY_CATALOG)


def build_route_authorization_lookup(
    route_policies: Iterable[RoutePolicy],
) -> RouteAuthorizationLookup:
    return RouteAuthorizationLookup(tuple(route_policies))


def required_permission_for_path(path: str) -> str | None:
    return DEFAULT_ROUTE_AUTHORIZATION_LOOKUP.required_permission_for_path(path)


def required_permission_for_request(
    path: str,
    query_params: Mapping[str, str] | None = None,
    method: str | None = None,
) -> str | None:
    return DEFAULT_ROUTE_AUTHORIZATION_LOOKUP.required_permission_for_request(
        path,
        query_params=query_params,
        method=method,
    )


def required_role_for_request(
    path: str,
    method: str | None = None,
) -> UserRole | None:
    return DEFAULT_ROUTE_AUTHORIZATION_LOOKUP.required_role_for_request(path, method)


def required_service_token_scope_for_request(
    path: str,
    method: str | None = None,
) -> str | None:
    return DEFAULT_ROUTE_AUTHORIZATION_LOOKUP.required_service_token_scope_for_request(
        path,
        method,
    )


def required_role_for_path(path: str) -> UserRole | None:
    return DEFAULT_ROUTE_AUTHORIZATION_LOOKUP.required_role_for_path(path)


def required_service_token_scope_for_path(path: str) -> str | None:
    return DEFAULT_ROUTE_AUTHORIZATION_LOOKUP.required_service_token_scope_for_path(path)
