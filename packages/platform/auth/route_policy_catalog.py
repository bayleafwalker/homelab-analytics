"""Generic route policy catalog helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, cast, overload

from packages.platform.auth.contracts import UserRole
from packages.platform.auth.route_policy_engine import (
    RouteAuthorizationLookup,
    RouteContext,
)


@overload
def lookup_route_policy_value(
    lookup: RouteAuthorizationLookup,
    path: str,
    *,
    field: Literal["role"],
    method: str | None = None,
    query_params: Mapping[str, str] | None = None,
) -> UserRole | None: ...


@overload
def lookup_route_policy_value(
    lookup: RouteAuthorizationLookup,
    path: str,
    *,
    field: Literal["permission", "scope"],
    method: str | None = None,
    query_params: Mapping[str, str] | None = None,
) -> str | None: ...


@overload
def lookup_route_policy_value(
    lookup: RouteAuthorizationLookup,
    path: str,
    *,
    field: str,
    method: str | None = None,
    query_params: Mapping[str, str] | None = None,
) -> UserRole | str | None: ...


def lookup_route_policy_value(
    lookup: RouteAuthorizationLookup,
    path: str,
    *,
    field: str,
    method: str | None = None,
    query_params: Mapping[str, str] | None = None,
) -> UserRole | str | None:
    context = RouteContext(
        path=path,
        method=(method or "").upper() or None,
        query_params=query_params or {},
    )
    return cast(
        UserRole | str | None,
        lookup.lookup(
            path,
            field=field,
            method=context.method,
            query_params=context.query_params,
        ),
    )
