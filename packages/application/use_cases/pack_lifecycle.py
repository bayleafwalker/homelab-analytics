"""Operator pack lifecycle: discover, check, plan and apply pack changes.

The lifecycle governs extension packs advertised by the locally cached
external registry (see ``packages.shared.pack_catalog``). State lives in the
control plane (``PackLifecycleStore``); every applied *and* every refused
change is written to the append-only lifecycle history with the actor and
the operator's reason.

State machine (per ``pack_key``)::

    not_installed --install--> enabled
    enabled  --disable--> disabled        disabled --enable--> enabled
    enabled|disabled --upgrade--> same enablement, newer version
                     (installed version parked as the rollback target)
    enabled|disabled --rollback--> same enablement, parked version
                     (current version parked, so rollback is reversible)
    enabled|disabled --pin/unpin--> pinned_version set / cleared

Safety refusals (any blocking diagnostic refuses the change):

- the transition is not legal from the current state;
- the pack is pinned and the change targets another version;
- the target version is not in the validated local registry cache, or its
  cached entry changed since it was installed (rollback/enable re-verify);
- an external registry entry self-declares ``verified`` trust;
- ``PackCompatibilityChecker`` reports a platform or dependency issue;
- the target would provide a publication another pack already provides;
- the change would remove a publication, or change its schema major version,
  while another enabled pack requires it;
- the change would leave an enabled pack's declared dependency unsatisfied.

``plan_pack_change`` is the dry run: it computes the same plan without
writing anything. Nothing here fetches from the network or imports pack
code; runtime loading of extension modules still follows the external
registry activation path.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from packages.adapters.contracts import PackManifest, TrustLevel
from packages.adapters.pack_compatibility import PackCompatibilityChecker, satisfies_constraint
from packages.platform.capability_types import CapabilityPack
from packages.shared.pack_catalog import PackCatalogEntry, discover_cached_pack_entries
from packages.storage.pack_lifecycle import (
    PACK_LIFECYCLE_ACTIONS,
    PackInstallationRecord,
    PackLifecycleActor,
    PackLifecycleEventCreate,
    PackLifecycleEventRecord,
    PackLifecycleStore,
    PackStateExpectation,
)

MAX_REASON_LENGTH = 500


class PackLifecycleValidationError(ValueError):
    """The request itself is malformed (unknown action, missing reason)."""


class PackChangeRefusedError(RuntimeError):
    """The plan has blocking diagnostics; the refusal was recorded."""

    def __init__(self, plan: PackChangePlan, event: PackLifecycleEventRecord) -> None:
        super().__init__(plan.summary())
        self.plan = plan
        self.event = event


@dataclass(frozen=True)
class PackDiagnostic:
    code: str
    severity: str  # "blocking" | "warning"
    message: str
    publication_key: str | None = None
    pack_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "publication_key": self.publication_key,
            "pack_key": self.pack_key,
        }


@dataclass(frozen=True)
class PublicationChange:
    publication_key: str
    change: str  # added | removed | schema_changed | unchanged
    from_schema_version: str | None
    to_schema_version: str | None
    breaking: bool
    dependents: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "publication_key": self.publication_key,
            "change": self.change,
            "from_schema_version": self.from_schema_version,
            "to_schema_version": self.to_schema_version,
            "breaking": self.breaking,
            "dependents": list(self.dependents),
        }


@dataclass(frozen=True)
class PackChangePlan:
    pack_key: str
    action: str
    from_version: str | None
    to_version: str | None
    from_enabled: bool | None
    to_enabled: bool | None
    platform_version: str
    target: PackCatalogEntry | None
    diagnostics: tuple[PackDiagnostic, ...]
    publication_changes: tuple[PublicationChange, ...]
    checked_at: datetime

    @property
    def allowed(self) -> bool:
        return not any(d.severity == "blocking" for d in self.diagnostics)

    @property
    def compatibility_status(self) -> str:
        if not self.allowed:
            return "incompatible"
        if self.diagnostics:
            return "warning"
        return "compatible"

    @property
    def contracts_affected(self) -> tuple[str, ...]:
        refs: list[str] = []
        for change in self.publication_changes:
            if change.change == "unchanged":
                continue
            version = change.to_schema_version or change.from_schema_version
            refs.append(f"{change.publication_key}@{version}")
        return tuple(refs)

    def summary(self) -> str:
        blocking = [d.message for d in self.diagnostics if d.severity == "blocking"]
        if not blocking:
            return f"{self.action} {self.pack_key} is allowed"
        return f"{self.action} {self.pack_key} refused: " + "; ".join(blocking)

    def compatibility_snapshot(self) -> dict[str, Any]:
        return {
            "status": self.compatibility_status,
            "platform_version": self.platform_version,
            "checked_at": self.checked_at.isoformat(),
            "issues": [d.message for d in self.diagnostics if d.severity == "blocking"],
            "warnings": [d.message for d in self.diagnostics if d.severity == "warning"],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_key": self.pack_key,
            "action": self.action,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "from_enabled": self.from_enabled,
            "to_enabled": self.to_enabled,
            "allowed": self.allowed,
            "compatibility_status": self.compatibility_status,
            "platform_version": self.platform_version,
            "checked_at": self.checked_at.isoformat(),
            "source": (
                {
                    "extension_registry_source_id": self.target.extension_registry_source_id,
                    "source_name": self.target.source_name,
                    "extension_registry_revision_id": self.target.extension_registry_revision_id,
                    "entry_digest": self.target.entry_digest,
                }
                if self.target is not None
                else None
            ),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "publication_changes": [c.to_dict() for c in self.publication_changes],
            "contracts_affected": list(self.contracts_affected),
        }


@dataclass(frozen=True)
class PackChangeResult:
    plan: PackChangePlan
    dry_run: bool
    event: PackLifecycleEventRecord | None = None
    installation: PackInstallationRecord | None = None


@dataclass(frozen=True)
class PackLifecycleContext:
    """Everything a plan is evaluated against; built per request."""

    store: PackLifecycleStore
    entries: Sequence[PackCatalogEntry]
    platform_packs: Sequence[CapabilityPack]
    platform_version: str
    discovery_errors: Sequence[str] = field(default_factory=tuple)
    sources_scanned: int = 0
    revisions_scanned: int = 0

    def entries_for(self, pack_key: str) -> list[PackCatalogEntry]:
        matches = [entry for entry in self.entries if entry.pack_key == pack_key]
        return sorted(matches, key=lambda entry: _version_key(entry.version))

    def entry(self, pack_key: str, version: str) -> PackCatalogEntry | None:
        for entry in self.entries:
            if entry.pack_key == pack_key and entry.version == version:
                return entry
        return None


def build_pack_lifecycle_context(
    store: Any,
    *,
    platform_packs: Sequence[CapabilityPack],
    platform_version: str,
) -> PackLifecycleContext:
    """Discover cached registry entries and bind them to the lifecycle store.

    ``store`` must be both an ``ExternalRegistryStore`` (discovery reads its
    validated revisions) and a ``PackLifecycleStore``.
    """
    discovery = discover_cached_pack_entries(store)
    return PackLifecycleContext(
        store=store,
        entries=discovery.entries,
        platform_packs=platform_packs,
        platform_version=platform_version,
        discovery_errors=discovery.errors,
        sources_scanned=discovery.sources_scanned,
        revisions_scanned=discovery.revisions_scanned,
    )


def actor_from_principal(principal: object | None) -> PackLifecycleActor:
    if principal is None:
        return PackLifecycleActor(
            actor="unauthenticated",
            actor_role=None,
            actor_auth_provider="disabled",
            actor_authenticated=False,
        )
    role = getattr(principal, "role", None)
    return PackLifecycleActor(
        actor=str(getattr(principal, "username", None) or getattr(principal, "user_id", "unknown")),
        actor_role=str(getattr(role, "value", role)) if role is not None else None,
        actor_auth_provider=str(getattr(principal, "auth_provider", None) or "unknown"),
        actor_authenticated=True,
    )


def _version_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.split("+", 1)[0].split("-", 1)[0].split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def _major(schema_version: str | None) -> int | None:
    if not schema_version:
        return None
    return _version_key(schema_version)[0]


def _platform_publications(context: PackLifecycleContext, *, exclude: str) -> dict[str, str]:
    """Publication key -> owning platform pack, skipping a loaded pack named ``exclude``."""
    owners: dict[str, str] = {}
    for pack in context.platform_packs:
        if pack.name == exclude:
            continue
        for publication in pack.publications:
            owners[publication.key] = pack.name
    return owners


def _installed_entries(
    context: PackLifecycleContext, *, exclude: str
) -> list[tuple[PackInstallationRecord, PackCatalogEntry | None]]:
    rows: list[tuple[PackInstallationRecord, PackCatalogEntry | None]] = []
    for installation in context.store.list_pack_installations():
        if installation.pack_key == exclude or not installation.enabled:
            continue
        rows.append(
            (installation, context.entry(installation.pack_key, installation.installed_version))
        )
    return rows


def _to_manifest(entry: PackCatalogEntry) -> PackManifest:
    return PackManifest(
        pack_key=entry.pack_key,
        display_name=entry.display_name,
        version=entry.version,
        trust_level=TrustLevel(entry.trust_level),
        pack_kind=entry.pack_kind,
        description=entry.description,
        requires_platform_version=entry.requires_platform_version,
        dependencies=entry.dependencies,
        publication_relations=entry.provided_publication_keys + entry.requires_publications,
    )


def assess_entry(
    context: PackLifecycleContext,
    entry: PackCatalogEntry,
) -> list[PackDiagnostic]:
    """Compatibility of one cached entry against the platform and enabled packs."""
    diagnostics: list[PackDiagnostic] = []
    if entry.trust_level == TrustLevel.VERIFIED.value:
        diagnostics.append(
            PackDiagnostic(
                code="untrusted_verified_claim",
                severity="blocking",
                message=(
                    "external registry entries cannot declare verified trust; "
                    "verified is reserved for platform-shipped packs"
                ),
            )
        )
    platform_owners = _platform_publications(context, exclude=entry.pack_key)
    installed = _installed_entries(context, exclude=entry.pack_key)
    installed_manifests: dict[str, PackManifest] = {
        pack.name: PackManifest(
            pack_key=pack.name,
            display_name=pack.name,
            version=pack.version,
            trust_level=TrustLevel.VERIFIED,
        )
        for pack in context.platform_packs
    }
    known_publications = set(platform_owners)
    known_publications.update(entry.provided_publication_keys)
    installed_owners: dict[str, str] = {}
    for installation, installed_entry in installed:
        if installed_entry is not None:
            installed_manifests[installation.pack_key] = _to_manifest(installed_entry)
            for key in installed_entry.provided_publication_keys:
                installed_owners[key] = installation.pack_key
                known_publications.add(key)
        else:
            installed_manifests[installation.pack_key] = PackManifest(
                pack_key=installation.pack_key,
                display_name=installation.display_name,
                version=installation.installed_version,
                trust_level=TrustLevel(installation.trust_level),
            )
    check = PackCompatibilityChecker(
        platform_version=context.platform_version,
        installed_packs=installed_manifests,
        known_publication_keys=frozenset(known_publications),
    ).check(_to_manifest(entry))
    diagnostics.extend(
        PackDiagnostic(code="compatibility", severity="blocking", message=issue)
        for issue in check.issues
    )
    diagnostics.extend(
        PackDiagnostic(code="compatibility_warning", severity="warning", message=warning)
        for warning in check.warnings
    )
    for key in entry.provided_publication_keys:
        owner = platform_owners.get(key) or installed_owners.get(key)
        if owner is not None:
            diagnostics.append(
                PackDiagnostic(
                    code="publication_conflict",
                    severity="blocking",
                    message=f"publication {key} is already provided by {owner}",
                    publication_key=key,
                    pack_key=owner,
                )
            )
    return diagnostics


def _publication_changes(
    context: PackLifecycleContext,
    pack_key: str,
    current: PackCatalogEntry | None,
    target: PackCatalogEntry | None,
) -> tuple[list[PublicationChange], list[PackDiagnostic]]:
    before = {c.publication_key: c.schema_version for c in (current.publications if current else ())}
    after = {c.publication_key: c.schema_version for c in (target.publications if target else ())}
    requirers: dict[str, list[str]] = {}
    for installation, installed_entry in _installed_entries(context, exclude=pack_key):
        if installed_entry is None:
            continue
        for key in installed_entry.requires_publications:
            requirers.setdefault(key, []).append(installation.pack_key)
    changes: list[PublicationChange] = []
    diagnostics: list[PackDiagnostic] = []
    for key in sorted(set(before) | set(after)):
        from_schema = before.get(key)
        to_schema = after.get(key)
        dependents = tuple(sorted(requirers.get(key, [])))
        if from_schema is None:
            change = "added"
        elif to_schema is None:
            change = "removed"
        elif from_schema != to_schema:
            change = "schema_changed"
        else:
            change = "unchanged"
        breaking = change == "removed" or (
            change == "schema_changed" and _major(from_schema) != _major(to_schema)
        )
        changes.append(
            PublicationChange(
                publication_key=key,
                change=change,
                from_schema_version=from_schema,
                to_schema_version=to_schema,
                breaking=breaking,
                dependents=dependents,
            )
        )
        if breaking and dependents:
            verb = "remove" if change == "removed" else "change the schema major of"
            diagnostics.append(
                PackDiagnostic(
                    code="would_break_publication",
                    severity="blocking",
                    message=(
                        f"would {verb} publication {key} required by {', '.join(dependents)}"
                    ),
                    publication_key=key,
                )
            )
        elif breaking:
            diagnostics.append(
                PackDiagnostic(
                    code="breaking_publication_change",
                    severity="warning",
                    message=f"publication {key} contract changes incompatibly ({change})",
                    publication_key=key,
                )
            )
    return changes, diagnostics


def _dependent_pack_diagnostics(
    context: PackLifecycleContext, pack_key: str, to_version: str | None
) -> list[PackDiagnostic]:
    """Enabled packs whose declared dependency on ``pack_key`` would break."""
    diagnostics: list[PackDiagnostic] = []
    for installation, installed_entry in _installed_entries(context, exclude=pack_key):
        if installed_entry is None:
            continue
        for dependency in installed_entry.dependencies:
            dep = dependency.strip()
            name = dep
            constraint = ""
            for op in (">=", "<=", "==", ">", "<"):
                index = dep.find(op)
                if index > 0:
                    name, constraint = dep[:index].strip(), dep[index:].strip()
                    break
            if name != pack_key:
                continue
            if to_version is None or not satisfies_constraint(to_version, constraint):
                diagnostics.append(
                    PackDiagnostic(
                        code="would_break_dependency",
                        severity="blocking",
                        message=(
                            f"{installation.pack_key} depends on {dependency}"
                            + (
                                "; the pack would no longer be enabled"
                                if to_version is None
                                else f"; {to_version} does not satisfy it"
                            )
                        ),
                        pack_key=installation.pack_key,
                    )
                )
    return diagnostics


def _blocking(code: str, message: str) -> PackDiagnostic:
    return PackDiagnostic(code=code, severity="blocking", message=message)


def plan_pack_change(
    context: PackLifecycleContext,
    *,
    pack_key: str,
    action: str,
    version: str | None = None,
    now: datetime | None = None,
) -> PackChangePlan:
    """Dry-run a lifecycle change; never writes."""
    if action not in PACK_LIFECYCLE_ACTIONS:
        raise PackLifecycleValidationError(f"Unknown pack lifecycle action: {action!r}")
    checked_at = now or datetime.now(UTC)
    current = context.store.get_pack_installation(pack_key)
    current_entry = (
        context.entry(pack_key, current.installed_version) if current is not None else None
    )
    diagnostics: list[PackDiagnostic] = []
    target: PackCatalogEntry | None = None
    to_version: str | None = current.installed_version if current else None
    to_enabled: bool | None = current.enabled if current else None
    # What is provided before/after, for publication diffs. A disabled pack
    # provides nothing, so enabling it "adds" its publications.
    before_entry = current_entry if current is not None and current.enabled else None
    after_entry: PackCatalogEntry | None = before_entry

    if action == "install":
        if current is not None:
            diagnostics.append(
                _blocking("illegal_transition", f"{pack_key} is already installed")
            )
        available = context.entries_for(pack_key)
        if version is None and available:
            version = available[-1].version
        target = context.entry(pack_key, version) if version else None
        to_version, to_enabled = version, True
        after_entry = target
    elif current is None:
        diagnostics.append(
            _blocking("illegal_transition", f"{pack_key} is not installed; install it first")
        )
    elif action == "upgrade":
        available = context.entries_for(pack_key)
        if version is None and available:
            version = available[-1].version
        if version is not None and version == current.installed_version:
            diagnostics.append(
                _blocking("illegal_transition", f"{pack_key} {version} is already installed")
            )
        elif version is not None and _version_key(version) < _version_key(
            current.installed_version
        ):
            diagnostics.append(
                _blocking(
                    "illegal_transition",
                    f"{version} is older than {current.installed_version}; use rollback",
                )
            )
        target = context.entry(pack_key, version) if version else None
        to_version = version
        after_entry = target if current.enabled else None
    elif action == "rollback":
        if current.previous_version is None:
            diagnostics.append(
                _blocking("no_rollback_target", f"{pack_key} has no previous version to roll back to")
            )
        else:
            target = context.entry(pack_key, current.previous_version)
            version = current.previous_version
            to_version = version
            after_entry = target if current.enabled else None
            if (
                target is not None
                and current.previous_entry_digest is not None
                and target.entry_digest != current.previous_entry_digest
            ):
                diagnostics.append(
                    _blocking(
                        "cached_entry_changed",
                        f"cached entry for {pack_key} {version} changed since it was installed",
                    )
                )
    elif action == "disable":
        if not current.enabled:
            diagnostics.append(_blocking("illegal_transition", f"{pack_key} is already disabled"))
        to_enabled = False
        after_entry = None
    elif action == "enable":
        if current.enabled:
            diagnostics.append(_blocking("illegal_transition", f"{pack_key} is already enabled"))
        target = current_entry
        version = current.installed_version
        to_enabled = True
        after_entry = target
        if target is not None and target.entry_digest != current.entry_digest:
            diagnostics.append(
                _blocking(
                    "cached_entry_changed",
                    f"cached entry for {pack_key} {version} changed since it was installed",
                )
            )
    elif action == "pin":
        if current.pinned_version is not None:
            diagnostics.append(
                _blocking("illegal_transition", f"{pack_key} is already pinned")
            )
    elif action == "unpin":
        if current.pinned_version is None:
            diagnostics.append(_blocking("illegal_transition", f"{pack_key} is not pinned"))

    target_required = action == "install" or (
        current is not None
        and (
            action in {"upgrade", "enable"}
            or (action == "rollback" and current.previous_version is not None)
        )
    )
    if target_required and target is None:
        diagnostics.append(
            _blocking(
                "not_in_registry_cache",
                (
                    f"{pack_key} {version} is not in the validated local registry cache"
                    if version
                    else f"no cached registry entry offers {pack_key}"
                ),
            )
        )
    if (
        current is not None
        and current.pinned_version is not None
        and action in {"upgrade", "rollback"}
        and to_version != current.pinned_version
    ):
        diagnostics.append(
            _blocking(
                "pinned",
                f"{pack_key} is pinned to {current.pinned_version}; unpin it first",
            )
        )

    # Compatibility and publication safety only matter when the pack will be
    # providing something after the change.
    if target is not None and (to_enabled or action == "install"):
        diagnostics.extend(assess_entry(context, target))
    if current is not None or action == "install":
        changes, change_diagnostics = _publication_changes(
            context, pack_key, before_entry, after_entry
        )
        diagnostics.extend(change_diagnostics)
    else:
        changes = []
    if current is not None and current.enabled and (
        action == "disable" or action in {"upgrade", "rollback"}
    ):
        diagnostics.extend(
            _dependent_pack_diagnostics(
                context, pack_key, None if action == "disable" else to_version
            )
        )

    return PackChangePlan(
        pack_key=pack_key,
        action=action,
        from_version=current.installed_version if current else None,
        to_version=to_version,
        from_enabled=current.enabled if current else None,
        to_enabled=to_enabled,
        platform_version=context.platform_version,
        target=target,
        diagnostics=tuple(diagnostics),
        publication_changes=tuple(changes),
        checked_at=checked_at,
    )


def _event(
    plan: PackChangePlan,
    *,
    outcome: str,
    reason: str,
    actor: PackLifecycleActor,
    installation: PackInstallationRecord | None,
) -> PackLifecycleEventCreate:
    source_id = (
        plan.target.extension_registry_source_id
        if plan.target is not None
        else (installation.extension_registry_source_id if installation else None)
    )
    revision_id = (
        plan.target.extension_registry_revision_id
        if plan.target is not None
        else (installation.extension_registry_revision_id if installation else None)
    )
    digest = (
        plan.target.entry_digest
        if plan.target is not None
        else (installation.entry_digest if installation else None)
    )
    return PackLifecycleEventCreate(
        event_id=f"packevt-{uuid4().hex}",
        pack_key=plan.pack_key,
        action=plan.action,
        outcome=outcome,
        from_version=plan.from_version,
        to_version=plan.to_version,
        reason=reason,
        extension_registry_source_id=source_id,
        extension_registry_revision_id=revision_id,
        entry_digest=digest,
        compatibility_snapshot=json.dumps(plan.compatibility_snapshot(), sort_keys=True),
        plan=json.dumps(plan.to_dict(), sort_keys=True),
        actor=actor,
        occurred_at=plan.checked_at,
    )


def _next_installation(
    context: PackLifecycleContext,
    plan: PackChangePlan,
    current: PackInstallationRecord | None,
) -> PackInstallationRecord:
    snapshot = json.dumps(plan.compatibility_snapshot(), sort_keys=True)
    available = json.dumps([entry.version for entry in context.entries_for(plan.pack_key)])
    now = plan.checked_at
    target = plan.target
    if plan.action == "install":
        assert target is not None
        return PackInstallationRecord(
            pack_key=target.pack_key,
            display_name=target.display_name,
            pack_kind=target.pack_kind,
            trust_level=target.trust_level,
            installed_version=target.version,
            previous_version=None,
            pinned_version=None,
            enabled=True,
            extension_registry_source_id=target.extension_registry_source_id,
            extension_registry_revision_id=target.extension_registry_revision_id,
            entry_digest=target.entry_digest,
            previous_entry_digest=None,
            available_versions=available,
            compatibility_snapshot=snapshot,
            installed_at=now,
            updated_at=now,
        )
    assert current is not None
    base = replace(current, available_versions=available, updated_at=now)
    if plan.action in {"upgrade", "rollback"}:
        assert target is not None
        return replace(
            base,
            display_name=target.display_name,
            pack_kind=target.pack_kind,
            trust_level=target.trust_level,
            installed_version=target.version,
            previous_version=current.installed_version,
            extension_registry_source_id=target.extension_registry_source_id,
            extension_registry_revision_id=target.extension_registry_revision_id,
            entry_digest=target.entry_digest,
            previous_entry_digest=current.entry_digest,
            compatibility_snapshot=snapshot,
        )
    if plan.action == "disable":
        return replace(base, enabled=False)
    if plan.action == "enable":
        return replace(base, enabled=True, compatibility_snapshot=snapshot)
    if plan.action == "pin":
        return replace(base, pinned_version=current.installed_version)
    return replace(base, pinned_version=None)


def apply_pack_change(
    context: PackLifecycleContext,
    *,
    pack_key: str,
    action: str,
    reason: str,
    actor: PackLifecycleActor,
    version: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> PackChangeResult:
    """Plan and, unless ``dry_run``, apply a change; refusals are recorded and raised."""
    cleaned_reason = (reason or "").strip()
    if not dry_run and not cleaned_reason:
        raise PackLifecycleValidationError("A reason is required for pack lifecycle changes.")
    if len(cleaned_reason) > MAX_REASON_LENGTH:
        raise PackLifecycleValidationError(
            f"Reason must be at most {MAX_REASON_LENGTH} characters."
        )
    plan = plan_pack_change(context, pack_key=pack_key, action=action, version=version, now=now)
    if dry_run:
        return PackChangeResult(plan=plan, dry_run=True)
    current = context.store.get_pack_installation(pack_key)
    if not plan.allowed:
        event = context.store.record_pack_lifecycle_event(
            _event(plan, outcome="refused", reason=cleaned_reason, actor=actor, installation=current)
        )
        raise PackChangeRefusedError(plan, event)
    installation = _next_installation(context, plan, current)
    expected = PackStateExpectation(
        installed_version=current.installed_version if current else None,
        enabled=current.enabled if current else None,
        pinned_version=current.pinned_version if current else None,
    )
    event = context.store.apply_pack_lifecycle_change(
        installation,
        _event(plan, outcome="applied", reason=cleaned_reason, actor=actor, installation=current),
        expected=expected,
    )
    return PackChangeResult(plan=plan, dry_run=False, event=event, installation=installation)


def _installation_dict(installation: PackInstallationRecord) -> dict[str, Any]:
    return {
        "installed_version": installation.installed_version,
        "previous_version": installation.previous_version,
        "pinned_version": installation.pinned_version,
        "enabled": installation.enabled,
        "state": "enabled" if installation.enabled else "disabled",
        "extension_registry_source_id": installation.extension_registry_source_id,
        "extension_registry_revision_id": installation.extension_registry_revision_id,
        "entry_digest": installation.entry_digest,
        "available_versions": json.loads(installation.available_versions),
        "compatibility_snapshot": json.loads(installation.compatibility_snapshot),
        "installed_at": installation.installed_at.isoformat(),
        "updated_at": installation.updated_at.isoformat(),
    }


def serialize_installation(installation: PackInstallationRecord) -> dict[str, Any]:
    return {"pack_key": installation.pack_key, **_installation_dict(installation)}


def serialize_event(event: PackLifecycleEventRecord) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "pack_key": event.pack_key,
        "action": event.action,
        "outcome": event.outcome,
        "from_version": event.from_version,
        "to_version": event.to_version,
        "reason": event.reason,
        "extension_registry_source_id": event.extension_registry_source_id,
        "extension_registry_revision_id": event.extension_registry_revision_id,
        "entry_digest": event.entry_digest,
        "compatibility_snapshot": json.loads(event.compatibility_snapshot),
        "plan": json.loads(event.plan),
        "actor": event.actor.actor,
        "actor_role": event.actor.actor_role,
        "actor_auth_provider": event.actor.actor_auth_provider,
        "actor_authenticated": event.actor.actor_authenticated,
        "occurred_at": event.occurred_at.isoformat(),
    }


def _entry_dict(
    context: PackLifecycleContext,
    entry: PackCatalogEntry,
    installation: PackInstallationRecord | None,
) -> dict[str, Any]:
    diagnostics = assess_entry(context, entry)
    blocking = [d.message for d in diagnostics if d.severity == "blocking"]
    warnings = [d.message for d in diagnostics if d.severity == "warning"]
    relation = "available"
    if installation is not None:
        if entry.version == installation.installed_version:
            relation = "installed"
        elif _version_key(entry.version) > _version_key(installation.installed_version):
            relation = "upgrade"
        elif entry.version == installation.previous_version:
            relation = "rollback"
        else:
            relation = "older"
    return {
        "version": entry.version,
        "relation": relation,
        "compatibility_status": (
            "incompatible" if blocking else ("warning" if warnings else "compatible")
        ),
        "issues": blocking,
        "warnings": warnings,
        "requires_platform_version": entry.requires_platform_version,
        "dependencies": list(entry.dependencies),
        "publications": [
            {"publication_key": c.publication_key, "schema_version": c.schema_version}
            for c in entry.publications
        ],
        "requires_publications": list(entry.requires_publications),
        "extension_registry_source_id": entry.extension_registry_source_id,
        "source_name": entry.source_name,
        "extension_registry_revision_id": entry.extension_registry_revision_id,
        "entry_digest": entry.entry_digest,
    }


def build_pack_catalog(context: PackLifecycleContext) -> dict[str, Any]:
    installations = {record.pack_key: record for record in context.store.list_pack_installations()}
    pack_keys = sorted({entry.pack_key for entry in context.entries} | set(installations))
    packs: list[dict[str, Any]] = []
    for pack_key in pack_keys:
        installation = installations.get(pack_key)
        versions = context.entries_for(pack_key)
        latest = versions[-1] if versions else None
        describing = (
            context.entry(pack_key, installation.installed_version)
            if installation is not None
            else None
        ) or latest
        version_rows = [_entry_dict(context, entry, installation) for entry in reversed(versions)]
        upgrade_available = any(row["relation"] == "upgrade" for row in version_rows)
        packs.append(
            {
                "pack_key": pack_key,
                "display_name": (
                    describing.display_name
                    if describing is not None
                    else (installation.display_name if installation else pack_key)
                ),
                "pack_kind": (
                    describing.pack_kind
                    if describing is not None
                    else (installation.pack_kind if installation else "domain")
                ),
                "trust_level": (
                    describing.trust_level
                    if describing is not None
                    else (installation.trust_level if installation else "community")
                ),
                "description": describing.description if describing is not None else "",
                "state": (
                    "not_installed"
                    if installation is None
                    else ("enabled" if installation.enabled else "disabled")
                ),
                "installation": _installation_dict(installation) if installation else None,
                "latest_version": latest.version if latest is not None else None,
                "upgrade_available": upgrade_available,
                "installed_version_cached": (
                    installation is None
                    or context.entry(pack_key, installation.installed_version) is not None
                ),
                "versions": version_rows,
            }
        )
    return {
        "platform_version": context.platform_version,
        "packs": packs,
        "platform_packs": [
            {
                "name": pack.name,
                "version": pack.version,
                "publication_count": len(pack.publications),
            }
            for pack in sorted(context.platform_packs, key=lambda pack: pack.name)
        ],
        "registry": {
            "sources_scanned": context.sources_scanned,
            "revisions_scanned": context.revisions_scanned,
            "entries": len(context.entries),
            "errors": list(context.discovery_errors),
        },
    }
