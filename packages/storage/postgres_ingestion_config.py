from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg.rows import dict_row

from packages.shared.extensions import ExtensionRegistry
from packages.storage.auth_store import (
    LocalUserCreate,
    LocalUserRecord,
    UserRole,
    normalize_username,
)
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    AuthAuditEventRecord,
    ControlPlaneSnapshot,
    ExecutionScheduleCreate,
    ExecutionScheduleRecord,
    PublicationAuditCreate,
    PublicationAuditRecord,
    ScheduleDispatchRecord,
    ScheduleDispatchRecoveryRecord,
    SourceLineageCreate,
    SourceLineageRecord,
    WorkerHeartbeatCreate,
    WorkerHeartbeatRecord,
)
from packages.storage.ingestion_config import (
    _BUILTIN_PUBLICATION_DEFINITIONS,
    _BUILTIN_TRANSFORMATION_PACKAGES,
    ColumnMappingCreate,
    ColumnMappingRecord,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    IngestionDefinitionRecord,
    PublicationDefinitionCreate,
    PublicationDefinitionRecord,
    SourceAssetCreate,
    SourceAssetRecord,
    SourceSystemCreate,
    SourceSystemRecord,
    TransformationPackageCreate,
    TransformationPackageRecord,
    _build_requeued_dispatch_worker_detail,
    _build_stale_dispatch_failure_reason,
    _build_stale_dispatch_worker_detail,
    _deserialize_auth_audit_event_row,
    _deserialize_columns,
    _deserialize_publication_audit_row,
    _deserialize_request_headers,
    _deserialize_rules,
    _deserialize_schedule_dispatch_row,
    _deserialize_source_lineage_row,
    _deserialize_worker_heartbeat_row,
    _serialize_request_headers,
    _validate_mapping_rules,
    validate_publication_key,
)
from packages.storage.postgres_support import configure_search_path, initialize_schema
from packages.storage.scheduling import next_cron_occurrence


