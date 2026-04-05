from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from packages.storage.external_registry_catalog import (
    ExtensionRegistryActivationRecord,
    ExtensionRegistryRevisionCreate,
    ExtensionRegistryRevisionRecord,
    ExtensionRegistrySourceCreate,
    ExtensionRegistrySourceRecord,
    deserialize_string_tuple,
    serialize_string_tuple,
    validate_external_registry_source_kind,
    validate_external_registry_sync_status,
)


def _deserialize_extension_registry_source_row(
    row: sqlite3.Row,
) -> ExtensionRegistrySourceRecord:
    return ExtensionRegistrySourceRecord(
        extension_registry_source_id=row["extension_registry_source_id"],
        name=row["name"],
        source_kind=row["source_kind"],
        location=row["location"],
        desired_ref=row["desired_ref"],
        subdirectory=row["subdirectory"],
        auth_secret_name=row["auth_secret_name"],
        auth_secret_key=row["auth_secret_key"],
        enabled=bool(row["enabled"]),
        archived=bool(row["archived"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _deserialize_extension_registry_revision_row(
    row: sqlite3.Row,
) -> ExtensionRegistryRevisionRecord:
    return ExtensionRegistryRevisionRecord(
        extension_registry_revision_id=row["extension_registry_revision_id"],
        extension_registry_source_id=row["extension_registry_source_id"],
        resolved_ref=row["resolved_ref"],
        runtime_path=row["runtime_path"],
        manifest_path=row["manifest_path"],
        manifest_digest=row["manifest_digest"],
        manifest_version=row["manifest_version"],
        content_fingerprint=row["content_fingerprint"],
        import_paths=deserialize_string_tuple(row["import_paths_json"]),
        extension_modules=deserialize_string_tuple(row["extension_modules_json"]),
        function_modules=deserialize_string_tuple(row["function_modules_json"]),
        minimum_platform_version=row["minimum_platform_version"],
        sync_status=row["sync_status"],
        validation_error=row["validation_error"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _deserialize_extension_registry_activation_row(
    row: sqlite3.Row,
) -> ExtensionRegistryActivationRecord:
    return ExtensionRegistryActivationRecord(
        extension_registry_source_id=row["extension_registry_source_id"],
        extension_registry_revision_id=row["extension_registry_revision_id"],
        activated_at=datetime.fromisoformat(row["activated_at"]),
    )


class SQLiteExternalRegistryCatalogMixin:
    def _connect(self) -> sqlite3.Connection:
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int(source.enabled),
                    int(source.archived),
                    source.created_at.isoformat(),
                ),
            )
            connection.commit()
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
                SET name = ?,
                    source_kind = ?,
                    location = ?,
                    desired_ref = ?,
                    subdirectory = ?,
                    auth_secret_name = ?,
                    auth_secret_key = ?,
                    enabled = ?,
                    archived = ?
                WHERE extension_registry_source_id = ?
                """,
                (
                    source.name,
                    source.source_kind,
                    source.location,
                    source.desired_ref,
                    source.subdirectory,
                    source.auth_secret_name,
                    source.auth_secret_key,
                    int(source.enabled),
                    int(source.archived),
                    source.extension_registry_source_id,
                ),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(
                "Unknown external registry source: "
                f"{source.extension_registry_source_id}"
            )
        return self.get_extension_registry_source(source.extension_registry_source_id)

    def get_extension_registry_source(
        self,
        extension_registry_source_id: str,
    ) -> ExtensionRegistrySourceRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
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
                WHERE extension_registry_source_id = ?
                """,
                (extension_registry_source_id,),
            ).fetchone()
        if row is None:
            raise KeyError(
                f"Unknown external registry source: {extension_registry_source_id}"
            )
        return _deserialize_extension_registry_source_row(row)

    def list_extension_registry_sources(
        self,
        *,
        include_archived: bool = False,
    ) -> list[ExtensionRegistrySourceRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
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
            params: tuple[object, ...] = ()
            if not include_archived:
                sql += " WHERE archived = 0"
            sql += " ORDER BY created_at, extension_registry_source_id"
            rows = connection.execute(sql, params).fetchall()
        return [_deserialize_extension_registry_source_row(row) for row in rows]

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
                SET archived = ?
                WHERE extension_registry_source_id = ?
                """,
                (int(archived), extension_registry_source_id),
            )
            connection.commit()
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    serialize_string_tuple(revision.import_paths),
                    serialize_string_tuple(revision.extension_modules),
                    serialize_string_tuple(revision.function_modules),
                    revision.minimum_platform_version,
                    revision.sync_status,
                    revision.validation_error,
                    revision.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_extension_registry_revision(revision.extension_registry_revision_id)

    def get_extension_registry_revision(
        self,
        extension_registry_revision_id: str,
    ) -> ExtensionRegistryRevisionRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
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
                WHERE extension_registry_revision_id = ?
                """,
                (extension_registry_revision_id,),
            ).fetchone()
        if row is None:
            raise KeyError(
                f"Unknown external registry revision: {extension_registry_revision_id}"
            )
        return _deserialize_extension_registry_revision_row(row)

    def list_extension_registry_revisions(
        self,
        *,
        extension_registry_source_id: str | None = None,
    ) -> list[ExtensionRegistryRevisionRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
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
                sql += " WHERE extension_registry_source_id = ?"
                params = (extension_registry_source_id,)
            sql += " ORDER BY created_at, extension_registry_revision_id"
            rows = connection.execute(sql, params).fetchall()
        return [_deserialize_extension_registry_revision_row(row) for row in rows]

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
                VALUES (?, ?, ?)
                ON CONFLICT(extension_registry_source_id)
                DO UPDATE SET
                    extension_registry_revision_id = excluded.extension_registry_revision_id,
                    activated_at = excluded.activated_at
                """,
                (
                    extension_registry_source_id,
                    extension_registry_revision_id,
                    activation_time.isoformat(),
                ),
            )
            connection.commit()
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
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    extension_registry_source_id,
                    extension_registry_revision_id,
                    activated_at
                FROM extension_registry_activations
                WHERE extension_registry_source_id = ?
                """,
                (extension_registry_source_id,),
            ).fetchone()
        if row is None:
            return None
        return _deserialize_extension_registry_activation_row(row)

    def list_extension_registry_activations(
        self,
    ) -> list[ExtensionRegistryActivationRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
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
        return [_deserialize_extension_registry_activation_row(row) for row in rows]
