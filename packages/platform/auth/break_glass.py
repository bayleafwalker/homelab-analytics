"""Break-glass policy evaluation and activation state."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network
from threading import Lock

from fastapi import Request

from packages.platform.auth.credential_resolution import request_remote_addr
from packages.shared.settings import AppSettings


@dataclass(frozen=True)
class BreakGlassStatus:
    enabled: bool
    internal_only: bool
    ttl_minutes: int
    allowed_cidrs: tuple[str, ...]
    active: bool
    active_until: str | None


def _is_internal_ip(remote_addr: str) -> bool:
    candidate = ip_address(remote_addr)
    return candidate.is_private or candidate.is_loopback or candidate.is_link_local


class BreakGlassController:
    def __init__(
        self,
        *,
        enabled: bool,
        internal_only: bool,
        ttl_minutes: int,
        allowed_cidrs: tuple[str, ...],
    ) -> None:
        self.enabled = enabled
        self.internal_only = internal_only
        self.ttl_minutes = ttl_minutes
        self.allowed_cidrs = tuple(cidr.strip() for cidr in allowed_cidrs if cidr.strip())
        self._allowed_networks = tuple(ip_network(cidr) for cidr in self.allowed_cidrs)
        self._active_until: datetime | None = None
        self._lock = Lock()

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "BreakGlassController":
        return cls(
            enabled=settings.break_glass_enabled,
            internal_only=settings.break_glass_internal_only,
            ttl_minutes=settings.break_glass_ttl_minutes,
            allowed_cidrs=settings.break_glass_allowed_cidrs,
        )

    def is_request_address_allowed(self, request: Request) -> bool:
        return self.is_remote_address_allowed(request_remote_addr(request))

    def is_remote_address_allowed(self, remote_addr: str | None) -> bool:
        if remote_addr is None:
            return False
        try:
            parsed = ip_address(remote_addr)
        except ValueError:
            return False
        if self._allowed_networks:
            return any(parsed in network for network in self._allowed_networks)
        if self.internal_only:
            return _is_internal_ip(remote_addr)
        return True

    def activate(self, *, now: datetime | None = None) -> datetime:
        current = now or datetime.now(UTC)
        active_until = current + timedelta(minutes=self.ttl_minutes)
        with self._lock:
            self._active_until = active_until
        return active_until

    def clear(self) -> None:
        with self._lock:
            self._active_until = None

    def is_active(self, *, now: datetime | None = None) -> bool:
        if not self.enabled:
            return False
        current = now or datetime.now(UTC)
        with self._lock:
            if self._active_until is None:
                return False
            if self._active_until <= current:
                self._active_until = None
                return False
            return True

    def status(self, *, now: datetime | None = None) -> BreakGlassStatus:
        active = self.is_active(now=now)
        with self._lock:
            active_until = self._active_until
        return BreakGlassStatus(
            enabled=self.enabled,
            internal_only=self.internal_only,
            ttl_minutes=self.ttl_minutes,
            allowed_cidrs=self.allowed_cidrs,
            active=active,
            active_until=active_until.isoformat() if active_until else None,
        )
