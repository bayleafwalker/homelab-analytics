from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

VALID_EXTERNAL_REGISTRY_SOURCE_KINDS = ("git", "path")
VALID_EXTERNAL_REGISTRY_SYNC_STATUSES = ("failed", "validated")


@dataclass(frozen=True)
class ExtensionRegistrySourceCreate:
    extension_registry_source_id: str
    name: str
    source_kind: str
    location: str
    desired_ref: str | None = None
    subdirectory: str | None = None
    auth_secret_name: str | None = None
    auth_secret_key: str | None = None
    enabled: bool = True
    archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ExtensionRegistrySourceRecord:
    extension_registry_source_id: str
    name: str
    source_kind: str
    location: str
    desired_ref: str | None
    subdirectory: str | None
    auth_secret_name: str | None
    auth_secret_key: str | None
    enabled: bool
    archived: bool
    created_at: datetime


@dataclass(frozen=True)
class ExtensionRegistryRevisionCreate:
    extension_registry_revision_id: str
    extension_registry_source_id: str
    resolved_ref: str | None = None
    runtime_path: str | None = None
    manifest_path: str | None = None
    manifest_digest: str | None = None
    manifest_version: int | None = None
    content_fingerprint: str | None = None
    import_paths: tuple[str, ...] = ()
    extension_modules: tuple[str, ...] = ()
    function_modules: tuple[str, ...] = ()
    minimum_platform_version: str | None = None
    sync_status: str = "validated"
    validation_error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ExtensionRegistryRevisionRecord:
    extension_registry_revision_id: str
    extension_registry_source_id: str
    resolved_ref: str | None
    runtime_path: str | None
    manifest_path: str | None
    manifest_digest: str | None
    manifest_version: int | None
    content_fingerprint: str | None
    import_paths: tuple[str, ...]
    extension_modules: tuple[str, ...]
    function_modules: tuple[str, ...]
    minimum_platform_version: str | None
    sync_status: str
    validation_error: str | None
    created_at: datetime


@dataclass(frozen=True)
class ExtensionRegistryActivationRecord:
    extension_registry_source_id: str
    extension_registry_revision_id: str
    activated_at: datetime


def validate_external_registry_source_kind(source_kind: str) -> None:
    if source_kind not in VALID_EXTERNAL_REGISTRY_SOURCE_KINDS:
        raise ValueError(
            "Unsupported external registry source kind: "
            f"{source_kind!r}. Expected one of {', '.join(VALID_EXTERNAL_REGISTRY_SOURCE_KINDS)}."
        )


def validate_external_registry_sync_status(sync_status: str) -> None:
    if sync_status not in VALID_EXTERNAL_REGISTRY_SYNC_STATUSES:
        raise ValueError(
            "Unsupported external registry sync status: "
            f"{sync_status!r}. Expected one of {', '.join(VALID_EXTERNAL_REGISTRY_SYNC_STATUSES)}."
        )


def serialize_string_tuple(values: tuple[str, ...]) -> str:
    return json.dumps(list(values))


def deserialize_string_tuple(value: str | list[object] | tuple[object, ...] | None) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return tuple(str(item) for item in json.loads(value))
