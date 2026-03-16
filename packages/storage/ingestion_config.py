from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from packages.storage.auth_store import (
    LocalUserCreate,
    LocalUserRecord,
    ServiceTokenCreate,
    ServiceTokenRecord,
    UserRole,
    normalize_service_token_name,
    normalize_service_token_scopes,
    normalize_username,
)
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    AuthAuditEventRecord,
    ControlPlaneSnapshot,
    ExecutionScheduleCreate,
    PublicationAuditCreate,
    PublicationAuditRecord,
    SourceLineageCreate,
    SourceLineageRecord,
)
from packages.storage.control_plane_support import (
    _deserialize_auth_audit_event_row,
    _deserialize_publication_audit_row,
    _deserialize_service_token_row,
    _deserialize_source_lineage_row,
)
from packages.storage.ingestion_catalog import (
    _BUILTIN_PUBLICATION_DEFINITIONS,
    _BUILTIN_TRANSFORMATION_PACKAGES,
    ColumnMappingCreate,
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    IngestionDefinitionRecord,
    PublicationDefinitionCreate,
    PublicationDefinitionRecord,
    RequestHeaderSecretRef,
    SourceAssetCreate,
    SourceAssetRecord,
    SourceSystemCreate,
    SourceSystemRecord,
    TransformationPackageCreate,
    TransformationPackageRecord,
    allowed_publication_keys,
    resolve_dataset_contract,
    validate_publication_key,
)
from packages.storage.sqlite_asset_definition_catalog import (
    SQLiteAssetDefinitionCatalogMixin,
)
from packages.storage.sqlite_execution_control_plane import (
    SQLiteExecutionControlPlaneMixin,
)
from packages.storage.sqlite_source_contract_catalog import (
    SQLiteSourceContractCatalogMixin,
)

__all__ = [
    "ColumnMappingCreate",
    "ColumnMappingRecord",
    "ColumnMappingRule",
    "DatasetColumnConfig",
    "DatasetContractConfigCreate",
    "DatasetContractConfigRecord",
    "IngestionConfigRepository",
    "IngestionDefinitionCreate",
    "IngestionDefinitionRecord",
    "PublicationDefinitionCreate",
    "PublicationDefinitionRecord",
    "RequestHeaderSecretRef",
    "SourceAssetCreate",
    "SourceAssetRecord",
    "SourceSystemCreate",
    "SourceSystemRecord",
    "TransformationPackageCreate",
    "TransformationPackageRecord",
    "allowed_publication_keys",
    "resolve_dataset_contract",
    "validate_publication_key",
    "_BUILTIN_PUBLICATION_DEFINITIONS",
    "_BUILTIN_TRANSFORMATION_PACKAGES",
]