class PostgresIngestionConfigRepository:
    def __init__(self, dsn: str, *, schema: str = "public") -> None:
        self.dsn = dsn
        self.schema = schema
        initialize_schema(dsn, schema)
        self._initialize()

    def _connect(self, *, row_factory=None):
        connection = psycopg.connect(self.dsn, row_factory=row_factory)
        configure_search_path(connection, self.schema)
        return connection

    def create_source_system(self, source_system: SourceSystemCreate) -> SourceSystemRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_systems (
                    source_system_id, name, source_type, transport, schedule_mode, description, enabled, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_system.source_system_id,
                    source_system.name,
                    source_system.source_type,
                    source_system.transport,
                    source_system.schedule_mode,
                    source_system.description,
                    source_system.enabled,
                    source_system.created_at,
                ),
            )
        return self.get_source_system(source_system.source_system_id)

    def update_source_system(self, source_system: SourceSystemCreate) -> SourceSystemRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_systems
                SET name = %s,
                    source_type = %s,
                    transport = %s,
                    schedule_mode = %s,
                    description = %s,
                    enabled = %s
                WHERE source_system_id = %s
                """,
                (
                    source_system.name,
                    source_system.source_type,
                    source_system.transport,
                    source_system.schedule_mode,
                    source_system.description,
                    source_system.enabled,
                    source_system.source_system_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source system: {source_system.source_system_id}")
        return self.get_source_system(source_system.source_system_id)

    def get_source_system(self, source_system_id: str) -> SourceSystemRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT source_system_id, name, source_type, transport, schedule_mode, description, enabled, created_at
                FROM source_systems
                WHERE source_system_id = %s
                """,
                (source_system_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown source system: {source_system_id}")
        return SourceSystemRecord(
            source_system_id=row["source_system_id"],
            name=row["name"],
            source_type=row["source_type"],
            transport=row["transport"],
            schedule_mode=row["schedule_mode"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
        )

    def list_source_systems(self) -> list[SourceSystemRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT source_system_id, name, source_type, transport, schedule_mode, description, enabled, created_at
                FROM source_systems
                ORDER BY created_at, source_system_id
                """
            ).fetchall()
        return [
            SourceSystemRecord(
                source_system_id=row["source_system_id"],
                name=row["name"],
                source_type=row["source_type"],
                transport=row["transport"],
                schedule_mode=row["schedule_mode"],
                description=row["description"],
                enabled=bool(row["enabled"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def create_dataset_contract(
        self,
        dataset_contract: DatasetContractConfigCreate,
    ) -> DatasetContractConfigRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO dataset_contracts (
                    dataset_contract_id, dataset_name, version, allow_extra_columns, archived, columns_json, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    dataset_contract.dataset_contract_id,
                    dataset_contract.dataset_name,
                    dataset_contract.version,
                    dataset_contract.allow_extra_columns,
                    dataset_contract.archived,
                    json.dumps(
                        [
                            {
                                "name": column.name,
                                "type": column.type.value,
                                "required": column.required,
                            }
                            for column in dataset_contract.columns
                        ]
                    ),
                    dataset_contract.created_at,
                ),
            )
        return self.get_dataset_contract(dataset_contract.dataset_contract_id)

    def get_dataset_contract(self, dataset_contract_id: str) -> DatasetContractConfigRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT dataset_contract_id, dataset_name, version, allow_extra_columns, archived, columns_json, created_at
                FROM dataset_contracts
                WHERE dataset_contract_id = %s
                """,
                (dataset_contract_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown dataset contract: {dataset_contract_id}")
        return DatasetContractConfigRecord(
            dataset_contract_id=row["dataset_contract_id"],
            dataset_name=row["dataset_name"],
            version=row["version"],
            allow_extra_columns=bool(row["allow_extra_columns"]),
            columns=_deserialize_columns(row["columns_json"]),
            archived=bool(row["archived"]),
            created_at=row["created_at"],
        )

    def list_dataset_contracts(
        self,
        *,
        include_archived: bool = False,
    ) -> list[DatasetContractConfigRecord]:
        with self._connect(row_factory=dict_row) as connection:
            sql = """
                SELECT dataset_contract_id, dataset_name, version, allow_extra_columns, archived, columns_json, created_at
                FROM dataset_contracts
            """
            if not include_archived:
                sql += " WHERE archived = FALSE"
            sql += " ORDER BY created_at, dataset_contract_id"
            rows = connection.execute(sql).fetchall()
        return [
            DatasetContractConfigRecord(
                dataset_contract_id=row["dataset_contract_id"],
                dataset_name=row["dataset_name"],
                version=row["version"],
                allow_extra_columns=bool(row["allow_extra_columns"]),
                columns=_deserialize_columns(row["columns_json"]),
                archived=bool(row["archived"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def set_dataset_contract_archived_state(
        self,
        dataset_contract_id: str,
        *,
        archived: bool,
    ) -> DatasetContractConfigRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE dataset_contracts
                SET archived = %s
                WHERE dataset_contract_id = %s
                """,
                (archived, dataset_contract_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown dataset contract: {dataset_contract_id}")
        return self.get_dataset_contract(dataset_contract_id)

    def create_column_mapping(self, column_mapping: ColumnMappingCreate) -> ColumnMappingRecord:
        _validate_mapping_rules(column_mapping.rules)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO column_mappings (
                    column_mapping_id, source_system_id, dataset_contract_id, version, archived, rules_json, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    column_mapping.column_mapping_id,
                    column_mapping.source_system_id,
                    column_mapping.dataset_contract_id,
                    column_mapping.version,
                    column_mapping.archived,
                    json.dumps([asdict(rule) for rule in column_mapping.rules]),
                    column_mapping.created_at,
                ),
            )
        return self.get_column_mapping(column_mapping.column_mapping_id)

    def get_column_mapping(self, column_mapping_id: str) -> ColumnMappingRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT column_mapping_id, source_system_id, dataset_contract_id, version, archived, rules_json, created_at
                FROM column_mappings
                WHERE column_mapping_id = %s
                """,
                (column_mapping_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown column mapping: {column_mapping_id}")
        return ColumnMappingRecord(
            column_mapping_id=row["column_mapping_id"],
            source_system_id=row["source_system_id"],
            dataset_contract_id=row["dataset_contract_id"],
            version=row["version"],
            rules=_deserialize_rules(row["rules_json"]),
            archived=bool(row["archived"]),
            created_at=row["created_at"],
        )

    def list_column_mappings(
        self,
        *,
        include_archived: bool = False,
    ) -> list[ColumnMappingRecord]:
        with self._connect(row_factory=dict_row) as connection:
            sql = """
                SELECT column_mapping_id, source_system_id, dataset_contract_id, version, archived, rules_json, created_at
                FROM column_mappings
            """
            if not include_archived:
                sql += " WHERE archived = FALSE"
            sql += " ORDER BY created_at, column_mapping_id"
            rows = connection.execute(sql).fetchall()
        return [
            ColumnMappingRecord(
                column_mapping_id=row["column_mapping_id"],
                source_system_id=row["source_system_id"],
                dataset_contract_id=row["dataset_contract_id"],
                version=row["version"],
                rules=_deserialize_rules(row["rules_json"]),
                archived=bool(row["archived"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def set_column_mapping_archived_state(
        self,
        column_mapping_id: str,
        *,
        archived: bool,
    ) -> ColumnMappingRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE column_mappings
                SET archived = %s
                WHERE column_mapping_id = %s
                """,
                (archived, column_mapping_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown column mapping: {column_mapping_id}")
        return self.get_column_mapping(column_mapping_id)

    def create_transformation_package(
        self,
        transformation_package: TransformationPackageCreate,
    ) -> TransformationPackageRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO transformation_packages (
                    transformation_package_id, name, handler_key, version, description, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    transformation_package.transformation_package_id,
                    transformation_package.name,
                    transformation_package.handler_key,
                    transformation_package.version,
                    transformation_package.description,
                    transformation_package.created_at,
                ),
            )
        return self.get_transformation_package(transformation_package.transformation_package_id)

    def get_transformation_package(self, transformation_package_id: str) -> TransformationPackageRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT transformation_package_id, name, handler_key, version, description, created_at
                FROM transformation_packages
                WHERE transformation_package_id = %s
                """,
                (transformation_package_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown transformation package: {transformation_package_id}")
        return TransformationPackageRecord(
            transformation_package_id=row["transformation_package_id"],
            name=row["name"],
            handler_key=row["handler_key"],
            version=row["version"],
            description=row["description"],
            created_at=row["created_at"],
        )

    def list_transformation_packages(self) -> list[TransformationPackageRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT transformation_package_id, name, handler_key, version, description, created_at
                FROM transformation_packages
                ORDER BY created_at, transformation_package_id
                """
            ).fetchall()
        return [
            TransformationPackageRecord(
                transformation_package_id=row["transformation_package_id"],
                name=row["name"],
                handler_key=row["handler_key"],
                version=row["version"],
                description=row["description"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def create_publication_definition(
        self,
        publication_definition: PublicationDefinitionCreate,
        *,
        extension_registry: ExtensionRegistry | None = None,
    ) -> PublicationDefinitionRecord:
        validate_publication_key(
            publication_definition.publication_key,
            extension_registry=extension_registry,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO publication_definitions (
                    publication_definition_id, transformation_package_id, publication_key, name, description, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    publication_definition.publication_definition_id,
                    publication_definition.transformation_package_id,
                    publication_definition.publication_key,
                    publication_definition.name,
                    publication_definition.description,
                    publication_definition.created_at,
                ),
            )
        return self.get_publication_definition(publication_definition.publication_definition_id)

    def get_publication_definition(self, publication_definition_id: str) -> PublicationDefinitionRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT publication_definition_id, transformation_package_id, publication_key, name, description, created_at
                FROM publication_definitions
                WHERE publication_definition_id = %s
                """,
                (publication_definition_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown publication definition: {publication_definition_id}")
        return PublicationDefinitionRecord(
            publication_definition_id=row["publication_definition_id"],
            transformation_package_id=row["transformation_package_id"],
            publication_key=row["publication_key"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
        )

    def list_publication_definitions(
        self,
        *,
        transformation_package_id: str | None = None,
    ) -> list[PublicationDefinitionRecord]:
        sql = """
            SELECT publication_definition_id, transformation_package_id, publication_key, name, description, created_at
            FROM publication_definitions
        """
        params: tuple[object, ...] = ()
        if transformation_package_id is not None:
            sql += " WHERE transformation_package_id = %s"
            params = (transformation_package_id,)
        sql += " ORDER BY created_at, publication_definition_id"
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [
            PublicationDefinitionRecord(
                publication_definition_id=row["publication_definition_id"],
                transformation_package_id=row["transformation_package_id"],
                publication_key=row["publication_key"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def create_source_asset(self, source_asset: SourceAssetCreate) -> SourceAssetRecord:
        dataset_contract = self.get_dataset_contract(source_asset.dataset_contract_id)
        if dataset_contract.archived:
            raise ValueError(
                f"Dataset contract is archived: {source_asset.dataset_contract_id}"
            )
        column_mapping = self.get_column_mapping(source_asset.column_mapping_id)
        if column_mapping.archived:
            raise ValueError(f"Column mapping is archived: {source_asset.column_mapping_id}")
        if source_asset.transformation_package_id is not None:
            self.get_transformation_package(source_asset.transformation_package_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_assets (
                    source_asset_id, source_system_id, dataset_contract_id, column_mapping_id,
                    transformation_package_id, name, asset_type, description, enabled, archived, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_asset.source_asset_id,
                    source_asset.source_system_id,
                    source_asset.dataset_contract_id,
                    source_asset.column_mapping_id,
                    source_asset.transformation_package_id,
                    source_asset.name,
                    source_asset.asset_type,
                    source_asset.description,
                    source_asset.enabled,
                    source_asset.archived,
                    source_asset.created_at,
                ),
            )
        return self.get_source_asset(source_asset.source_asset_id)

    def update_source_asset(self, source_asset: SourceAssetCreate) -> SourceAssetRecord:
        dataset_contract = self.get_dataset_contract(source_asset.dataset_contract_id)
        if dataset_contract.archived:
            raise ValueError(
                f"Dataset contract is archived: {source_asset.dataset_contract_id}"
            )
        column_mapping = self.get_column_mapping(source_asset.column_mapping_id)
        if column_mapping.archived:
            raise ValueError(f"Column mapping is archived: {source_asset.column_mapping_id}")
        if source_asset.transformation_package_id is not None:
            self.get_transformation_package(source_asset.transformation_package_id)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_assets
                SET source_system_id = %s,
                    dataset_contract_id = %s,
                    column_mapping_id = %s,
                    transformation_package_id = %s,
                    name = %s,
                    asset_type = %s,
                    description = %s,
                    enabled = %s,
                    archived = %s
                WHERE source_asset_id = %s
                """,
                (
                    source_asset.source_system_id,
                    source_asset.dataset_contract_id,
                    source_asset.column_mapping_id,
                    source_asset.transformation_package_id,
                    source_asset.name,
                    source_asset.asset_type,
                    source_asset.description,
                    source_asset.enabled,
                    source_asset.archived,
                    source_asset.source_asset_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source asset: {source_asset.source_asset_id}")
        return self.get_source_asset(source_asset.source_asset_id)

    def get_source_asset(self, source_asset_id: str) -> SourceAssetRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT source_asset_id, source_system_id, dataset_contract_id, column_mapping_id,
                       transformation_package_id, name, asset_type, description, enabled, archived, created_at
                FROM source_assets
                WHERE source_asset_id = %s
                """,
                (source_asset_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown source asset: {source_asset_id}")
        return SourceAssetRecord(
            source_asset_id=row["source_asset_id"],
            source_system_id=row["source_system_id"],
            dataset_contract_id=row["dataset_contract_id"],
            column_mapping_id=row["column_mapping_id"],
            transformation_package_id=row["transformation_package_id"],
            name=row["name"],
            asset_type=row["asset_type"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            archived=bool(row["archived"]),
            created_at=row["created_at"],
        )

    def list_source_assets(
        self,
        *,
        include_archived: bool = False,
    ) -> list[SourceAssetRecord]:
        with self._connect(row_factory=dict_row) as connection:
            sql = """
                SELECT source_asset_id, source_system_id, dataset_contract_id, column_mapping_id,
                       transformation_package_id, name, asset_type, description, enabled, archived, created_at
                FROM source_assets
            """
            if not include_archived:
                sql += " WHERE archived = FALSE"
            sql += " ORDER BY created_at, source_asset_id"
            rows = connection.execute(sql).fetchall()
        return [
            SourceAssetRecord(
                source_asset_id=row["source_asset_id"],
                source_system_id=row["source_system_id"],
                dataset_contract_id=row["dataset_contract_id"],
                column_mapping_id=row["column_mapping_id"],
                transformation_package_id=row["transformation_package_id"],
                name=row["name"],
                asset_type=row["asset_type"],
                description=row["description"],
                enabled=bool(row["enabled"]),
                archived=bool(row["archived"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def set_source_asset_archived_state(
        self,
        source_asset_id: str,
        *,
        archived: bool,
    ) -> SourceAssetRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_assets
                SET archived = %s,
                    enabled = CASE WHEN %s THEN FALSE ELSE enabled END
                WHERE source_asset_id = %s
                """,
                (archived, archived, source_asset_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source asset: {source_asset_id}")
        return self.get_source_asset(source_asset_id)

    def delete_source_asset(self, source_asset_id: str) -> None:
        source_asset = self.get_source_asset(source_asset_id)
        if not source_asset.archived:
            raise ValueError("Archive source asset before deleting it.")
        dependencies = [
            record.ingestion_definition_id
            for record in self.list_ingestion_definitions(include_archived=True)
            if record.source_asset_id == source_asset_id
        ]
        if dependencies:
            raise ValueError(
                "Cannot delete source asset while ingestion definitions still reference it: "
                + ", ".join(sorted(dependencies))
            )
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM source_assets WHERE source_asset_id = %s",
                (source_asset_id,),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source asset: {source_asset_id}")

    def find_source_asset_by_binding(
        self,
        *,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
    ) -> SourceAssetRecord | None:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT source_asset_id, source_system_id, dataset_contract_id, column_mapping_id,
                       transformation_package_id, name, asset_type, description, enabled, archived, created_at
                FROM source_assets
                WHERE source_system_id = %s
                  AND dataset_contract_id = %s
                  AND column_mapping_id = %s
                  AND enabled = TRUE
                  AND archived = FALSE
                ORDER BY created_at, source_asset_id
                """,
                (source_system_id, dataset_contract_id, column_mapping_id),
            ).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise ValueError(
                "Multiple source assets match the configured CSV binding; use source_asset_id-bound ingestion instead."
            )
        row = rows[0]
        return SourceAssetRecord(
            source_asset_id=row["source_asset_id"],
            source_system_id=row["source_system_id"],
            dataset_contract_id=row["dataset_contract_id"],
            column_mapping_id=row["column_mapping_id"],
            transformation_package_id=row["transformation_package_id"],
            name=row["name"],
            asset_type=row["asset_type"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            archived=bool(row["archived"]),
            created_at=row["created_at"],
        )

    def create_ingestion_definition(
        self,
        ingestion_definition: IngestionDefinitionCreate,
    ) -> IngestionDefinitionRecord:
        source_asset = self.get_source_asset(ingestion_definition.source_asset_id)
        if source_asset.archived:
            raise ValueError(
                f"Source asset is archived: {ingestion_definition.source_asset_id}"
            )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_definitions (
                    ingestion_definition_id, source_asset_id, transport, schedule_mode, source_path, file_pattern,
                    processed_path, failed_path, poll_interval_seconds, request_url, request_method,
                    request_headers_json, request_timeout_seconds, response_format, output_file_name,
                    enabled, archived, source_name, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ingestion_definition.ingestion_definition_id,
                    ingestion_definition.source_asset_id,
                    ingestion_definition.transport,
                    ingestion_definition.schedule_mode,
                    ingestion_definition.source_path,
                    ingestion_definition.file_pattern,
                    ingestion_definition.processed_path,
                    ingestion_definition.failed_path,
                    ingestion_definition.poll_interval_seconds,
                    ingestion_definition.request_url,
                    ingestion_definition.request_method,
                    _serialize_request_headers(ingestion_definition.request_headers),
                    ingestion_definition.request_timeout_seconds,
                    ingestion_definition.response_format,
                    ingestion_definition.output_file_name,
                    ingestion_definition.enabled,
                    ingestion_definition.archived,
                    ingestion_definition.source_name,
                    ingestion_definition.created_at,
                ),
            )
        return self.get_ingestion_definition(ingestion_definition.ingestion_definition_id)

    def update_ingestion_definition(
        self,
        ingestion_definition: IngestionDefinitionCreate,
    ) -> IngestionDefinitionRecord:
        source_asset = self.get_source_asset(ingestion_definition.source_asset_id)
        if source_asset.archived:
            raise ValueError(
                f"Source asset is archived: {ingestion_definition.source_asset_id}"
            )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ingestion_definitions
                SET source_asset_id = %s,
                    transport = %s,
                    schedule_mode = %s,
                    source_path = %s,
                    file_pattern = %s,
                    processed_path = %s,
                    failed_path = %s,
                    poll_interval_seconds = %s,
                    request_url = %s,
                    request_method = %s,
                    request_headers_json = %s,
                    request_timeout_seconds = %s,
                    response_format = %s,
                    output_file_name = %s,
                    enabled = %s,
                    archived = %s,
                    source_name = %s
                WHERE ingestion_definition_id = %s
                """,
                (
                    ingestion_definition.source_asset_id,
                    ingestion_definition.transport,
                    ingestion_definition.schedule_mode,
                    ingestion_definition.source_path,
                    ingestion_definition.file_pattern,
                    ingestion_definition.processed_path,
                    ingestion_definition.failed_path,
                    ingestion_definition.poll_interval_seconds,
                    ingestion_definition.request_url,
                    ingestion_definition.request_method,
                    _serialize_request_headers(ingestion_definition.request_headers),
                    ingestion_definition.request_timeout_seconds,
                    ingestion_definition.response_format,
                    ingestion_definition.output_file_name,
                    ingestion_definition.enabled,
                    ingestion_definition.archived,
                    ingestion_definition.source_name,
                    ingestion_definition.ingestion_definition_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(
                f"Unknown ingestion definition: {ingestion_definition.ingestion_definition_id}"
            )
        return self.get_ingestion_definition(ingestion_definition.ingestion_definition_id)

    def get_ingestion_definition(self, ingestion_definition_id: str) -> IngestionDefinitionRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT ingestion_definition_id, source_asset_id, transport, schedule_mode, source_path, file_pattern,
                       processed_path, failed_path, poll_interval_seconds, request_url, request_method,
                       request_headers_json, request_timeout_seconds, response_format, output_file_name,
                       enabled, archived, source_name, created_at
                FROM ingestion_definitions
                WHERE ingestion_definition_id = %s
                """,
                (ingestion_definition_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown ingestion definition: {ingestion_definition_id}")
        return IngestionDefinitionRecord(
            ingestion_definition_id=row["ingestion_definition_id"],
            source_asset_id=row["source_asset_id"],
            transport=row["transport"],
            schedule_mode=row["schedule_mode"],
            source_path=row["source_path"],
            file_pattern=row["file_pattern"],
            processed_path=row["processed_path"],
            failed_path=row["failed_path"],
            poll_interval_seconds=row["poll_interval_seconds"],
            request_url=row["request_url"],
            request_method=row["request_method"],
            request_headers=_deserialize_request_headers(row["request_headers_json"]),
            request_timeout_seconds=row["request_timeout_seconds"],
            response_format=row["response_format"],
            output_file_name=row["output_file_name"],
            enabled=bool(row["enabled"]),
            archived=bool(row["archived"]),
            source_name=row["source_name"],
            created_at=row["created_at"],
        )

    def list_ingestion_definitions(
        self,
        *,
        enabled_only: bool = False,
        include_archived: bool = False,
    ) -> list[IngestionDefinitionRecord]:
        sql = """
            SELECT ingestion_definition_id, source_asset_id, transport, schedule_mode, source_path, file_pattern,
                   processed_path, failed_path, poll_interval_seconds, request_url, request_method,
                   request_headers_json, request_timeout_seconds, response_format, output_file_name,
                   enabled, archived, source_name, created_at
            FROM ingestion_definitions
        """
        clauses: list[str] = []
        if enabled_only:
            clauses.append("enabled = TRUE")
        if not include_archived:
            clauses.append("archived = FALSE")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at, ingestion_definition_id"
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql).fetchall()
        return [
            IngestionDefinitionRecord(
                ingestion_definition_id=row["ingestion_definition_id"],
                source_asset_id=row["source_asset_id"],
                transport=row["transport"],
                schedule_mode=row["schedule_mode"],
                source_path=row["source_path"],
                file_pattern=row["file_pattern"],
                processed_path=row["processed_path"],
                failed_path=row["failed_path"],
                poll_interval_seconds=row["poll_interval_seconds"],
                request_url=row["request_url"],
                request_method=row["request_method"],
                request_headers=_deserialize_request_headers(row["request_headers_json"]),
                request_timeout_seconds=row["request_timeout_seconds"],
                response_format=row["response_format"],
                output_file_name=row["output_file_name"],
                enabled=bool(row["enabled"]),
                archived=bool(row["archived"]),
                source_name=row["source_name"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def set_ingestion_definition_archived_state(
        self,
        ingestion_definition_id: str,
        *,
        archived: bool,
    ) -> IngestionDefinitionRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ingestion_definitions
                SET archived = %s,
                    enabled = CASE WHEN %s THEN FALSE ELSE enabled END
                WHERE ingestion_definition_id = %s
                """,
                (archived, archived, ingestion_definition_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown ingestion definition: {ingestion_definition_id}")
        return self.get_ingestion_definition(ingestion_definition_id)

    def delete_ingestion_definition(self, ingestion_definition_id: str) -> None:
        definition = self.get_ingestion_definition(ingestion_definition_id)
        if not definition.archived:
            raise ValueError("Archive ingestion definition before deleting it.")
        dependent_schedules = [
            record.schedule_id
            for record in self.list_execution_schedules(include_archived=True)
            if record.target_kind == "ingestion_definition"
            and record.target_ref == ingestion_definition_id
        ]
        if dependent_schedules:
            raise ValueError(
                "Cannot delete ingestion definition while schedules still reference it: "
                + ", ".join(sorted(dependent_schedules))
            )
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM ingestion_definitions WHERE ingestion_definition_id = %s",
                (ingestion_definition_id,),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown ingestion definition: {ingestion_definition_id}")

    def create_execution_schedule(self, schedule: ExecutionScheduleCreate) -> ExecutionScheduleRecord:
        _validate_execution_schedule_target_postgres(
            self,
            schedule.target_kind,
            schedule.target_ref,
        )
        next_due_at = schedule.next_due_at or next_cron_occurrence(
            schedule.cron_expression,
            timezone=schedule.timezone,
            after=schedule.created_at,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO execution_schedules (
                    schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,
                    max_concurrency, next_due_at, last_enqueued_at, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    schedule.schedule_id,
                    schedule.target_kind,
                    schedule.target_ref,
                    schedule.cron_expression,
                    schedule.timezone,
                    schedule.enabled,
                    schedule.archived,
                    schedule.max_concurrency,
                    next_due_at,
                    schedule.last_enqueued_at,
                    schedule.created_at,
                ),
            )
        return self.get_execution_schedule(schedule.schedule_id)

    def update_execution_schedule(self, schedule: ExecutionScheduleCreate) -> ExecutionScheduleRecord:
        _validate_execution_schedule_target_postgres(
            self,
            schedule.target_kind,
            schedule.target_ref,
        )
        next_due_at = schedule.next_due_at or next_cron_occurrence(
            schedule.cron_expression,
            timezone=schedule.timezone,
            after=schedule.last_enqueued_at or schedule.created_at,
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE execution_schedules
                SET target_kind = %s,
                    target_ref = %s,
                    cron_expression = %s,
                    timezone = %s,
                    enabled = %s,
                    archived = %s,
                    max_concurrency = %s,
                    next_due_at = %s,
                    last_enqueued_at = %s
                WHERE schedule_id = %s
                """,
                (
                    schedule.target_kind,
                    schedule.target_ref,
                    schedule.cron_expression,
                    schedule.timezone,
                    schedule.enabled,
                    schedule.archived,
                    schedule.max_concurrency,
                    next_due_at,
                    schedule.last_enqueued_at,
                    schedule.schedule_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown execution schedule: {schedule.schedule_id}")
        return self.get_execution_schedule(schedule.schedule_id)

    def get_execution_schedule(self, schedule_id: str) -> ExecutionScheduleRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,
                       max_concurrency, next_due_at, last_enqueued_at, created_at
                FROM execution_schedules
                WHERE schedule_id = %s
                """,
                (schedule_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown execution schedule: {schedule_id}")
        return ExecutionScheduleRecord(
            schedule_id=row["schedule_id"],
            target_kind=row["target_kind"],
            target_ref=row["target_ref"],
            cron_expression=row["cron_expression"],
            timezone=row["timezone"],
            enabled=bool(row["enabled"]),
            archived=bool(row["archived"]),
            max_concurrency=row["max_concurrency"],
            next_due_at=row["next_due_at"],
            last_enqueued_at=row["last_enqueued_at"],
            created_at=row["created_at"],
        )

    def list_execution_schedules(
        self,
        *,
        enabled_only: bool = False,
        include_archived: bool = False,
    ) -> list[ExecutionScheduleRecord]:
        sql = """
            SELECT schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,
                   max_concurrency, next_due_at, last_enqueued_at, created_at
            FROM execution_schedules
        """
        clauses: list[str] = []
        if enabled_only:
            clauses.append("enabled = TRUE")
        if not include_archived:
            clauses.append("archived = FALSE")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at, schedule_id"
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql).fetchall()
        return [
            ExecutionScheduleRecord(
                schedule_id=row["schedule_id"],
                target_kind=row["target_kind"],
                target_ref=row["target_ref"],
                cron_expression=row["cron_expression"],
                timezone=row["timezone"],
                enabled=bool(row["enabled"]),
                archived=bool(row["archived"]),
                max_concurrency=row["max_concurrency"],
                next_due_at=row["next_due_at"],
                last_enqueued_at=row["last_enqueued_at"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def set_execution_schedule_archived_state(
        self,
        schedule_id: str,
        *,
        archived: bool,
    ) -> ExecutionScheduleRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE execution_schedules
                SET archived = %s,
                    enabled = CASE WHEN %s THEN FALSE ELSE enabled END
                WHERE schedule_id = %s
                """,
                (archived, archived, schedule_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown execution schedule: {schedule_id}")
        return self.get_execution_schedule(schedule_id)

    def delete_execution_schedule(self, schedule_id: str) -> None:
        schedule = self.get_execution_schedule(schedule_id)
        if not schedule.archived:
            raise ValueError("Archive execution schedule before deleting it.")
        dispatches = self.list_schedule_dispatches(schedule_id=schedule_id)
        if dispatches:
            raise ValueError(
                "Cannot delete execution schedule while dispatch history exists: "
                + ", ".join(dispatch.dispatch_id for dispatch in dispatches)
            )
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM execution_schedules WHERE schedule_id = %s",
                (schedule_id,),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown execution schedule: {schedule_id}")

    def enqueue_due_execution_schedules(
        self,
        *,
        as_of: datetime | None = None,
        limit: int | None = None,
    ) -> list[ScheduleDispatchRecord]:
        dispatches: list[ScheduleDispatchRecord] = []
        resolved_as_of = as_of or datetime.now(UTC)
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,
                       max_concurrency, next_due_at, last_enqueued_at, created_at
                FROM execution_schedules
                WHERE enabled = TRUE
                  AND archived = FALSE
                  AND next_due_at IS NOT NULL
                  AND next_due_at <= %s
                ORDER BY next_due_at, schedule_id
                """,
                (resolved_as_of,),
            ).fetchall()
            for row in rows:
                if limit is not None and len(dispatches) >= limit:
                    break
                active_count = connection.execute(
                    """
                    SELECT COUNT(*) AS active_count
                    FROM schedule_dispatches
                    WHERE schedule_id = %s
                      AND status IN ('enqueued', 'running')
                    """,
                    (row["schedule_id"],),
                ).fetchone()["active_count"]
                if active_count >= row["max_concurrency"]:
                    continue
                dispatch_id = uuid.uuid4().hex[:16]
                connection.execute(
                    """
                    INSERT INTO schedule_dispatches (
                        dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                        started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                        claimed_by_worker_id, claimed_at, claim_expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        dispatch_id,
                        row["schedule_id"],
                        row["target_kind"],
                        row["target_ref"],
                        resolved_as_of,
                        "enqueued",
                        None,
                        None,
                        "[]",
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                )
                next_due_at = next_cron_occurrence(
                    row["cron_expression"],
                    timezone=row["timezone"],
                    after=resolved_as_of,
                )
                connection.execute(
                    """
                    UPDATE execution_schedules
                    SET last_enqueued_at = %s, next_due_at = %s
                    WHERE schedule_id = %s
                    """,
                    (resolved_as_of, next_due_at, row["schedule_id"]),
                )
                dispatches.append(
                    ScheduleDispatchRecord(
                        dispatch_id=dispatch_id,
                        schedule_id=row["schedule_id"],
                        target_kind=row["target_kind"],
                        target_ref=row["target_ref"],
                        enqueued_at=resolved_as_of,
                        status="enqueued",
                        started_at=None,
                        completed_at=None,
                        run_ids=(),
                        failure_reason=None,
                        worker_detail=None,
                        claimed_by_worker_id=None,
                        claimed_at=None,
                        claim_expires_at=None,
                    )
                )
        return dispatches

    def list_schedule_dispatches(
        self,
        *,
        schedule_id: str | None = None,
        status: str | None = None,
    ) -> list[ScheduleDispatchRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if schedule_id is not None:
            clauses.append("schedule_id = %s")
            params.append(schedule_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"""
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                {where_sql}
                ORDER BY enqueued_at DESC, dispatch_id DESC
                """,
                params,
            ).fetchall()
        normalized = [
            {
                "dispatch_id": row["dispatch_id"],
                "schedule_id": row["schedule_id"],
                "target_kind": row["target_kind"],
                "target_ref": row["target_ref"],
                "enqueued_at": row["enqueued_at"].isoformat(),
                "status": row["status"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                "run_ids_json": row["run_ids_json"] or "[]",
                "failure_reason": row["failure_reason"],
                "worker_detail": row["worker_detail"],
                "claimed_by_worker_id": row["claimed_by_worker_id"],
                "claimed_at": row["claimed_at"].isoformat() if row["claimed_at"] else None,
                "claim_expires_at": (
                    row["claim_expires_at"].isoformat() if row["claim_expires_at"] else None
                ),
            }
            for row in rows
        ]
        return [_deserialize_schedule_dispatch_row(row) for row in normalized]  # type: ignore[arg-type]

    def get_schedule_dispatch(self, dispatch_id: str) -> ScheduleDispatchRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                WHERE dispatch_id = %s
                """,
                (dispatch_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
        normalized = {
            "dispatch_id": row["dispatch_id"],
            "schedule_id": row["schedule_id"],
            "target_kind": row["target_kind"],
            "target_ref": row["target_ref"],
            "enqueued_at": row["enqueued_at"].isoformat(),
            "status": row["status"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "run_ids_json": row["run_ids_json"] or "[]",
            "failure_reason": row["failure_reason"],
            "worker_detail": row["worker_detail"],
            "claimed_by_worker_id": row["claimed_by_worker_id"],
            "claimed_at": row["claimed_at"].isoformat() if row["claimed_at"] else None,
            "claim_expires_at": (
                row["claim_expires_at"].isoformat() if row["claim_expires_at"] else None
            ),
        }
        return _deserialize_schedule_dispatch_row(normalized)  # type: ignore[arg-type]

    def create_schedule_dispatch(
        self,
        schedule_id: str,
        *,
        enqueued_at: datetime | None = None,
    ) -> ScheduleDispatchRecord:
        resolved_enqueued_at = enqueued_at or datetime.now(UTC)
        with self._connect(row_factory=dict_row) as connection:
            schedule_row = connection.execute(
                """
                SELECT schedule_id, target_kind, target_ref, enabled, archived, max_concurrency
                FROM execution_schedules
                WHERE schedule_id = %s
                """,
                (schedule_id,),
            ).fetchone()
            if schedule_row is None:
                raise KeyError(f"Unknown execution schedule: {schedule_id}")
            if bool(schedule_row["archived"]):
                raise ValueError(f"Execution schedule is archived: {schedule_id}")
            if not bool(schedule_row["enabled"]):
                raise ValueError(f"Execution schedule is disabled: {schedule_id}")
            active_count = connection.execute(
                """
                SELECT COUNT(*) AS active_count
                FROM schedule_dispatches
                WHERE schedule_id = %s
                  AND status IN ('enqueued', 'running')
                """,
                (schedule_id,),
            ).fetchone()["active_count"]
            if active_count >= schedule_row["max_concurrency"]:
                raise ValueError(
                    f"Execution schedule already has max_concurrency active dispatches: {schedule_id}"
                )
            dispatch_id = uuid.uuid4().hex[:16]
            connection.execute(
                """
                INSERT INTO schedule_dispatches (
                    dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                    started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                    claimed_by_worker_id, claimed_at, claim_expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    dispatch_id,
                    schedule_id,
                    schedule_row["target_kind"],
                    schedule_row["target_ref"],
                    resolved_enqueued_at,
                    "enqueued",
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            connection.execute(
                """
                UPDATE execution_schedules
                SET last_enqueued_at = %s
                WHERE schedule_id = %s
                """,
                (resolved_enqueued_at, schedule_id),
            )
        return ScheduleDispatchRecord(
            dispatch_id=dispatch_id,
            schedule_id=schedule_id,
            target_kind=schedule_row["target_kind"],
            target_ref=schedule_row["target_ref"],
            enqueued_at=resolved_enqueued_at,
            status="enqueued",
            started_at=None,
            completed_at=None,
            run_ids=(),
            failure_reason=None,
            worker_detail=None,
            claimed_by_worker_id=None,
            claimed_at=None,
            claim_expires_at=None,
        )

    def claim_schedule_dispatch(
        self,
        dispatch_id: str,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord:
        resolved_claimed_at = claimed_at or datetime.now(UTC)
        claim_expires_at = resolved_claimed_at + timedelta(seconds=lease_seconds)
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                WHERE dispatch_id = %s
                FOR UPDATE
                """,
                (dispatch_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
            existing = ScheduleDispatchRecord(
                dispatch_id=row["dispatch_id"],
                schedule_id=row["schedule_id"],
                target_kind=row["target_kind"],
                target_ref=row["target_ref"],
                enqueued_at=row["enqueued_at"],
                status=row["status"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                run_ids=tuple(json.loads(row["run_ids_json"] or "[]")),
                failure_reason=row["failure_reason"],
                worker_detail=row["worker_detail"],
                claimed_by_worker_id=row["claimed_by_worker_id"],
                claimed_at=row["claimed_at"],
                claim_expires_at=row["claim_expires_at"],
            )
            if existing.status != "enqueued":
                raise ValueError(
                    f"Schedule dispatch must be enqueued before claiming: {dispatch_id}"
                )
            cursor = connection.execute(
                """
                UPDATE schedule_dispatches
                SET status = %s,
                    started_at = %s,
                    completed_at = NULL,
                    failure_reason = NULL,
                    worker_detail = %s,
                    claimed_by_worker_id = %s,
                    claimed_at = %s,
                    claim_expires_at = %s
                WHERE dispatch_id = %s
                  AND status = 'enqueued'
                """,
                (
                    "running",
                    existing.started_at or resolved_claimed_at,
                    worker_detail if worker_detail is not None else existing.worker_detail,
                    worker_id,
                    resolved_claimed_at,
                    claim_expires_at,
                    dispatch_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError(
                    f"Schedule dispatch could not be claimed: {dispatch_id}"
                )
        return self.get_schedule_dispatch(dispatch_id)

    def claim_next_schedule_dispatch(
        self,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord | None:
        resolved_claimed_at = claimed_at or datetime.now(UTC)
        claim_expires_at = resolved_claimed_at + timedelta(seconds=lease_seconds)
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                WITH next_dispatch AS (
                    SELECT dispatch_id
                    FROM schedule_dispatches
                    WHERE status = 'enqueued'
                    ORDER BY enqueued_at, dispatch_id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE schedule_dispatches AS dispatch
                SET status = %s,
                    started_at = COALESCE(dispatch.started_at, %s),
                    completed_at = NULL,
                    failure_reason = NULL,
                    worker_detail = COALESCE(%s, dispatch.worker_detail),
                    claimed_by_worker_id = %s,
                    claimed_at = %s,
                    claim_expires_at = %s
                FROM next_dispatch
                WHERE dispatch.dispatch_id = next_dispatch.dispatch_id
                RETURNING dispatch.dispatch_id, dispatch.schedule_id, dispatch.target_kind,
                          dispatch.target_ref, dispatch.enqueued_at, dispatch.status,
                          dispatch.started_at, dispatch.completed_at, dispatch.run_ids_json,
                          dispatch.failure_reason, dispatch.worker_detail,
                          dispatch.claimed_by_worker_id, dispatch.claimed_at,
                          dispatch.claim_expires_at
                """,
                (
                    "running",
                    resolved_claimed_at,
                    worker_detail,
                    worker_id,
                    resolved_claimed_at,
                    claim_expires_at,
                ),
            ).fetchone()
        if row is None:
            return None
        normalized = {
            "dispatch_id": row["dispatch_id"],
            "schedule_id": row["schedule_id"],
            "target_kind": row["target_kind"],
            "target_ref": row["target_ref"],
            "enqueued_at": row["enqueued_at"].isoformat(),
            "status": row["status"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "run_ids_json": row["run_ids_json"] or "[]",
            "failure_reason": row["failure_reason"],
            "worker_detail": row["worker_detail"],
            "claimed_by_worker_id": row["claimed_by_worker_id"],
            "claimed_at": row["claimed_at"].isoformat() if row["claimed_at"] else None,
            "claim_expires_at": (
                row["claim_expires_at"].isoformat() if row["claim_expires_at"] else None
            ),
        }
        return _deserialize_schedule_dispatch_row(normalized)  # type: ignore[arg-type]

    def renew_schedule_dispatch_claim(
        self,
        dispatch_id: str,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord:
        resolved_claimed_at = claimed_at or datetime.now(UTC)
        claim_expires_at = resolved_claimed_at + timedelta(seconds=lease_seconds)
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                WHERE dispatch_id = %s
                FOR UPDATE
                """,
                (dispatch_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
            existing = ScheduleDispatchRecord(
                dispatch_id=row["dispatch_id"],
                schedule_id=row["schedule_id"],
                target_kind=row["target_kind"],
                target_ref=row["target_ref"],
                enqueued_at=row["enqueued_at"],
                status=row["status"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                run_ids=tuple(json.loads(row["run_ids_json"] or "[]")),
                failure_reason=row["failure_reason"],
                worker_detail=row["worker_detail"],
                claimed_by_worker_id=row["claimed_by_worker_id"],
                claimed_at=row["claimed_at"],
                claim_expires_at=row["claim_expires_at"],
            )
            if existing.status != "running":
                raise ValueError(
                    f"Schedule dispatch must be running before lease renewal: {dispatch_id}"
                )
            if existing.claimed_by_worker_id != worker_id:
                raise ValueError(
                    "Schedule dispatch lease can only be renewed by the claiming worker: "
                    f"{dispatch_id}"
                )
            cursor = connection.execute(
                """
                UPDATE schedule_dispatches
                SET worker_detail = %s,
                    claimed_at = %s,
                    claim_expires_at = %s
                WHERE dispatch_id = %s
                  AND status = 'running'
                  AND claimed_by_worker_id = %s
                """,
                (
                    worker_detail if worker_detail is not None else existing.worker_detail,
                    resolved_claimed_at,
                    claim_expires_at,
                    dispatch_id,
                    worker_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError(
                    f"Schedule dispatch lease could not be renewed: {dispatch_id}"
                )
        return self.get_schedule_dispatch(dispatch_id)

    def requeue_expired_schedule_dispatches(
        self,
        *,
        as_of: datetime | None = None,
        limit: int | None = None,
        recovered_by_worker_id: str | None = None,
    ) -> list[ScheduleDispatchRecoveryRecord]:
        resolved_as_of = as_of or datetime.now(UTC)
        recoveries: list[ScheduleDispatchRecoveryRecord] = []
        with self._connect(row_factory=dict_row) as connection:
            query = """
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                WHERE status = 'running'
                  AND claim_expires_at IS NOT NULL
                  AND claim_expires_at < %s
                ORDER BY claim_expires_at, dispatch_id
                FOR UPDATE SKIP LOCKED
            """
            parameters: list[object] = [resolved_as_of]
            if limit is not None:
                query += " LIMIT %s"
                parameters.append(limit)
            rows = connection.execute(query, tuple(parameters)).fetchall()
            for row in rows:
                existing = ScheduleDispatchRecord(
                    dispatch_id=row["dispatch_id"],
                    schedule_id=row["schedule_id"],
                    target_kind=row["target_kind"],
                    target_ref=row["target_ref"],
                    enqueued_at=row["enqueued_at"],
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    run_ids=tuple(json.loads(row["run_ids_json"] or "[]")),
                    failure_reason=row["failure_reason"],
                    worker_detail=row["worker_detail"],
                    claimed_by_worker_id=row["claimed_by_worker_id"],
                    claimed_at=row["claimed_at"],
                    claim_expires_at=row["claim_expires_at"],
                )
                recovery_reason = _build_stale_dispatch_failure_reason(
                    existing,
                    recovered_at=resolved_as_of,
                    recovered_by_worker_id=recovered_by_worker_id,
                )
                stale_detail = _build_stale_dispatch_worker_detail(
                    existing,
                    recovered_at=resolved_as_of,
                    recovered_by_worker_id=recovered_by_worker_id,
                )
                cursor = connection.execute(
                    """
                    UPDATE schedule_dispatches
                    SET status = %s,
                        completed_at = %s,
                        failure_reason = %s,
                        worker_detail = %s,
                        claim_expires_at = NULL
                    WHERE dispatch_id = %s
                      AND status = 'running'
                      AND claim_expires_at IS NOT NULL
                      AND claim_expires_at < %s
                    """,
                    (
                        "failed",
                        resolved_as_of,
                        recovery_reason,
                        stale_detail,
                        existing.dispatch_id,
                        resolved_as_of,
                    ),
                )
                if cursor.rowcount == 0:
                    continue
                stale_dispatch = ScheduleDispatchRecord(
                    dispatch_id=existing.dispatch_id,
                    schedule_id=existing.schedule_id,
                    target_kind=existing.target_kind,
                    target_ref=existing.target_ref,
                    enqueued_at=existing.enqueued_at,
                    status="failed",
                    started_at=existing.started_at,
                    completed_at=resolved_as_of,
                    run_ids=existing.run_ids,
                    failure_reason=recovery_reason,
                    worker_detail=stale_detail,
                    claimed_by_worker_id=existing.claimed_by_worker_id,
                    claimed_at=existing.claimed_at,
                    claim_expires_at=None,
                )
                schedule_row = connection.execute(
                    """
                    SELECT schedule_id, target_kind, target_ref, enabled, archived, max_concurrency
                    FROM execution_schedules
                    WHERE schedule_id = %s
                    """,
                    (existing.schedule_id,),
                ).fetchone()
                replacement_dispatch: ScheduleDispatchRecord | None = None
                if (
                    schedule_row is not None
                    and not bool(schedule_row["archived"])
                    and bool(schedule_row["enabled"])
                ):
                    active_count = connection.execute(
                        """
                        SELECT COUNT(*) AS active_count
                        FROM schedule_dispatches
                        WHERE schedule_id = %s
                          AND status IN ('enqueued', 'running')
                        """,
                        (existing.schedule_id,),
                    ).fetchone()["active_count"]
                    if active_count < schedule_row["max_concurrency"]:
                        replacement_dispatch_id = uuid.uuid4().hex[:16]
                        replacement_detail = _build_requeued_dispatch_worker_detail(
                            existing,
                            recovered_at=resolved_as_of,
                            recovered_by_worker_id=recovered_by_worker_id,
                        )
                        connection.execute(
                            """
                            INSERT INTO schedule_dispatches (
                                dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                                started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                                claimed_by_worker_id, claimed_at, claim_expires_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                replacement_dispatch_id,
                                existing.schedule_id,
                                schedule_row["target_kind"],
                                schedule_row["target_ref"],
                                resolved_as_of,
                                "enqueued",
                                None,
                                None,
                                "[]",
                                None,
                                replacement_detail,
                                None,
                                None,
                                None,
                            ),
                        )
                        connection.execute(
                            """
                            UPDATE execution_schedules
                            SET last_enqueued_at = %s
                            WHERE schedule_id = %s
                            """,
                            (resolved_as_of, existing.schedule_id),
                        )
                        replacement_dispatch = ScheduleDispatchRecord(
                            dispatch_id=replacement_dispatch_id,
                            schedule_id=existing.schedule_id,
                            target_kind=schedule_row["target_kind"],
                            target_ref=schedule_row["target_ref"],
                            enqueued_at=resolved_as_of,
                            status="enqueued",
                            started_at=None,
                            completed_at=None,
                            run_ids=(),
                            failure_reason=None,
                            worker_detail=replacement_detail,
                            claimed_by_worker_id=None,
                            claimed_at=None,
                            claim_expires_at=None,
                        )
                recoveries.append(
                    ScheduleDispatchRecoveryRecord(
                        stale_dispatch=stale_dispatch,
                        replacement_dispatch=replacement_dispatch,
                        recovered_at=resolved_as_of,
                        recovered_by_worker_id=recovered_by_worker_id,
                    )
                )
        return recoveries

    def mark_schedule_dispatch_status(
        self,
        dispatch_id: str,
        *,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        run_ids: tuple[str, ...] | None = None,
        failure_reason: str | None = None,
        worker_detail: str | None = None,
        expected_status: str | None = None,
        expected_worker_id: str | None = None,
    ) -> ScheduleDispatchRecord:
        existing = self.get_schedule_dispatch(dispatch_id)
        if expected_status is not None and existing.status != expected_status:
            raise ValueError(
                "Schedule dispatch status changed before update: "
                f"{dispatch_id} expected {expected_status}, found {existing.status}"
            )
        if (
            expected_worker_id is not None
            and existing.claimed_by_worker_id != expected_worker_id
        ):
            raise ValueError(
                "Schedule dispatch claim changed before update: "
                f"{dispatch_id} expected worker {expected_worker_id}, "
                f"found {existing.claimed_by_worker_id}"
            )
        if status == "enqueued":
            resolved_started_at = None
            resolved_completed_at = None
            resolved_run_ids: tuple[str, ...] = ()
            resolved_failure_reason = None
            resolved_worker_detail = worker_detail
            resolved_claimed_by_worker_id = None
            resolved_claimed_at = None
            resolved_claim_expires_at = None
        elif status == "running":
            resolved_started_at = started_at or existing.started_at
            resolved_completed_at = None
            resolved_run_ids = run_ids or ()
            resolved_failure_reason = None
            resolved_worker_detail = (
                worker_detail if worker_detail is not None else existing.worker_detail
            )
            resolved_claimed_by_worker_id = existing.claimed_by_worker_id
            resolved_claimed_at = existing.claimed_at
            resolved_claim_expires_at = existing.claim_expires_at
        elif status == "failed":
            resolved_started_at = started_at or existing.started_at
            resolved_completed_at = completed_at
            resolved_run_ids = run_ids if run_ids is not None else existing.run_ids
            resolved_failure_reason = (
                failure_reason
                if failure_reason is not None
                else existing.failure_reason
            )
            resolved_worker_detail = (
                worker_detail if worker_detail is not None else existing.worker_detail
            )
            resolved_claimed_by_worker_id = existing.claimed_by_worker_id
            resolved_claimed_at = existing.claimed_at
            resolved_claim_expires_at = None
        else:
            resolved_started_at = started_at or existing.started_at
            resolved_completed_at = completed_at
            resolved_run_ids = run_ids if run_ids is not None else existing.run_ids
            resolved_failure_reason = None
            resolved_worker_detail = (
                worker_detail if worker_detail is not None else existing.worker_detail
            )
            resolved_claimed_by_worker_id = existing.claimed_by_worker_id
            resolved_claimed_at = existing.claimed_at
            resolved_claim_expires_at = None
        with self._connect() as connection:
            query = """
                UPDATE schedule_dispatches
                SET status = %s,
                    started_at = %s,
                    completed_at = %s,
                    run_ids_json = %s,
                    failure_reason = %s,
                    worker_detail = %s,
                    claimed_by_worker_id = %s,
                    claimed_at = %s,
                    claim_expires_at = %s
                WHERE dispatch_id = %s
            """
            parameters: list[object] = [
                status,
                resolved_started_at,
                resolved_completed_at,
                json.dumps(list(resolved_run_ids)),
                resolved_failure_reason,
                resolved_worker_detail,
                resolved_claimed_by_worker_id,
                resolved_claimed_at,
                resolved_claim_expires_at,
                dispatch_id,
            ]
            if expected_status is not None:
                query += " AND status = %s"
                parameters.append(expected_status)
            if expected_worker_id is not None:
                query += " AND claimed_by_worker_id = %s"
                parameters.append(expected_worker_id)
            cursor = connection.execute(
                query,
                tuple(parameters),
            )
        if cursor.rowcount == 0:
            raise ValueError(f"Schedule dispatch could not be updated: {dispatch_id}")
        return self.get_schedule_dispatch(dispatch_id)

    def record_worker_heartbeat(
        self,
        heartbeat: WorkerHeartbeatCreate,
    ) -> WorkerHeartbeatRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO worker_heartbeats (
                    worker_id, status, active_dispatch_id, detail, observed_at
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (worker_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    active_dispatch_id = EXCLUDED.active_dispatch_id,
                    detail = EXCLUDED.detail,
                    observed_at = EXCLUDED.observed_at
                """,
                (
                    heartbeat.worker_id,
                    heartbeat.status,
                    heartbeat.active_dispatch_id,
                    heartbeat.detail,
                    heartbeat.observed_at,
                ),
            )
        return WorkerHeartbeatRecord(
            worker_id=heartbeat.worker_id,
            status=heartbeat.status,
            active_dispatch_id=heartbeat.active_dispatch_id,
            detail=heartbeat.detail,
            observed_at=heartbeat.observed_at,
        )

    def list_worker_heartbeats(self) -> list[WorkerHeartbeatRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT worker_id, status, active_dispatch_id, detail, observed_at
                FROM worker_heartbeats
                ORDER BY observed_at DESC, worker_id
                """
            ).fetchall()
        normalized = [
            {
                "worker_id": row["worker_id"],
                "status": row["status"],
                "active_dispatch_id": row["active_dispatch_id"],
                "detail": row["detail"],
                "observed_at": row["observed_at"].isoformat(),
            }
            for row in rows
        ]
        return [_deserialize_worker_heartbeat_row(row) for row in normalized]  # type: ignore[arg-type]

    def record_source_lineage(
        self,
        entries: tuple[SourceLineageCreate, ...],
    ) -> list[SourceLineageRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO source_lineage (
                        lineage_id, input_run_id, target_layer, target_name, target_kind,
                        row_count, source_system, source_run_id, recorded_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                            entry.recorded_at,
                        )
                        for entry in entries
                    ],
                )
        return self.list_source_lineage()

    def list_source_lineage(
        self,
        *,
        input_run_id: str | None = None,
        target_layer: str | None = None,
    ) -> list[SourceLineageRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if input_run_id is not None:
            clauses.append("input_run_id = %s")
            params.append(input_run_id)
        if target_layer is not None:
            clauses.append("target_layer = %s")
            params.append(target_layer)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"""
                SELECT lineage_id, input_run_id, target_layer, target_name, target_kind,
                       row_count, source_system, source_run_id, recorded_at
                FROM source_lineage
                {where_sql}
                ORDER BY recorded_at, lineage_id
                """,
                params,
            ).fetchall()
        normalized = [
            {
                "lineage_id": row["lineage_id"],
                "input_run_id": row["input_run_id"],
                "target_layer": row["target_layer"],
                "target_name": row["target_name"],
                "target_kind": row["target_kind"],
                "row_count": row["row_count"],
                "source_system": row["source_system"],
                "source_run_id": row["source_run_id"],
                "recorded_at": row["recorded_at"].isoformat(),
            }
            for row in rows
        ]
        return [_deserialize_source_lineage_row(row) for row in normalized]  # type: ignore[arg-type]

    def record_publication_audit(
        self,
        entries: tuple[PublicationAuditCreate, ...],
    ) -> list[PublicationAuditRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO publication_audit (
                        publication_audit_id, run_id, publication_key, relation_name, status, published_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            entry.publication_audit_id,
                            entry.run_id,
                            entry.publication_key,
                            entry.relation_name,
                            entry.status,
                            entry.published_at,
                        )
                        for entry in entries
                    ],
                )
        return self.list_publication_audit()

    def list_publication_audit(
        self,
        *,
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> list[PublicationAuditRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if run_id is not None:
            clauses.append("run_id = %s")
            params.append(run_id)
        if publication_key is not None:
            clauses.append("publication_key = %s")
            params.append(publication_key)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"""
                SELECT publication_audit_id, run_id, publication_key, relation_name, status, published_at
                FROM publication_audit
                {where_sql}
                ORDER BY published_at, publication_audit_id
                """,
                params,
            ).fetchall()
        normalized = [
            {
                "publication_audit_id": row["publication_audit_id"],
                "run_id": row["run_id"],
                "publication_key": row["publication_key"],
                "relation_name": row["relation_name"],
                "status": row["status"],
                "published_at": row["published_at"].isoformat(),
            }
            for row in rows
        ]
        return [_deserialize_publication_audit_row(row) for row in normalized]  # type: ignore[arg-type]

    def create_local_user(self, user: LocalUserCreate) -> LocalUserRecord:
        username = normalize_username(user.username)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO local_users (
                    user_id, username, password_hash, role, enabled, created_at, last_login_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user.user_id,
                    username,
                    user.password_hash,
                    user.role.value,
                    user.enabled,
                    user.created_at,
                    user.last_login_at,
                ),
            )
        return self.get_local_user(user.user_id)

    def get_local_user(self, user_id: str) -> LocalUserRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT user_id, username, password_hash, role, enabled, created_at, last_login_at
                FROM local_users
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown local user: {user_id}")
        return _deserialize_local_user_row(row)

    def get_local_user_by_username(self, username: str) -> LocalUserRecord:
        normalized_username = normalize_username(username)
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT user_id, username, password_hash, role, enabled, created_at, last_login_at
                FROM local_users
                WHERE username = %s
                """,
                (normalized_username,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown local user: {normalized_username}")
        return _deserialize_local_user_row(row)

    def list_local_users(self, *, enabled_only: bool = False) -> list[LocalUserRecord]:
        sql = """
            SELECT user_id, username, password_hash, role, enabled, created_at, last_login_at
            FROM local_users
        """
        params: list[object] = []
        if enabled_only:
            sql += " WHERE enabled = %s"
            params.append(True)
        sql += " ORDER BY created_at, username"
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql, params).fetchall()
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
            assignments.append("role = %s")
            params.append(role.value)
        if enabled is not None:
            assignments.append("enabled = %s")
            params.append(enabled)
        if not assignments:
            return self.get_local_user(user_id)
        params.append(user_id)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE local_users
                    SET {", ".join(assignments)}
                    WHERE user_id = %s
                    """,
                    params,
                )
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
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE local_users
                    SET password_hash = %s
                    WHERE user_id = %s
                    """,
                    (password_hash, user_id),
                )
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
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE local_users
                    SET last_login_at = %s
                    WHERE user_id = %s
                    """,
                    (resolved_logged_in_at, user_id),
                )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown local user: {user_id}")
        return self.get_local_user(user_id)

    def record_auth_audit_events(
        self,
        entries: tuple[AuthAuditEventCreate, ...],
    ) -> list[AuthAuditEventRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            entry.event_id,
                            entry.event_type,
                            entry.success,
                            entry.actor_user_id,
                            entry.actor_username,
                            entry.subject_user_id,
                            normalize_username(entry.subject_username)
                            if entry.subject_username
                            else None,
                            entry.remote_addr,
                            entry.user_agent,
                            entry.detail,
                            entry.occurred_at,
                        )
                        for entry in entries
                    ],
                )
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
            clauses.append("event_type = %s")
            params.append(event_type)
        if success is not None:
            clauses.append("success = %s")
            params.append(success)
        if actor_user_id is not None:
            clauses.append("actor_user_id = %s")
            params.append(actor_user_id)
        if subject_user_id is not None:
            clauses.append("subject_user_id = %s")
            params.append(subject_user_id)
        if subject_username is not None:
            clauses.append("subject_username = %s")
            params.append(normalize_username(subject_username))
        if since is not None:
            clauses.append("occurred_at >= %s")
            params.append(since)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY occurred_at DESC, event_id DESC"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_deserialize_auth_audit_event_row(row) for row in rows]  # type: ignore[arg-type]

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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
                continue

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_systems (
                    source_system_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    schedule_mode TEXT NOT NULL,
                    description TEXT,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_contracts (
                    dataset_contract_id TEXT PRIMARY KEY,
                    dataset_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    allow_extra_columns BOOLEAN NOT NULL,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    columns_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS column_mappings (
                    column_mapping_id TEXT PRIMARY KEY,
                    source_system_id TEXT NOT NULL REFERENCES source_systems (source_system_id),
                    dataset_contract_id TEXT NOT NULL REFERENCES dataset_contracts (dataset_contract_id),
                    version INTEGER NOT NULL,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    rules_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transformation_packages (
                    transformation_package_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    handler_key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_definitions (
                    publication_definition_id TEXT PRIMARY KEY,
                    transformation_package_id TEXT NOT NULL REFERENCES transformation_packages (transformation_package_id),
                    publication_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_assets (
                    source_asset_id TEXT PRIMARY KEY,
                    source_system_id TEXT NOT NULL REFERENCES source_systems (source_system_id),
                    dataset_contract_id TEXT NOT NULL REFERENCES dataset_contracts (dataset_contract_id),
                    column_mapping_id TEXT NOT NULL REFERENCES column_mappings (column_mapping_id),
                    transformation_package_id TEXT REFERENCES transformation_packages (transformation_package_id),
                    name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    description TEXT,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_definitions (
                    ingestion_definition_id TEXT PRIMARY KEY,
                    source_asset_id TEXT NOT NULL REFERENCES source_assets (source_asset_id),
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
                    enabled BOOLEAN NOT NULL,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    source_name TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    target_kind TEXT NOT NULL,
                    target_ref TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    max_concurrency INTEGER NOT NULL,
                    next_due_at TIMESTAMPTZ,
                    last_enqueued_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schedule_dispatches (
                    dispatch_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL REFERENCES execution_schedules (schedule_id),
                    target_kind TEXT NOT NULL,
                    target_ref TEXT NOT NULL,
                    enqueued_at TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ,
                    run_ids_json TEXT NOT NULL DEFAULT '[]',
                    failure_reason TEXT,
                    worker_detail TEXT,
                    claimed_by_worker_id TEXT,
                    claimed_at TIMESTAMPTZ,
                    claim_expires_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    worker_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    active_dispatch_id TEXT,
                    detail TEXT,
                    observed_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_lineage (
                    lineage_id TEXT PRIMARY KEY,
                    input_run_id TEXT,
                    target_layer TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    row_count INTEGER,
                    source_system TEXT,
                    source_run_id TEXT,
                    recorded_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_audit (
                    publication_audit_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    publication_key TEXT NOT NULL,
                    relation_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    published_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS local_users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    last_login_at TIMESTAMPTZ
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    actor_user_id TEXT,
                    actor_username TEXT,
                    subject_user_id TEXT,
                    subject_username TEXT,
                    remote_addr TEXT,
                    user_agent TEXT,
                    detail TEXT,
                    occurred_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                ALTER TABLE source_systems
                ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
            connection.execute(
                """
                ALTER TABLE dataset_contracts
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE column_mappings
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE source_assets
                ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
            connection.execute(
                """
                ALTER TABLE source_assets
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE ingestion_definitions
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE execution_schedules
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS run_ids_json TEXT NOT NULL DEFAULT '[]'
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS failure_reason TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS worker_detail TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS claimed_by_worker_id TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS claim_expires_at TIMESTAMPTZ
                """
            )
            self._seed_builtins(connection)

    def _seed_builtins(self, connection: psycopg.Connection) -> None:
        now = datetime.now(UTC)
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO transformation_packages (
                    transformation_package_id, name, handler_key, version, description, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (transformation_package_id) DO NOTHING
                """,
                [
                    (
                        package.transformation_package_id,
                        package.name,
                        package.handler_key,
                        package.version,
                        package.description,
                        now,
                    )
                    for package in _BUILTIN_TRANSFORMATION_PACKAGES
                ],
            )
            cursor.executemany(
                """
                INSERT INTO publication_definitions (
                    publication_definition_id, transformation_package_id, publication_key, name, description, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (publication_definition_id) DO NOTHING
                """,
                [
                    (
                        publication.publication_definition_id,
                        publication.transformation_package_id,
                        publication.publication_key,
                        publication.name,
                        publication.description,
                        now,
                    )
                    for publication in _BUILTIN_PUBLICATION_DEFINITIONS
                ],
            )


def _deserialize_local_user_row(row: dict[str, object]) -> LocalUserRecord:
    return LocalUserRecord(
        user_id=str(row["user_id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        role=UserRole(str(row["role"])),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],  # type: ignore[arg-type]
        last_login_at=row["last_login_at"],  # type: ignore[arg-type]
    )


def _validate_execution_schedule_target_postgres(
    repository: PostgresIngestionConfigRepository,
    target_kind: str,
    target_ref: str,
) -> None:
    if target_kind == "ingestion_definition":
        definition = repository.get_ingestion_definition(target_ref)
        if definition.archived:
            raise ValueError(f"Ingestion definition is archived: {target_ref}")
