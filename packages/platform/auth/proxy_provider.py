"""Trusted proxy identity provider for header-based principal construction."""
from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network

from fastapi import Request

from packages.platform.auth.credential_resolution import request_remote_addr
from packages.platform.auth.permission_registry import normalize_permission_grants
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.shared.settings import AppSettings
from packages.storage.auth_store import UserRole


class ProxyAuthenticationError(ValueError):
    """Raised when proxy identity headers are missing or invalid."""


class ProxyAuthorizationError(PermissionError):
    """Raised when a request is not from a trusted proxy source."""


_ROLE_BY_NAME = {
    "reader": UserRole.READER,
    "operator": UserRole.OPERATOR,
    "admin": UserRole.ADMIN,
}


@dataclass(frozen=True)
class ProxyProvider:
    username_header: str
    role_header: str
    permissions_header: str | None
    trusted_cidrs: tuple[str, ...]
    _trusted_networks: tuple[IPv4Network | IPv6Network, ...] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_trusted_networks",
            tuple(ip_network(cidr, strict=False) for cidr in self.trusted_cidrs),
        )

    def authenticate_request(self, request: Request) -> AuthenticatedPrincipal:
        remote_addr = request_remote_addr(request)
        if not self._is_trusted_source(remote_addr):
            raise ProxyAuthorizationError(
                "Proxy identity headers are accepted only from trusted proxy CIDRs."
            )
        raw_username = request.headers.get(self.username_header, "").strip()
        if not raw_username:
            raise ProxyAuthenticationError(
                f"Proxy identity header '{self.username_header}' is missing."
            )
        role = self._role_from_headers(request)
        permissions = self._permissions_from_headers(request)
        return AuthenticatedPrincipal(
            user_id=f"proxy:{raw_username}",
            username=raw_username,
            role=role,
            auth_provider="proxy",
            permissions=permissions,
        )

    def _is_trusted_source(self, remote_addr: str | None) -> bool:
        if not remote_addr:
            return False
        try:
            parsed = ip_address(remote_addr)
        except ValueError:
            return False
        return any(parsed in network for network in self._trusted_networks)

    def _role_from_headers(self, request: Request) -> UserRole:
        raw_role = request.headers.get(self.role_header, "reader").strip().lower()
        role = _ROLE_BY_NAME.get(raw_role)
        if role is None:
            raise ProxyAuthenticationError(
                f"Proxy role header '{self.role_header}' contains unsupported role '{raw_role}'."
            )
        return role

    def _permissions_from_headers(self, request: Request) -> tuple[str, ...]:
        if not self.permissions_header:
            return ()
        raw_permissions = request.headers.get(self.permissions_header, "").strip()
        if not raw_permissions:
            return ()
        return normalize_permission_grants(raw_permissions.split(","))


def build_proxy_provider(settings: AppSettings) -> ProxyProvider | None:
    if settings.resolved_auth_mode != "proxy":
        return None
    return ProxyProvider(
        username_header=settings.proxy_username_header,
        role_header=settings.proxy_role_header,
        permissions_header=settings.proxy_permissions_header,
        trusted_cidrs=settings.proxy_trusted_cidrs,
    )