class IngestionConfigRepository(
    SQLiteSourceContractCatalogMixin,
    SQLiteAssetDefinitionCatalogMixin,
    SQLiteExecutionControlPlaneMixin,
):
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def record_source_lineage(
        self,
        entries: tuple[SourceLineageCreate, ...],
    ) -> list[SourceLineageRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO source_lineage (
                    lineage_id,
                    input_run_id,
                    target_layer,
                    target_name,
                    target_kind,
                    row_count,
                    source_system,
                    source_run_id,
                    recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.lineage_id,
                        entry.input_run_id,
                        entry.target_layer,
                        entry.target_name,
                        entry.target_kind,
                        entry.row_count,
                        entry.source_system,
                        entry.source_run_id,
                        entry.recorded_at.isoformat(),
                    )
                    for entry in entries
                ],
            )
            connection.commit()
        return self.list_source_lineage()

    def list_source_lineage(
        self,
        *,
        input_run_id: str | None = None,
        target_layer: str | None = None,
    ) -> list[SourceLineageRecord]:
        clauses: list[str] = []
        params: list[str] = []
        if input_run_id is not None:
            clauses.append("input_run_id = ?")
            params.append(input_run_id)
        if target_layer is not None:
            clauses.append("target_layer = ?")
            params.append(target_layer)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    lineage_id,
                    input_run_id,
                    target_layer,
                    target_name,
                    target_kind,
                    row_count,
                    source_system,
                    source_run_id,
                    recorded_at
                FROM source_lineage
                {where_sql}
                ORDER BY recorded_at, lineage_id
                """,
                params,
            ).fetchall()
        return [_deserialize_source_lineage_row(row) for row in rows]

    def record_publication_audit(
        self,
        entries: tuple[PublicationAuditCreate, ...],
    ) -> list[PublicationAuditRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO publication_audit (
                    publication_audit_id,
                    run_id,
                    publication_key,
                    relation_name,
                    status,
                    published_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.publication_audit_id,
                        entry.run_id,
                        entry.publication_key,
                        entry.relation_name,
                        entry.status,
                        entry.published_at.isoformat(),
                    )
                    for entry in entries
                ],
            )
            connection.commit()
        return self.list_publication_audit()

    def list_publication_audit(
        self,
        *,
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> list[PublicationAuditRecord]:
        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if publication_key is not None:
            clauses.append("publication_key = ?")
            params.append(publication_key)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    publication_audit_id,
                    run_id,
                    publication_key,
                    relation_name,
                    status,
                    published_at
                FROM publication_audit
                {where_sql}
                ORDER BY published_at, publication_audit_id
                """,
                params,
            ).fetchall()
        return [_deserialize_publication_audit_row(row) for row in rows]

    def create_local_user(self, user: LocalUserCreate) -> LocalUserRecord:
        username = normalize_username(user.username)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO local_users (
                    user_id,
                    username,
                    password_hash,
                    role,
                    enabled,
                    created_at,
                    last_login_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    username,
                    user.password_hash,
                    user.role.value,
                    int(user.enabled),
                    user.created_at.isoformat(),
                    user.last_login_at.isoformat() if user.last_login_at else None,
                ),
            )
            connection.commit()
        return self.get_local_user(user.user_id)

    def get_local_user(self, user_id: str) -> LocalUserRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    user_id,
                    username,
                    password_hash,
                    role,
                    enabled,
                    created_at,
                    last_login_at
                FROM local_users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown local user: {user_id}")
        return _deserialize_local_user_row(row)

    def get_local_user_by_username(self, username: str) -> LocalUserRecord:
        normalized_username = normalize_username(username)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    user_id,
                    username,
                    password_hash,
                    role,
                    enabled,
                    created_at,
                    last_login_at
                FROM local_users
                WHERE username = ?
                """,
                (normalized_username,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown local user: {normalized_username}")
        return _deserialize_local_user_row(row)

    def list_local_users(self, *, enabled_only: bool = False) -> list[LocalUserRecord]:
        sql = """
            SELECT
                user_id,
                username,
                password_hash,
                role,
                enabled,
                created_at,
                last_login_at
            FROM local_users
        """
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at, username"
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(sql).fetchall()
        return [_deserialize_local_user_row(row) for row in rows]

    def update_local_user(
        self,
        user_id: str,
        *,
        role: UserRole | None = None,
        enabled: bool | None = None,
    ) -> LocalUserRecord:
        assignments: list[str] = []
        params: list[object] = []
        if role is not None:
            assignments.append("role = ?")
            params.append(role.value)
        if enabled is not None:
            assignments.append("enabled = ?")
            params.append(int(enabled))
        if not assignments:
            return self.get_local_user(user_id)
        params.append(user_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE local_users
                SET {", ".join(assignments)}
                WHERE user_id = ?
                """,
                tuple(params),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown local user: {user_id}")
        return self.get_local_user(user_id)

    def update_local_user_password(
        self,
        user_id: str,
        *,
        password_hash: str,
    ) -> LocalUserRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE local_users
                SET password_hash = ?
                WHERE user_id = ?
                """,
                (password_hash, user_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown local user: {user_id}")
        return self.get_local_user(user_id)

    def record_local_user_login(
        self,
        user_id: str,
        *,
        logged_in_at: datetime | None = None,
    ) -> LocalUserRecord:
        resolved_logged_in_at = logged_in_at or datetime.now(UTC)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE local_users
                SET last_login_at = ?
                WHERE user_id = ?
                """,
                (resolved_logged_in_at.isoformat(), user_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown local user: {user_id}")
        return self.get_local_user(user_id)

    def create_service_token(self, token: ServiceTokenCreate) -> ServiceTokenRecord:
        token_name = normalize_service_token_name(token.token_name)
        scopes = normalize_service_token_scopes(token.scopes)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO service_tokens (
                    token_id,
                    token_name,
                    token_secret_hash,
                    role,
                    scopes_json,
                    expires_at,
                    created_at,
                    last_used_at,
                    revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token.token_id,
                    token_name,
                    token.token_secret_hash,
                    token.role.value,
                    json.dumps(list(scopes)),
                    token.expires_at.isoformat() if token.expires_at else None,
                    token.created_at.isoformat(),
                    token.last_used_at.isoformat() if token.last_used_at else None,
                    token.revoked_at.isoformat() if token.revoked_at else None,
                ),
            )
            connection.commit()
        return self.get_service_token(token.token_id)

    def get_service_token(self, token_id: str) -> ServiceTokenRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    token_id,
                    token_name,
                    token_secret_hash,
                    role,
                    scopes_json,
                    expires_at,
                    created_at,
                    last_used_at,
                    revoked_at
                FROM service_tokens
                WHERE token_id = ?
                """,
                (token_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown service token: {token_id}")
        return _deserialize_service_token_row(row)

    def list_service_tokens(
        self,
        *,
        include_revoked: bool = False,
    ) -> list[ServiceTokenRecord]:
        sql = """
            SELECT
                token_id,
                token_name,
                token_secret_hash,
                role,
                scopes_json,
                expires_at,
                created_at,
                last_used_at,
                revoked_at
            FROM service_tokens
        """
        params: list[object] = []
        if not include_revoked:
            sql += " WHERE revoked_at IS NULL"
        sql += " ORDER BY created_at, token_name"
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(sql, params).fetchall()
        return [_deserialize_service_token_row(row) for row in rows]

    def revoke_service_token(
        self,
        token_id: str,
        *,
        revoked_at: datetime | None = None,
    ) -> ServiceTokenRecord:
        resolved_revoked_at = revoked_at or datetime.now(UTC)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE service_tokens
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE token_id = ?
                """,
                (resolved_revoked_at.isoformat(), token_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown service token: {token_id}")
        return self.get_service_token(token_id)

    def record_service_token_use(
        self,
        token_id: str,
        *,
        used_at: datetime | None = None,
    ) -> ServiceTokenRecord:
        resolved_used_at = used_at or datetime.now(UTC)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE service_tokens
                SET last_used_at = ?
                WHERE token_id = ?
                """,
                (resolved_used_at.isoformat(), token_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown service token: {token_id}")
        return self.get_service_token(token_id)

    def record_auth_audit_events(
        self,
        entries: tuple[AuthAuditEventCreate, ...],
    ) -> list[AuthAuditEventRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO auth_audit_events (
                    event_id,
                    event_type,
                    success,
                    actor_user_id,
                    actor_username,
                    subject_user_id,
                    subject_username,
                    remote_addr,
                    user_agent,
                    detail,
                    occurred_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.event_id,
                        entry.event_type,
                        int(entry.success),
                        entry.actor_user_id,
                        entry.actor_username,
                        entry.subject_user_id,
                        normalize_username(entry.subject_username)
                        if entry.subject_username
                        else None,
                        entry.remote_addr,
                        entry.user_agent,
                        entry.detail,
                        entry.occurred_at.isoformat(),
                    )
                    for entry in entries
                ],
            )
            connection.commit()
        recorded_ids = {entry.event_id for entry in entries}
        return [
            record
            for record in self.list_auth_audit_events(limit=len(entries))
            if record.event_id in recorded_ids
        ]

    def list_auth_audit_events(
        self,
        *,
        event_type: str | None = None,
        success: bool | None = None,
        actor_user_id: str | None = None,
        subject_user_id: str | None = None,
        subject_username: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[AuthAuditEventRecord]:
        sql = """
            SELECT
                event_id,
                event_type,
                success,
                actor_user_id,
                actor_username,
                subject_user_id,
                subject_username,
                remote_addr,
                user_agent,
                detail,
                occurred_at
            FROM auth_audit_events
        """
        clauses: list[str] = []
        params: list[object] = []
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if success is not None:
            clauses.append("success = ?")
            params.append(int(success))
        if actor_user_id is not None:
            clauses.append("actor_user_id = ?")
            params.append(actor_user_id)
        if subject_user_id is not None:
            clauses.append("subject_user_id = ?")
            params.append(subject_user_id)
        if subject_username is not None:
            clauses.append("subject_username = ?")
            params.append(normalize_username(subject_username))
        if since is not None:
            clauses.append("occurred_at >= ?")
            params.append(since.isoformat())
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY occurred_at DESC, event_id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(sql, params).fetchall()
        return [_deserialize_auth_audit_event_row(row) for row in rows]

    def export_snapshot(self) -> ControlPlaneSnapshot:
        return ControlPlaneSnapshot(
            source_systems=tuple(self.list_source_systems()),
            dataset_contracts=tuple(self.list_dataset_contracts(include_archived=True)),
            column_mappings=tuple(self.list_column_mappings(include_archived=True)),
            transformation_packages=tuple(self.list_transformation_packages()),
            publication_definitions=tuple(self.list_publication_definitions()),
            source_assets=tuple(self.list_source_assets(include_archived=True)),
            ingestion_definitions=tuple(
                self.list_ingestion_definitions(include_archived=True)
            ),
            execution_schedules=tuple(
                self.list_execution_schedules(include_archived=True)
            ),
            source_lineage=tuple(self.list_source_lineage()),
            publication_audit=tuple(self.list_publication_audit()),
            auth_audit_events=tuple(self.list_auth_audit_events()),
            local_users=tuple(self.list_local_users()),
            service_tokens=tuple(self.list_service_tokens(include_revoked=True)),
        )

    def import_snapshot(self, snapshot: ControlPlaneSnapshot) -> None:
        for source_system_record in snapshot.source_systems:
            try:
                self.create_source_system(
                    SourceSystemCreate(
                        source_system_id=source_system_record.source_system_id,
                        name=source_system_record.name,
                        source_type=source_system_record.source_type,
                        transport=source_system_record.transport,
                        schedule_mode=source_system_record.schedule_mode,
                        description=source_system_record.description,
                        enabled=source_system_record.enabled,
                        created_at=source_system_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for dataset_contract_record in snapshot.dataset_contracts:
            try:
                self.create_dataset_contract(
                    DatasetContractConfigCreate(
                        dataset_contract_id=dataset_contract_record.dataset_contract_id,
                        dataset_name=dataset_contract_record.dataset_name,
                        version=dataset_contract_record.version,
                        allow_extra_columns=dataset_contract_record.allow_extra_columns,
                        columns=dataset_contract_record.columns,
                        archived=False,
                        created_at=dataset_contract_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for column_mapping_record in snapshot.column_mappings:
            try:
                self.create_column_mapping(
                    ColumnMappingCreate(
                        column_mapping_id=column_mapping_record.column_mapping_id,
                        source_system_id=column_mapping_record.source_system_id,
                        dataset_contract_id=column_mapping_record.dataset_contract_id,
                        version=column_mapping_record.version,
                        rules=column_mapping_record.rules,
                        archived=False,
                        created_at=column_mapping_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for transformation_package_record in snapshot.transformation_packages:
            try:
                self.create_transformation_package(
                    TransformationPackageCreate(
                        transformation_package_id=transformation_package_record.transformation_package_id,
                        name=transformation_package_record.name,
                        handler_key=transformation_package_record.handler_key,
                        version=transformation_package_record.version,
                        description=transformation_package_record.description,
                        created_at=transformation_package_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for publication_definition_record in snapshot.publication_definitions:
            try:
                self.create_publication_definition(
                    PublicationDefinitionCreate(
                        publication_definition_id=publication_definition_record.publication_definition_id,
                        transformation_package_id=publication_definition_record.transformation_package_id,
                        publication_key=publication_definition_record.publication_key,
                        name=publication_definition_record.name,
                        description=publication_definition_record.description,
                        created_at=publication_definition_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for source_asset_record in snapshot.source_assets:
            try:
                self.create_source_asset(
                    SourceAssetCreate(
                        source_asset_id=source_asset_record.source_asset_id,
                        source_system_id=source_asset_record.source_system_id,
                        dataset_contract_id=source_asset_record.dataset_contract_id,
                        column_mapping_id=source_asset_record.column_mapping_id,
                        transformation_package_id=source_asset_record.transformation_package_id,
                        name=source_asset_record.name,
                        asset_type=source_asset_record.asset_type,
                        description=source_asset_record.description,
                        enabled=source_asset_record.enabled,
                        archived=False,
                        created_at=source_asset_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for ingestion_definition_record in snapshot.ingestion_definitions:
            try:
                self.create_ingestion_definition(
                    IngestionDefinitionCreate(
                        ingestion_definition_id=ingestion_definition_record.ingestion_definition_id,
                        source_asset_id=ingestion_definition_record.source_asset_id,
                        transport=ingestion_definition_record.transport,
                        schedule_mode=ingestion_definition_record.schedule_mode,
                        source_path=ingestion_definition_record.source_path,
                        file_pattern=ingestion_definition_record.file_pattern,
                        processed_path=ingestion_definition_record.processed_path,
                        failed_path=ingestion_definition_record.failed_path,
                        poll_interval_seconds=ingestion_definition_record.poll_interval_seconds,
                        request_url=ingestion_definition_record.request_url,
                        request_method=ingestion_definition_record.request_method,
                        request_headers=ingestion_definition_record.request_headers,
                        request_timeout_seconds=ingestion_definition_record.request_timeout_seconds,
                        response_format=ingestion_definition_record.response_format,
                        output_file_name=ingestion_definition_record.output_file_name,
                        enabled=ingestion_definition_record.enabled,
                        archived=False,
                        source_name=ingestion_definition_record.source_name,
                        created_at=ingestion_definition_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for execution_schedule_record in snapshot.execution_schedules:
            try:
                self.create_execution_schedule(
                    ExecutionScheduleCreate(
                        schedule_id=execution_schedule_record.schedule_id,
                        target_kind=execution_schedule_record.target_kind,
                        target_ref=execution_schedule_record.target_ref,
                        cron_expression=execution_schedule_record.cron_expression,
                        timezone=execution_schedule_record.timezone,
                        enabled=execution_schedule_record.enabled,
                        archived=False,
                        max_concurrency=execution_schedule_record.max_concurrency,
                        next_due_at=execution_schedule_record.next_due_at,
                        last_enqueued_at=execution_schedule_record.last_enqueued_at,
                        created_at=execution_schedule_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for source_asset_record in snapshot.source_assets:
            if source_asset_record.archived:
                self.set_source_asset_archived_state(
                    source_asset_record.source_asset_id,
                    archived=True,
                )
        for ingestion_definition_record in snapshot.ingestion_definitions:
            if ingestion_definition_record.archived:
                self.set_ingestion_definition_archived_state(
                    ingestion_definition_record.ingestion_definition_id,
                    archived=True,
                )
        for execution_schedule_record in snapshot.execution_schedules:
            if execution_schedule_record.archived:
                self.set_execution_schedule_archived_state(
                    execution_schedule_record.schedule_id,
                    archived=True,
                )
        for column_mapping_record in snapshot.column_mappings:
            if column_mapping_record.archived:
                self.set_column_mapping_archived_state(
                    column_mapping_record.column_mapping_id,
                    archived=True,
                )
        for dataset_contract_record in snapshot.dataset_contracts:
            if dataset_contract_record.archived:
                self.set_dataset_contract_archived_state(
                    dataset_contract_record.dataset_contract_id,
                    archived=True,
                )
        self.record_source_lineage(
            tuple(
                SourceLineageCreate(
                    lineage_id=record.lineage_id,
                    input_run_id=record.input_run_id,
                    target_layer=record.target_layer,
                    target_name=record.target_name,
                    target_kind=record.target_kind,
                    row_count=record.row_count,
                    source_system=record.source_system,
                    source_run_id=record.source_run_id,
                    recorded_at=record.recorded_at,
                )
                for record in snapshot.source_lineage
            )
        )
        self.record_publication_audit(
            tuple(
                PublicationAuditCreate(
                    publication_audit_id=record.publication_audit_id,
                    run_id=record.run_id,
                    publication_key=record.publication_key,
                    relation_name=record.relation_name,
                    status=record.status,
                    published_at=record.published_at,
                )
                for record in snapshot.publication_audit
            )
        )
        self.record_auth_audit_events(
            tuple(
                AuthAuditEventCreate(
                    event_id=record.event_id,
                    event_type=record.event_type,
                    success=record.success,
                    actor_user_id=record.actor_user_id,
                    actor_username=record.actor_username,
                    subject_user_id=record.subject_user_id,
                    subject_username=record.subject_username,
                    remote_addr=record.remote_addr,
                    user_agent=record.user_agent,
                    detail=record.detail,
                    occurred_at=record.occurred_at,
                )
                for record in snapshot.auth_audit_events
            )
        )
        for local_user_record in snapshot.local_users:
            try:
                self.create_local_user(
                    LocalUserCreate(
                        user_id=local_user_record.user_id,
                        username=local_user_record.username,
                        password_hash=local_user_record.password_hash,
                        role=local_user_record.role,
                        enabled=local_user_record.enabled,
                        created_at=local_user_record.created_at,
                        last_login_at=local_user_record.last_login_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for service_token_record in snapshot.service_tokens:
            try:
                self.create_service_token(
                    ServiceTokenCreate(
                        token_id=service_token_record.token_id,
                        token_name=service_token_record.token_name,
                        token_secret_hash=service_token_record.token_secret_hash,
                        role=service_token_record.role,
                        scopes=service_token_record.scopes,
                        expires_at=service_token_record.expires_at,
                        created_at=service_token_record.created_at,
                        last_used_at=service_token_record.last_used_at,
                        revoked_at=service_token_record.revoked_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_systems (
                    source_system_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    schedule_mode TEXT NOT NULL,
                    description TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dataset_contracts (
                    dataset_contract_id TEXT PRIMARY KEY,
                    dataset_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    allow_extra_columns INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    columns_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS column_mappings (
                    column_mapping_id TEXT PRIMARY KEY,
                    source_system_id TEXT NOT NULL,
                    dataset_contract_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    rules_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_system_id) REFERENCES source_systems (source_system_id),
                    FOREIGN KEY (dataset_contract_id) REFERENCES dataset_contracts (dataset_contract_id)
                );

                CREATE TABLE IF NOT EXISTS transformation_packages (
                    transformation_package_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    handler_key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS publication_definitions (
                    publication_definition_id TEXT PRIMARY KEY,
                    transformation_package_id TEXT NOT NULL,
                    publication_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (transformation_package_id) REFERENCES transformation_packages (transformation_package_id)
                );

                CREATE TABLE IF NOT EXISTS source_assets (
                    source_asset_id TEXT PRIMARY KEY,
                    source_system_id TEXT NOT NULL,
                    dataset_contract_id TEXT NOT NULL,
                    column_mapping_id TEXT NOT NULL,
                    transformation_package_id TEXT,
                    name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    description TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_system_id) REFERENCES source_systems (source_system_id),
                    FOREIGN KEY (dataset_contract_id) REFERENCES dataset_contracts (dataset_contract_id),
                    FOREIGN KEY (column_mapping_id) REFERENCES column_mappings (column_mapping_id),
                    FOREIGN KEY (transformation_package_id) REFERENCES transformation_packages (transformation_package_id)
                );

                CREATE TABLE IF NOT EXISTS ingestion_definitions (
                    ingestion_definition_id TEXT PRIMARY KEY,
                    source_asset_id TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    schedule_mode TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    file_pattern TEXT NOT NULL,
                    processed_path TEXT,
                    failed_path TEXT,
                    poll_interval_seconds INTEGER,
                    request_url TEXT,
                    request_method TEXT,
                    request_headers_json TEXT,
                    request_timeout_seconds INTEGER,
                    response_format TEXT,
                    output_file_name TEXT,
                    enabled INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    source_name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_asset_id) REFERENCES source_assets (source_asset_id)
                );

                CREATE TABLE IF NOT EXISTS execution_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    target_kind TEXT NOT NULL,
                    target_ref TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    max_concurrency INTEGER NOT NULL,
                    next_due_at TEXT,
                    last_enqueued_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS schedule_dispatches (
                    dispatch_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_ref TEXT NOT NULL,
                    enqueued_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    run_ids_json TEXT NOT NULL DEFAULT '[]',
                    failure_reason TEXT,
                    worker_detail TEXT,
                    claimed_by_worker_id TEXT,
                    claimed_at TEXT,
                    claim_expires_at TEXT,
                    FOREIGN KEY (schedule_id) REFERENCES execution_schedules (schedule_id)
                );

                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    worker_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    active_dispatch_id TEXT,
                    detail TEXT,
                    observed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_lineage (
                    lineage_id TEXT PRIMARY KEY,
                    input_run_id TEXT,
                    target_layer TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    row_count INTEGER,
                    source_system TEXT,
                    source_run_id TEXT,
                    recorded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS publication_audit (
                    publication_audit_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    publication_key TEXT NOT NULL,
                    relation_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    published_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS local_users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS auth_audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    actor_user_id TEXT,
                    actor_username TEXT,
                    subject_user_id TEXT,
                    subject_username TEXT,
                    remote_addr TEXT,
                    user_agent TEXT,
                    detail TEXT,
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS service_tokens (
                    token_id TEXT PRIMARY KEY,
                    token_name TEXT NOT NULL,
                    token_secret_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    revoked_at TEXT
                );
                """
            )
            self._ensure_dataset_contract_columns(connection)
            self._ensure_column_mapping_columns(connection)
            self._ensure_source_system_columns(connection)
            self._ensure_source_asset_columns(connection)
            self._ensure_ingestion_definition_columns(connection)
            self._ensure_execution_schedule_columns(connection)
            self._ensure_schedule_dispatch_columns(connection)
            self._ensure_worker_heartbeat_table(connection)
            self._seed_builtin_transformation_packages(connection)
            connection.commit()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)

    def _ensure_source_system_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(source_systems)").fetchall()
        }
        if "enabled" in columns:
            return
        connection.execute(
            "ALTER TABLE source_systems ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
        )

    def _ensure_dataset_contract_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(dataset_contracts)").fetchall()
        }
        if "archived" not in columns:
            connection.execute(
                "ALTER TABLE dataset_contracts ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )

    def _ensure_column_mapping_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(column_mappings)").fetchall()
        }
        if "archived" not in columns:
            connection.execute(
                "ALTER TABLE column_mappings ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )

    def _ensure_ingestion_definition_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(ingestion_definitions)"
            ).fetchall()
        }
        required_columns = {
            "request_url": "TEXT",
            "request_method": "TEXT",
            "request_headers_json": "TEXT",
            "request_timeout_seconds": "INTEGER",
            "response_format": "TEXT",
            "output_file_name": "TEXT",
        }
        for column_name, column_type in required_columns.items():
            if column_name in columns:
                continue
            connection.execute(
                f"ALTER TABLE ingestion_definitions ADD COLUMN {column_name} {column_type}"
            )
        if "archived" not in columns:
            connection.execute(
                "ALTER TABLE ingestion_definitions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )

    def _ensure_source_asset_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(source_assets)").fetchall()
        }
        if "transformation_package_id" not in columns:
            connection.execute(
                "ALTER TABLE source_assets ADD COLUMN transformation_package_id TEXT"
            )
        if "enabled" not in columns:
            connection.execute(
                "ALTER TABLE source_assets ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
            )
        if "archived" not in columns:
            connection.execute(
                "ALTER TABLE source_assets ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )

    def _ensure_execution_schedule_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(execution_schedules)"
            ).fetchall()
        }
        if "archived" not in columns:
            connection.execute(
                "ALTER TABLE execution_schedules ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )

    def _ensure_schedule_dispatch_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(schedule_dispatches)"
            ).fetchall()
        }
        if "started_at" not in columns:
            connection.execute(
                "ALTER TABLE schedule_dispatches ADD COLUMN started_at TEXT"
            )
        if "run_ids_json" not in columns:
            connection.execute(
                "ALTER TABLE schedule_dispatches ADD COLUMN run_ids_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "failure_reason" not in columns:
            connection.execute(
                "ALTER TABLE schedule_dispatches ADD COLUMN failure_reason TEXT"
            )
        if "worker_detail" not in columns:
            connection.execute(
                "ALTER TABLE schedule_dispatches ADD COLUMN worker_detail TEXT"
            )
        if "claimed_by_worker_id" not in columns:
            connection.execute(
                "ALTER TABLE schedule_dispatches ADD COLUMN claimed_by_worker_id TEXT"
            )
        if "claimed_at" not in columns:
            connection.execute(
                "ALTER TABLE schedule_dispatches ADD COLUMN claimed_at TEXT"
            )
        if "claim_expires_at" not in columns:
            connection.execute(
                "ALTER TABLE schedule_dispatches ADD COLUMN claim_expires_at TEXT"
            )

    def _ensure_worker_heartbeat_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_heartbeats (
                worker_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                active_dispatch_id TEXT,
                detail TEXT,
                observed_at TEXT NOT NULL
            )
            """
        )

    def _seed_builtin_transformation_packages(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        for package in _BUILTIN_TRANSFORMATION_PACKAGES:
            connection.execute(
                """
                INSERT OR IGNORE INTO transformation_packages (
                    transformation_package_id,
                    name,
                    handler_key,
                    version,
                    description,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    package.transformation_package_id,
                    package.name,
                    package.handler_key,
                    package.version,
                    package.description,
                    now,
                ),
            )
        for publication in _BUILTIN_PUBLICATION_DEFINITIONS:
            connection.execute(
                """
                INSERT OR IGNORE INTO publication_definitions (
                    publication_definition_id,
                    transformation_package_id,
                    publication_key,
                    name,
                    description,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    publication.publication_definition_id,
                    publication.transformation_package_id,
                    publication.publication_key,
                    publication.name,
                    publication.description,
                    now,
                ),
            )


def _deserialize_local_user_row(row: sqlite3.Row) -> LocalUserRecord:
    return LocalUserRecord(
        user_id=row["user_id"],
        username=row["username"],
        password_hash=row["password_hash"],
        role=UserRole(row["role"]),
        enabled=bool(row["enabled"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        last_login_at=(
            datetime.fromisoformat(row["last_login_at"])
            if row["last_login_at"]
            else None
        ),
    )
