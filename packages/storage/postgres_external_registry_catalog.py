from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

import psycopg
from psycopg.rows import dict_row

from packages.storage.external_registry_catalog import (
    ExtensionRegistryActivationRecord,
    ExtensionRegistryRevisionCreate,
    ExtensionRegistryRevisionRecord,
    ExtensionRegistrySourceCreate,
    ExtensionRegistrySourceRecord,
    deserialize_string_tuple,
    validate_external_registry_source_kind,
    validate_external_registry_sync_status,
)


def _coerce_row_mapping(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise TypeError(f"Unsupported row value: {row!r}")
    return cast(dict[str, object], row)


def _coerce_datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _deserialize_extension_registry_source_row(
    row: dict[str, object],
) -> ExtensionRegistrySourceRecord:
    return ExtensionRegistrySourceRecord(
        extension_registry_source_id=str(row["extension_registry_source_id"]),
        name=str(row["name"]),
        source_kind=str(row["source_kind"]),
        location=str(row["location"]),
        desired_ref=(
            str(row["desired_ref"]) if row["desired_ref"] is not None else None
        ),
        subdirectory=(
            str(row["subdirectory"]) if row["subdirectory"] is not None else None
        ),
        auth_secret_name=(
            str(row["auth_secret_name"]) if row["auth_secret_name"] is not None else None
        ),
        auth_secret_key=(
            str(row["auth_secret_key"]) if row["auth_secret_key"] is not None else None
        ),
        enabled=bool(row["enabled"]),
        archived=bool(row["archived"]),
        created_at=_coerce_datetime_value(row["created_at"]),
    )


def _deserialize_extension_registry_revision_row(
    row: dict[str, object],
) -> ExtensionRegistryRevisionRecord:
    return ExtensionRegistryRevisionRecord(
        extension_registry_revision_id=str(row["extension_registry_revision_id"]),
        extension_registry_source_id=str(row["extension_registry_source_id"]),
        resolved_ref=(
            str(row["resolved_ref"]) if row["resolved_ref"] is not None else None
        ),
        runtime_path=(
            str(row["runtime_path"]) if row["runtime_path"] is not None else None
        ),
        manifest_path=(
            str(row["manifest_path"]) if row["manifest_path"] is not None else None
        ),
        manifest_digest=(
            str(row["manifest_digest"]) if row["manifest_digest"] is not None else None
        ),
        manifest_version=(
            int(str(row["manifest_version"])) if row["manifest_version"] is not None else None
        ),
        content_fingerprint=(
            str(row["content_fingerprint"])
            if row["content_fingerprint"] is not None
            else None
        ),
        import_paths=deserialize_string_tuple(cast("list[object] | None", row["import_paths_json"])),
        extension_modules=deserialize_string_tuple(cast("list[object] | None", row["extension_modules_json"])),
        function_modules=deserialize_string_tuple(cast("list[object] | None", row["function_modules_json"])),
        minimum_platform_version=(
            str(row["minimum_platform_version"])
            if row["minimum_platform_version"] is not None
            else None
        ),
        sync_status=str(row["sync_status"]),
        validation_error=(
            str(row["validation_error"]) if row["validation_error"] is not None else None
        ),
        created_at=_coerce_datetime_value(row["created_at"]),
    )


def _deserialize_extension_registry_activation_row(
    row: dict[str, object],
) -> ExtensionRegistryActivationRecord:
    return ExtensionRegistryActivationRecord(
        extension_registry_source_id=str(row["extension_registry_source_id"]),
        extension_registry_revision_id=str(row["extension_registry_revision_id"]),
        activated_at=_coerce_datetime_value(row["activated_at"]),
    )


class PostgresExternalRegistryCatalogMixin:
    def _connect(
        self,
        *,
        row_factory: object = None,
    ) -> psycopg.Connection[object]:
        raise NotImplementedError

    def create_extension_registry_source(
        self,
        source: ExtensionRegistrySourceCreate,
    ) -> ExtensionRegistrySourceRecord:
        validate_external_registry_source_kind(source.source_kind)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO extension_registry_sources (
                    extension_registry_source_id,
                    name,
                    source_kind,
                    location,
                    desired_ref,
                    subdirectory,
                    auth_secret_name,
                    auth_secret_key,
                    enabled,
                    archived,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source.extension_registry_source_id,
                    source.name,
                    source.source_kind,
                    source.location,
                    source.desired_ref,
                    source.subdirectory,
                    source.auth_secret_name,
                    source.auth_secret_key,
                    source.enabled,
                    source.archived,
                    source.created_at,
                ),
            )
        return self.get_extension_registry_source(source.extension_registry_source_id)

    def update_extension_registry_source(
        self,
        source: ExtensionRegistrySourceCreate,
    ) -> ExtensionRegistrySourceRecord:
        validate_external_registry_source_kind(source.source_kind)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE extension_registry_sources
                SET name = %s,
                    source_kind = %s,
                    location = %s,
                    desired_ref = %s,
                    subdirectory = %s,
                    auth_secret_name = %s,
                    auth_secret_key = %s,
                    enabled = %s,
                    archived = %s
                WHERE extension_registry_source_id = %s
                """,
                (
                    source.name,
                    source.source_kind,
                    source.location,
                    source.desired_ref,
                    source.subdirectory,
                    source.auth_secret_name,
                    source.auth_secret_key,
                    source.enabled,
                    source.archived,
                    source.extension_registry_source_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(
                f"Unknown external registry source: {source.extension_registry_source_id}"
            )
        return self.get_extension_registry_source(source.extension_registry_source_id)

    def get_extension_registry_source(
        self,
        extension_registry_source_id: str,
    ) -> ExtensionRegistrySourceRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT
                    extension_registry_source_id,
                    name,
                    source_kind,
                    location,
                    desired_ref,
                    subdirectory,
                    auth_secret_name,
                    auth_secret_key,
                    enabled,
                    archived,
                    created_at
                FROM extension_registry_sources
                WHERE extension_registry_source_id = %s
                """,
                (extension_registry_source_id,),
            ).fetchone()
        if row is None:
            raise KeyError(
                f"Unknown external registry source: {extension_registry_source_id}"
            )
        return _deserialize_extension_registry_source_row(_coerce_row_mapping(row))

    def list_extension_registry_sources(
        self,
        *,
        include_archived: bool = False,
    ) -> list[ExtensionRegistrySourceRecord]:
        with self._connect(row_factory=dict_row) as connection:
            sql = """
                SELECT
                    extension_registry_source_id,
                    name,
                    source_kind,
                    location,
                    desired_ref,
                    subdirectory,
                    auth_secret_name,
                    auth_secret_key,
                    enabled,
                    archived,
                    created_at
                FROM extension_registry_sources
            """
            if not include_archived:
                sql += " WHERE archived = FALSE"
            sql += " ORDER BY created_at, extension_registry_source_id"
            rows = connection.execute(sql).fetchall()
        return [
            _deserialize_extension_registry_source_row(_coerce_row_mapping(row))
            for row in rows
        ]

    def set_extension_registry_source_archived_state(
        self,
        extension_registry_source_id: str,
        *,
        archived: bool,
    ) -> ExtensionRegistrySourceRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE extension_registry_sources
                SET archived = %s
                WHERE extension_registry_source_id = %s
                """,
                (archived, extension_registry_source_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(
                f"Unknown external registry source: {extension_registry_source_id}"
            )
        return self.get_extension_registry_source(extension_registry_source_id)

    def create_extension_registry_revision(
        self,
        revision: ExtensionRegistryRevisionCreate,
    ) -> ExtensionRegistryRevisionRecord:
        validate_external_registry_sync_status(revision.sync_status)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO extension_registry_revisions (
                    extension_registry_revision_id,
                    extension_registry_source_id,
                    resolved_ref,
                    runtime_path,
                    manifest_path,
                    manifest_digest,
                    manifest_version,
                    content_fingerprint,
                    import_paths_json,
                    extension_modules_json,
                    function_modules_json,
                    minimum_platform_version,
                    sync_status,
                    validation_error,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
                """,
                (
                    revision.extension_registry_revision_id,
                    revision.extension_registry_source_id,
                    revision.resolved_ref,
                    revision.runtime_path,
                    revision.manifest_path,
                    revision.manifest_digest,
                    revision.manifest_version,
                    revision.content_fingerprint,
                    json.dumps(list(revision.import_paths)),
                    json.dumps(list(revision.extension_modules)),
                    json.dumps(list(revision.function_modules)),
                    revision.minimum_platform_version,
                    revision.sync_status,
                    revision.validation_error,
                    revision.created_at,
                ),
            )
        return self.get_extension_registry_revision(revision.extension_registry_revision_id)

    def get_extension_registry_revision(
        self,
        extension_registry_revision_id: str,
    ) -> ExtensionRegistryRevisionRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT
                    extension_registry_revision_id,
                    extension_registry_source_id,
                    resolved_ref,
                    runtime_path,
                    manifest_path,
                    manifest_digest,
                    manifest_version,
                    content_fingerprint,
                    import_paths_json,
                    extension_modules_json,
                    function_modules_json,
                    minimum_platform_version,
                    sync_status,
                    validation_error,
                    created_at
                FROM extension_registry_revisions
                WHERE extension_registry_revision_id = %s
                """,
                (extension_registry_revision_id,),
            ).fetchone()
        if row is None:
            raise KeyError(
                f"Unknown external registry revision: {extension_registry_revision_id}"
            )
        return _deserialize_extension_registry_revision_row(_coerce_row_mapping(row))

    def list_extension_registry_revisions(
        self,
        *,
        extension_registry_source_id: str | None = None,
    ) -> list[ExtensionRegistryRevisionRecord]:
        with self._connect(row_factory=dict_row) as connection:
            sql = """
                SELECT
                    extension_registry_revision_id,
                    extension_registry_source_id,
                    resolved_ref,
                    runtime_path,
                    manifest_path,
                    manifest_digest,
                    manifest_version,
                    content_fingerprint,
                    import_paths_json,
                    extension_modules_json,
                    function_modules_json,
                    minimum_platform_version,
                    sync_status,
                    validation_error,
                    created_at
                FROM extension_registry_revisions
            """
            params: tuple[object, ...] = ()
            if extension_registry_source_id is not None:
                sql += " WHERE extension_registry_source_id = %s"
                params = (extension_registry_source_id,)
            sql += " ORDER BY created_at, extension_registry_revision_id"
            rows = connection.execute(sql, params).fetchall()
        return [
            _deserialize_extension_registry_revision_row(_coerce_row_mapping(row))
            for row in rows
        ]

    def activate_extension_registry_revision(
        self,
        *,
        extension_registry_source_id: str,
        extension_registry_revision_id: str,
        activated_at: datetime | None = None,
    ) -> ExtensionRegistryActivationRecord:
        source = self.get_extension_registry_source(extension_registry_source_id)
        if source.archived:
            raise ValueError(
                f"Cannot activate archived external registry source: {extension_registry_source_id}"
            )
        if not source.enabled:
            raise ValueError(
                f"Cannot activate disabled external registry source: {extension_registry_source_id}"
            )
        revision = self.get_extension_registry_revision(extension_registry_revision_id)
        if revision.extension_registry_source_id != extension_registry_source_id:
            raise ValueError(
                "External registry revision does not belong to source: "
                f"{extension_registry_revision_id}"
            )
        if revision.sync_status != "validated":
            raise ValueError(
                "Cannot activate external registry revision with sync_status="
                f"{revision.sync_status!r}"
            )
        activation_time = activated_at or datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO extension_registry_activations (
                    extension_registry_source_id,
                    extension_registry_revision_id,
                    activated_at
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (extension_registry_source_id)
                DO UPDATE SET
                    extension_registry_revision_id = EXCLUDED.extension_registry_revision_id,
                    activated_at = EXCLUDED.activated_at
                """,
                (
                    extension_registry_source_id,
                    extension_registry_revision_id,
                    activation_time,
                ),
            )
        activation = self.get_extension_registry_activation(extension_registry_source_id)
        if activation is None:
            raise KeyError(
                f"Missing activation for external registry source: {extension_registry_source_id}"
            )
        return activation

    def get_extension_registry_activation(
        self,
        extension_registry_source_id: str,
    ) -> ExtensionRegistryActivationRecord | None:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT
                    extension_registry_source_id,
                    extension_registry_revision_id,
                    activated_at
                FROM extension_registry_activations
                WHERE extension_registry_source_id = %s
                """,
                (extension_registry_source_id,),
            ).fetchone()
        if row is None:
            return None
        return _deserialize_extension_registry_activation_row(_coerce_row_mapping(row))

    def list_extension_registry_activations(
        self,
    ) -> list[ExtensionRegistryActivationRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT
                    extension_registry_source_id,
                    extension_registry_revision_id,
                    activated_at
                FROM extension_registry_activations
                ORDER BY activated_at, extension_registry_source_id
                """
            ).fetchall()
        return [
            _deserialize_extension_registry_activation_row(_coerce_row_mapping(row))
            for row in rows
        ]
