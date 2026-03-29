"""Stage 6 — Integration Adapter Contracts.

Defines the generic adapter model: manifest, runtime status, and the three
direction protocols (IngestAdapter, PublishAdapter, ActionAdapter).

Design rules
------------
- ``AdapterManifest`` is a static declaration; it must not carry live handles.
- ``AdapterRuntimeStatus`` is the typed snapshot returned by ``get_status()``.
- Protocol classes use ``runtime_checkable`` so ``isinstance`` checks work at
  the adapter registration boundary without requiring inheritance.
- HA-specific details stay in the HA adapter wrappers, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Direction and capability vocabulary
# ---------------------------------------------------------------------------


class AdapterDirection(str, Enum):
    """The three directions an adapter can participate in."""

    INGEST = "ingest"
    PUBLISH = "publish"
    ACTION = "action"


# ---------------------------------------------------------------------------
# AdapterManifest — static registration record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdapterManifest:
    """Static declaration of an adapter's identity and capabilities.

    This is a contract surface, not a runtime object.  It is sufficient to
    validate whether an adapter can be activated before any live connection
    is opened.  Live handles, counters, and last-seen timestamps belong in
    ``AdapterRuntimeStatus``.

    Parameters
    ----------
    adapter_key:
        Stable identifier used for registration and diagnostics.
    display_name:
        Operator-facing name shown in status surfaces.
    version:
        Adapter contract or package version string.
    supported_directions:
        One or more of ``AdapterDirection.INGEST``, ``PUBLISH``, ``ACTION``.
    supported_entity_classes:
        Canonical entity classes the adapter can read or produce.
    credential_requirements:
        Names of required secrets, tokens, or external auth references.
    health_check_contract:
        Human-readable description of how liveness is assessed.
    target_capabilities:
        Adapter-specific feature flags downstream code may rely on.
    """

    adapter_key: str
    display_name: str
    version: str
    supported_directions: tuple[AdapterDirection, ...]
    supported_entity_classes: tuple[str, ...] = field(default_factory=tuple)
    credential_requirements: tuple[str, ...] = field(default_factory=tuple)
    health_check_contract: str = ""
    target_capabilities: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# AdapterRuntimeStatus — typed live snapshot
# ---------------------------------------------------------------------------


@dataclass
class AdapterRuntimeStatus:
    """Typed runtime snapshot returned by any adapter's ``get_status()`` call.

    The shared fields cover the four health dimensions all adapters expose:

    - ``enabled``: whether the adapter is configured and participating.
    - ``connected``: whether the live transport is currently attached.
    - ``last_activity_at``: ISO-8601 timestamp of the most recent successful
      sync, publish, or dispatch.  ``None`` when the adapter has not yet
      completed any operation.
    - ``error_count``: cumulative error counter since startup.

    Adapters may supply extra domain-specific fields via ``extra``.  Callers
    that need the full picture can inspect ``extra``; callers that only care
    about health can rely on the four shared fields being stable across all
    adapter types.
    """

    enabled: bool
    connected: bool
    last_activity_at: str | None
    error_count: int
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Flatten to a JSON-serialisable dict for API responses."""
        result: dict[str, Any] = {
            "enabled": self.enabled,
            "connected": self.connected,
            "last_activity_at": self.last_activity_at,
            "error_count": self.error_count,
        }
        result.update(self.extra)
        return result


# ---------------------------------------------------------------------------
# Direction protocol types
# ---------------------------------------------------------------------------


@runtime_checkable
class IngestAdapter(Protocol):
    """Protocol for adapters that pull state from an external system.

    Required lifecycle responsibilities
    ------------------------------------
    connect → stream_or_poll → normalize → disconnect

    The adapter is responsible for
    --------------------------------
    - translating source-specific objects into canonical platform entities
    - resolving entity identity and naming instability
    - preserving checkpoint or cursor state when the source supports it

    Source-specific protocol details must not leak into the core model.
    """

    manifest: AdapterManifest

    def get_status(self) -> AdapterRuntimeStatus:
        ...  # pragma: no cover


@runtime_checkable
class PublishAdapter(Protocol):
    """Protocol for adapters that push platform state to an external system.

    Required lifecycle responsibilities
    ------------------------------------
    connect → format → publish → disconnect

    The adapter is responsible for
    --------------------------------
    - mapping canonical platform state to the target system's publication shape
    - carrying freshness and provenance metadata where the target supports it
    - making publication failures explicit rather than silently dropping updates
    """

    manifest: AdapterManifest

    def get_status(self) -> AdapterRuntimeStatus:
        ...  # pragma: no cover


@runtime_checkable
class ActionAdapter(Protocol):
    """Protocol for adapters that dispatch commands to an external system.

    Required lifecycle responsibilities
    ------------------------------------
    validate → dispatch → report_result → disconnect (when required)

    The adapter is responsible for
    --------------------------------
    - checking whether an action is supported before dispatch
    - surfacing approval or safety gates where the target requires them
    - returning a durable result that can be audited later
    """

    manifest: AdapterManifest

    def get_status(self) -> AdapterRuntimeStatus:
        ...  # pragma: no cover
