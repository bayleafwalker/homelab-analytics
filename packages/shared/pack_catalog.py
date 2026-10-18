"""Pack catalog discovery over the locally cached external registry.

An external registry manifest (``homelab-analytics.registry.json``,
``schema_version`` 1) may carry an optional ``packs`` array that advertises
the packs its extension modules provide::

    {
      "schema_version": 1,
      "extension_modules": ["acme_energy_pack"],
      "packs": [
        {
          "pack_key": "acme_energy",
          "display_name": "Acme Energy",
          "version": "1.2.0",
          "pack_kind": "domain",
          "trust_level": "community",
          "requires_platform_version": ">=0.1.0",
          "dependencies": ["other_pack>=1.0"],
          "publications": [{"publication_key": "acme_tariffs", "schema_version": "1.0.0"}],
          "requires_publications": ["utility_cost_summary"]
        }
      ]
    }

The key is additive and optional, so ``schema_version`` stays 1 and
``parse_extension_registry_manifest`` ignores it.

Trust boundary: discovery only reads manifests that a previous sync already
validated and cached on local disk (``revision.manifest_path``). It never
clones, fetches or imports code; a request-time catalog read is a local file
read. Each revision's cached manifest is re-checked against the digest the
sync recorded, and every pack entry gets its own content digest so the
lifecycle can detect a cached entry that changed after it was installed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.shared.external_registry import (
    _build_manifest_digest,
    _current_platform_version,
    parse_extension_registry_manifest,
)
from packages.storage.control_plane import ExternalRegistryStore

PACK_CATALOG_MANIFEST_KEY = "packs"
PACK_CATALOG_KINDS = frozenset({"adapter", "domain", "reporting", "automation", "source"})
PACK_CATALOG_TRUST_LEVELS = frozenset({"verified", "community", "local"})


@dataclass(frozen=True)
class PackPublicationContract:
    publication_key: str
    schema_version: str

    @property
    def contract_ref(self) -> str:
        return f"{self.publication_key}@{self.schema_version}"


@dataclass(frozen=True)
class PackCatalogEntry:
    """One pack version advertised by one validated, cached registry revision."""

    pack_key: str
    display_name: str
    version: str
    pack_kind: str
    trust_level: str
    description: str
    requires_platform_version: str
    dependencies: tuple[str, ...]
    publications: tuple[PackPublicationContract, ...]
    requires_publications: tuple[str, ...]
    extension_registry_source_id: str
    source_name: str
    extension_registry_revision_id: str
    manifest_digest: str
    entry_digest: str

    @property
    def provided_publication_keys(self) -> tuple[str, ...]:
        return tuple(contract.publication_key for contract in self.publications)


@dataclass(frozen=True)
class PackDiscoveryResult:
    entries: tuple[PackCatalogEntry, ...]
    errors: tuple[str, ...]
    sources_scanned: int
    revisions_scanned: int


def current_platform_version() -> str:
    """The running platform release, as the registry sync validates against."""
    return _current_platform_version()


def manifest_core_digest(payload: dict[str, object]) -> str:
    """Digest of the registry manifest fields a sync validates (excludes ``packs``)."""
    return _build_manifest_digest(parse_extension_registry_manifest(payload))


def pack_entry_digest(raw_entry: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(raw_entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _string(raw: dict[str, Any], key: str, *, required: bool = True, default: str = "") -> str:
    value = raw.get(key, default)
    if value is None:
        value = default
    if not isinstance(value, str):
        raise ValueError(f"pack entry field {key!r} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"pack entry requires {key!r}")
    return value


def _string_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"pack entry field {key!r} must be a list of strings")
    return tuple(item.strip() for item in value if item.strip())


def parse_pack_catalog_entry(
    raw: object,
    *,
    extension_registry_source_id: str,
    source_name: str,
    extension_registry_revision_id: str,
    manifest_digest: str,
) -> PackCatalogEntry:
    if not isinstance(raw, dict):
        raise ValueError("pack entry must be an object")
    pack_key = _string(raw, "pack_key")
    pack_kind = _string(raw, "pack_kind", default="domain")
    if pack_kind not in PACK_CATALOG_KINDS:
        raise ValueError(f"pack {pack_key!r} has unsupported pack_kind {pack_kind!r}")
    trust_level = _string(raw, "trust_level", default="community")
    if trust_level not in PACK_CATALOG_TRUST_LEVELS:
        raise ValueError(f"pack {pack_key!r} has unsupported trust_level {trust_level!r}")
    raw_publications = raw.get("publications", [])
    if not isinstance(raw_publications, list):
        raise ValueError(f"pack {pack_key!r} publications must be a list")
    publications: list[PackPublicationContract] = []
    for item in raw_publications:
        if not isinstance(item, dict):
            raise ValueError(f"pack {pack_key!r} publication entries must be objects")
        publications.append(
            PackPublicationContract(
                publication_key=_string(item, "publication_key"),
                schema_version=_string(item, "schema_version", default="1.0.0"),
            )
        )
    keys = [contract.publication_key for contract in publications]
    if len(keys) != len(set(keys)):
        raise ValueError(f"pack {pack_key!r} declares a publication twice")
    return PackCatalogEntry(
        pack_key=pack_key,
        display_name=_string(raw, "display_name", required=False) or pack_key,
        version=_string(raw, "version"),
        pack_kind=pack_kind,
        trust_level=trust_level,
        description=_string(raw, "description", required=False),
        requires_platform_version=_string(raw, "requires_platform_version", required=False),
        dependencies=_string_tuple(raw, "dependencies"),
        publications=tuple(publications),
        requires_publications=_string_tuple(raw, "requires_publications"),
        extension_registry_source_id=extension_registry_source_id,
        source_name=source_name,
        extension_registry_revision_id=extension_registry_revision_id,
        manifest_digest=manifest_digest,
        entry_digest=pack_entry_digest(raw),
    )


def discover_cached_pack_entries(
    store: ExternalRegistryStore,
    *,
    read_text: Callable[[Path], str] | None = None,
) -> PackDiscoveryResult:
    """List pack entries from validated revisions of enabled registry sources.

    Newest revision wins when two revisions advertise the same pack version.
    Problems (missing cache file, manifest changed since sync, malformed
    entries) are reported in ``errors`` and never raise, so one bad source
    cannot hide the rest of the catalog.
    """
    reader = read_text or (lambda path: path.read_text(encoding="utf-8"))
    entries: dict[tuple[str, str], PackCatalogEntry] = {}
    errors: list[str] = []
    sources = [
        source
        for source in store.list_extension_registry_sources()
        if source.enabled and not source.archived
    ]
    revisions_scanned = 0
    for source in sources:
        revisions = sorted(
            (
                revision
                for revision in store.list_extension_registry_revisions(
                    extension_registry_source_id=source.extension_registry_source_id
                )
                if revision.sync_status == "validated" and revision.manifest_path
            ),
            key=lambda revision: revision.created_at,
            reverse=True,
        )
        for revision in revisions:
            revisions_scanned += 1
            label = f"{source.name} revision {revision.extension_registry_revision_id}"
            manifest_path = Path(str(revision.manifest_path))
            try:
                payload = json.loads(reader(manifest_path))
            except FileNotFoundError:
                errors.append(f"{label}: cached manifest is missing ({manifest_path})")
                continue
            except (OSError, ValueError) as exc:
                errors.append(f"{label}: cached manifest is unreadable ({exc})")
                continue
            if not isinstance(payload, dict):
                errors.append(f"{label}: cached manifest is not an object")
                continue
            try:
                digest = manifest_core_digest(payload)
            except ValueError as exc:
                errors.append(f"{label}: cached manifest is invalid ({exc})")
                continue
            if revision.manifest_digest and digest != revision.manifest_digest:
                errors.append(
                    f"{label}: cached manifest changed since it was synced; re-sync the source"
                )
                continue
            raw_entries = payload.get(PACK_CATALOG_MANIFEST_KEY, [])
            if not isinstance(raw_entries, list):
                errors.append(f"{label}: 'packs' must be a list")
                continue
            for raw in raw_entries:
                try:
                    entry = parse_pack_catalog_entry(
                        raw,
                        extension_registry_source_id=source.extension_registry_source_id,
                        source_name=source.name,
                        extension_registry_revision_id=revision.extension_registry_revision_id,
                        manifest_digest=digest,
                    )
                except ValueError as exc:
                    errors.append(f"{label}: {exc}")
                    continue
                key = (entry.pack_key, entry.version)
                existing = entries.get(key)
                if existing is None:
                    entries[key] = entry
                elif existing.extension_registry_source_id != entry.extension_registry_source_id:
                    errors.append(
                        f"{entry.pack_key} {entry.version} is advertised by more than one "
                        f"source; using {existing.source_name}"
                    )
    ordered = tuple(sorted(entries.values(), key=lambda entry: (entry.pack_key, entry.version)))
    return PackDiscoveryResult(
        entries=ordered,
        errors=tuple(errors),
        sources_scanned=len(sources),
        revisions_scanned=revisions_scanned,
    )


__all__ = [
    "PACK_CATALOG_MANIFEST_KEY",
    "PackCatalogEntry",
    "PackDiscoveryResult",
    "PackPublicationContract",
    "current_platform_version",
    "discover_cached_pack_entries",
    "manifest_core_digest",
    "pack_entry_digest",
    "parse_pack_catalog_entry",
]
