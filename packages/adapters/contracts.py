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
from typing import Protocol, runtime_checkable

from packages.platform.adapter_runtime_status import AdapterRuntimeStatus

# ---------------------------------------------------------------------------
# Direction and capability vocabulary
# ---------------------------------------------------------------------------


class AdapterDirection(str, Enum):
    """The three directions an adapter can participate in."""

    INGEST = "ingest"
    PUBLISH = "publish"
    ACTION = "action"
    OBSERVE = "observe"


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


# ---------------------------------------------------------------------------
# Renderer contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderedOutput:
    """The result of a Renderer rendering a publication."""

    format: str          # e.g. "csv", "json"
    content: bytes
    content_type: str    # MIME type, e.g. "text/csv"
    encoding: str = "utf-8"


@dataclass(frozen=True)
class RendererManifest:
    """Static declaration of a renderer's identity and output formats."""

    renderer_key: str
    display_name: str
    version: str
    supported_formats: tuple[str, ...]     # e.g. ("csv", "json")
    supported_publication_keys: tuple[str, ...] = field(default_factory=tuple)
    # Empty means "all publications"


@runtime_checkable
class Renderer(Protocol):
    """Protocol for adapters that render publication data to a target format."""

    manifest: RendererManifest

    def render(self, publication_key: str, rows: list[dict]) -> RenderedOutput:
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Adapter pack management
# ---------------------------------------------------------------------------


class TrustLevel(str, Enum):
    """Trust level for an adapter pack, set by the operator."""

    VERIFIED = "verified"    # Platform-shipped, fully trusted
    COMMUNITY = "community"  # Third-party, elevated scrutiny
    LOCAL = "local"          # User-defined, no external verification


@dataclass(frozen=True)
class CompatibilityCheck:
    """Result of checking an adapter pack's compatibility with the platform."""

    is_compatible: bool
    issues: tuple[str, ...]     # Human-readable incompatibility reasons
    warnings: tuple[str, ...]   # Non-blocking concerns


@dataclass(frozen=True)
class AdapterPack:
    """A named, versioned bundle of adapters and/or renderers."""

    pack_key: str                                        # Stable identifier
    display_name: str
    version: str
    trust_level: TrustLevel
    adapters: tuple[AdapterManifest, ...] = field(default_factory=tuple)
    renderers: tuple[RendererManifest, ...] = field(default_factory=tuple)
    description: str = ""
    requires_platform_version: str = ""                 # Semver constraint, "" = any
