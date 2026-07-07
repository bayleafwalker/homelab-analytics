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
        One or more of ``AdapterDirection.INGEST``, ``PUBLISH``, ``ACTION``,
        ``OBSERVE``. OBSERVE adapters read platform state for external
        observability consumers; no ObserveAdapter protocol is defined yet.
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
class CanonicalEntityId:
    """Canonical identifier for a physical or logical household entity.

    Adapters may see the same real-world entity through different source
    identifiers (``sensor.heat_pump_power`` in Home Assistant,
    ``hp_power_watts`` in Prometheus). A ``CanonicalEntityId`` names the
    entity once so cross-adapter reads and cross-domain reasoning share
    a single identity. ``entity_class`` maps to the vocabulary listed in
    ``AdapterManifest.supported_entity_classes``.
    """

    entity_class: str
    canonical_key: str


@dataclass(frozen=True)
class EntityAlias:
    """One adapter's binding of a source identifier to a canonical entity.

    Aliases are declarative: an adapter says "in my namespace,
    ``source_entity_id`` refers to ``CanonicalEntityId(entity_class,
    canonical_key)``". Multiple adapters may register aliases for the
    same canonical entity and that is exactly the correlation. Two
    registrations with the same ``(adapter_key, entity_class,
    source_entity_id)`` are a conflict and are resolved by trust: a
    higher-trust alias replaces a lower-trust one; equal trust favours
    the latest registration.
    """

    adapter_key: str
    entity_class: str
    source_entity_id: str
    canonical_key: str
    trust_level: "TrustLevel"

    @property
    def canonical_id(self) -> CanonicalEntityId:
        return CanonicalEntityId(
            entity_class=self.entity_class, canonical_key=self.canonical_key
        )


@dataclass(frozen=True)
class RendererManifest:
    """Static declaration of a renderer's identity and output formats."""

    renderer_key: str
    display_name: str
    version: str
    supported_formats: tuple[str, ...]     # e.g. ("csv", "json")
    supported_publication_keys: tuple[str, ...] = field(default_factory=tuple)
    # Empty means "all publications"
    supported_publication_versions: tuple[str, ...] = field(default_factory=tuple)
    # Empty means "any publication schema_version"


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


PACK_KIND_ADAPTER = "adapter"
PACK_KIND_DOMAIN = "domain"
PACK_KIND_REPORTING = "reporting"
PACK_KIND_AUTOMATION = "automation"

VALID_PACK_KINDS: frozenset[str] = frozenset(
    {PACK_KIND_ADAPTER, PACK_KIND_DOMAIN, PACK_KIND_REPORTING, PACK_KIND_AUTOMATION}
)


@dataclass(frozen=True)
class PackManifest:
    """Unified identity, versioning, and dependency declaration for a pack.

    ``PackManifest`` names any capability pack — adapter, domain,
    reporting, or automation — with a stable pack_key, a version, a
    trust level, an optional platform-version constraint, declared
    pack-level dependencies, and the publication keys the pack
    contributes or requires.

    An ``AdapterPack`` is the adapter-flavoured specialization that
    additionally carries adapter and renderer manifests; ``AdapterPack``
    exposes ``to_pack_manifest()`` so lifecycle and compatibility
    checkers can treat every pack uniformly.
    """

    pack_key: str
    display_name: str
    version: str
    trust_level: TrustLevel
    pack_kind: str = PACK_KIND_ADAPTER
    description: str = ""
    requires_platform_version: str = ""
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    publication_relations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdapterPack:
    """A named, versioned bundle of adapters and/or renderers.

    ``AdapterPack`` is the adapter-flavoured specialization of
    :class:`PackManifest`. Call ``to_pack_manifest()`` to obtain the
    unified manifest view used by lifecycle and compatibility checks.
    """

    pack_key: str                                        # Stable identifier
    display_name: str
    version: str
    trust_level: TrustLevel
    adapters: tuple[AdapterManifest, ...] = field(default_factory=tuple)
    renderers: tuple[RendererManifest, ...] = field(default_factory=tuple)
    description: str = ""
    requires_platform_version: str = ""                 # Semver constraint, "" = any
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    publication_relations: tuple[str, ...] = field(default_factory=tuple)

    def to_pack_manifest(self) -> PackManifest:
        return PackManifest(
            pack_key=self.pack_key,
            display_name=self.display_name,
            version=self.version,
            trust_level=self.trust_level,
            pack_kind=PACK_KIND_ADAPTER,
            description=self.description,
            requires_platform_version=self.requires_platform_version,
            dependencies=self.dependencies,
            publication_relations=self.publication_relations,
        )
