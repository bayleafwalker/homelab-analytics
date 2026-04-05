"""Shared typed runtime status model for integration adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdapterRuntimeStatus:
    """Typed runtime snapshot returned by adapter-facing status methods."""

    enabled: bool
    connected: bool
    last_activity_at: str | None
    error_count: int
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "enabled": self.enabled,
            "connected": self.connected,
            "last_activity_at": self.last_activity_at,
            "error_count": self.error_count,
        }
        result.update(self.extra)
        return result
