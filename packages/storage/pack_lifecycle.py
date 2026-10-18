"""Pack lifecycle records: operator-governed install state for extension packs.

``pack_installations`` holds the current state of each installed extension
pack: the installed version and the cached registry entry it came from
(registry source, revision and entry digest), the version parked for
rollback, an optional operator pin, enablement, the versions the registry
cache offered at the last lifecycle action, and the compatibility
diagnostics snapshot taken when that action was planned.

``pack_lifecycle_events`` is the append-only audit history: every applied or
refused install, upgrade, rollback, disable, enable, pin and unpin with the
acting identity, the operator's reason, the compatibility snapshot and the
dry-run plan that was evaluated. Events are never edited.

State changes go through :meth:`PackLifecycleStore.apply_pack_lifecycle_change`,
which writes the new installation row and its event in one transaction and
refuses (``PackLifecycleConflictError``) when the stored state no longer
matches what the caller planned against, so two operators cannot interleave
an upgrade and a rollback on stale reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

PACK_LIFECYCLE_ACTIONS = frozenset(
    {"install", "upgrade", "rollback", "disable", "enable", "pin", "unpin"}
)
PACK_LIFECYCLE_OUTCOMES = frozenset({"applied", "refused"})


class PackLifecycleConflictError(RuntimeError):
    """The stored installation changed after the caller planned against it."""


@dataclass(frozen=True)
class PackLifecycleActor:
    actor: str
    actor_role: str | None
    actor_auth_provider: str
    actor_authenticated: bool


@dataclass(frozen=True)
class PackInstallationRecord:
    pack_key: str
    display_name: str
    pack_kind: str
    trust_level: str
    installed_version: str
    previous_version: str | None
    pinned_version: str | None
    enabled: bool
    extension_registry_source_id: str
    extension_registry_revision_id: str
    entry_digest: str
    previous_entry_digest: str | None
    available_versions: str  # JSON list of version strings
    compatibility_snapshot: str  # JSON document
    installed_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PackLifecycleEventCreate:
    event_id: str
    pack_key: str
    action: str
    outcome: str
    from_version: str | None
    to_version: str | None
    reason: str
    extension_registry_source_id: str | None
    extension_registry_revision_id: str | None
    entry_digest: str | None
    compatibility_snapshot: str  # JSON document
    plan: str  # JSON document of the evaluated dry-run plan
    actor: PackLifecycleActor
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PackLifecycleEventRecord:
    event_id: str
    pack_key: str
    action: str
    outcome: str
    from_version: str | None
    to_version: str | None
    reason: str
    extension_registry_source_id: str | None
    extension_registry_revision_id: str | None
    entry_digest: str | None
    compatibility_snapshot: str
    plan: str
    actor: PackLifecycleActor
    occurred_at: datetime


@dataclass(frozen=True)
class PackStateExpectation:
    """What the caller planned against; ``None`` installed_version = not installed."""

    installed_version: str | None
    enabled: bool | None = None
    pinned_version: str | None = None


@runtime_checkable
class PackLifecycleStore(Protocol):
    def get_pack_installation(self, pack_key: str) -> PackInstallationRecord | None: ...

    def list_pack_installations(self) -> list[PackInstallationRecord]: ...

    def apply_pack_lifecycle_change(
        self,
        installation: PackInstallationRecord,
        event: PackLifecycleEventCreate,
        *,
        expected: PackStateExpectation,
    ) -> PackLifecycleEventRecord: ...

    def record_pack_lifecycle_event(
        self, event: PackLifecycleEventCreate
    ) -> PackLifecycleEventRecord: ...

    def list_pack_lifecycle_events(
        self, *, pack_key: str | None = None, limit: int | None = None
    ) -> list[PackLifecycleEventRecord]: ...


def aware_utc(value: datetime) -> datetime:
    """Normalize storage timestamps to aware UTC; naive values are UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return aware_utc(value)
    if isinstance(value, str):
        return aware_utc(datetime.fromisoformat(value))
    raise TypeError(f"Unsupported datetime value: {value!r}")


def validate_event(event: PackLifecycleEventCreate) -> None:
    if event.action not in PACK_LIFECYCLE_ACTIONS:
        raise ValueError(f"Unknown pack lifecycle action: {event.action!r}")
    if event.outcome not in PACK_LIFECYCLE_OUTCOMES:
        raise ValueError(f"Unknown pack lifecycle outcome: {event.outcome!r}")
    if not event.reason.strip():
        raise ValueError("Pack lifecycle events require a non-empty reason.")


def matches_expectation(
    current: PackInstallationRecord | None, expected: PackStateExpectation
) -> bool:
    if current is None:
        return expected.installed_version is None
    if current.installed_version != expected.installed_version:
        return False
    if expected.enabled is not None and current.enabled != expected.enabled:
        return False
    return current.pinned_version == expected.pinned_version
