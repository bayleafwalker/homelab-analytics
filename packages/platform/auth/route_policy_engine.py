"""Generic route-policy primitives and lookup helpers."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal, cast, overload

from packages.platform.auth.contracts import UserRole


@dataclass(frozen=True)
class RouteContext:
    path: str
    method: str | None = None
    query_params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteDecision:
    role: UserRole | Callable[[RouteContext], UserRole | None] | None = None
    permission: str | Callable[[RouteContext], str | None] | None = None
    scope: str | Callable[[RouteContext], str | None] | None = None

    def resolve_role(self, context: RouteContext) -> UserRole | None:
        return _resolve_role_value(self.role, context)

    def resolve_permission(self, context: RouteContext) -> str | None:
        return _resolve_text_value(self.permission, context)

    def resolve_scope(self, context: RouteContext) -> str | None:
        return _resolve_text_value(self.scope, context)


@dataclass(frozen=True)
class RoutePolicy:
    exact_paths: tuple[str, ...] = ()
    prefix_paths: tuple[str, ...] = ()
    path_decision: RouteDecision | None = None
    request_decision: RouteDecision | None = None

    def matches(self, path: str) -> bool:
        if path in self.exact_paths:
            return True
        return any(_matches_prefix(path, prefix) for prefix in self.prefix_paths)


def _matches_prefix(path: str, prefix: str) -> bool:
    if prefix.endswith("/"):
        return path.startswith(prefix)
    return path == prefix or path.startswith(f"{prefix}/")


def _resolve_role_value(
    value: UserRole | Callable[[RouteContext], UserRole | None] | None,
    context: RouteContext,
) -> UserRole | None:
    if callable(value):
        resolver = cast(Callable[[RouteContext], UserRole | None], value)
        return resolver(context)
    return value


def _resolve_text_value(
    value: str | Callable[[RouteContext], str | None] | None,
    context: RouteContext,
) -> str | None:
    if callable(value):
        resolver = cast(Callable[[RouteContext], str | None], value)
        return resolver(context)
    return value


def static_route_decision(
    *,
    role: UserRole | None = None,
    permission: str | None = None,
    scope: str | None = None,
) -> RouteDecision:
    return RouteDecision(role=role, permission=permission, scope=scope)


@dataclass(frozen=True)
class RouteAuthorizationLookup:
    policies: tuple[RoutePolicy, ...]

    @overload
    def lookup(
        self,
        path: str,
        *,
        field: Literal["role"],
        method: str | None = None,
        query_params: Mapping[str, str] | None = None,
    ) -> UserRole | None: ...

    @overload
    def lookup(
        self,
        path: str,
        *,
        field: Literal["permission", "scope"],
        method: str | None = None,
        query_params: Mapping[str, str] | None = None,
    ) -> str | None: ...

    @overload
    def lookup(
        self,
        path: str,
        *,
        field: str,
        method: str | None = None,
        query_params: Mapping[str, str] | None = None,
    ) -> UserRole | str | None: ...

    def lookup(
        self,
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
        for policy in self.policies:
            if not policy.matches(path):
                continue
            decision = policy.request_decision if context.method else policy.path_decision
            if decision is None:
                decision = policy.path_decision
            if decision is None:
                continue
            value: UserRole | str | None
            if field == "role":
                value = decision.resolve_role(context)
            elif field == "permission":
                value = decision.resolve_permission(context)
            elif field == "scope":
                value = decision.resolve_scope(context)
            else:
                raise ValueError(f"Unknown route policy field: {field}")
            if value is None:
                continue
            return value
        return None

    def required_permission_for_path(self, path: str) -> str | None:
        return cast(str | None, self.lookup(path, field="permission"))

    def required_permission_for_request(
        self,
        path: str,
        query_params: Mapping[str, str] | None = None,
        method: str | None = None,
    ) -> str | None:
        request_method = (method or "GET").upper()
        return cast(
            str | None,
            self.lookup(
                path,
                field="permission",
                method=request_method,
                query_params=query_params,
            ),
        )

    def required_role_for_request(
        self,
        path: str,
        method: str | None = None,
    ) -> UserRole | None:
        request_method = (method or "GET").upper()
        return cast(UserRole | None, self.lookup(path, field="role", method=request_method))

    def required_service_token_scope_for_request(
        self,
        path: str,
        method: str | None = None,
    ) -> str | None:
        request_method = (method or "GET").upper()
        return cast(str | None, self.lookup(path, field="scope", method=request_method))

    def required_role_for_path(self, path: str) -> UserRole | None:
        return cast(UserRole | None, self.lookup(path, field="role"))

    def required_service_token_scope_for_path(self, path: str) -> str | None:
        return cast(str | None, self.lookup(path, field="scope"))
