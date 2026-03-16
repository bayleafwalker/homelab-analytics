from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import cast

from packages.storage.control_plane import ExecutionStore
from packages.storage.ingestion_catalog import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    IngestionDefinitionRecord,
    SourceAssetCreate,
    SourceAssetRecord,
    TransformationPackageRecord,
    _deserialize_request_headers,
    _serialize_request_headers,
)


def _deserialize_source_asset_row(row: sqlite3.Row) -> SourceAssetRecord:
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
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _deserialize_ingestion_definition_row(
    row: sqlite3.Row,
) -> IngestionDefinitionRecord:
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
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class SQLiteAssetDefinitionCatalogMixin:
    def _connect(self) -> sqlite3.Connection:
        raise NotImplementedError

    def get_dataset_contract(self, dataset_contract_id: str) -> DatasetContractConfigRecord:
        raise NotImplementedError

    def get_column_mapping(self, column_mapping_id: str) -> ColumnMappingRecord:
        raise NotImplementedError

    def get_transformation_package(
        self,
        transformation_package_id: str,
    ) -> TransformationPackageRecord:
        raise NotImplementedError

    def _validate_source_asset_dependencies(
        self,
        source_asset: SourceAssetCreate,
    ) -> None:
        dataset_contract = self.get_dataset_contract(source_asset.dataset_contract_id)
        if dataset_contract.archived:
            raise ValueError(
                f"Dataset contract is archived: {source_asset.dataset_contract_id}"
            )
        column_mapping = self.get_column_mapping(source_asset.column_mapping_id)
        if column_mapping.archived:
            raise ValueError(f"Column mapping is archived: {source_asset.column_mapping_id}")
        if source_asset.transformation_package_id is not None:
            transformation_package = self.get_transformation_package(
                source_asset.transformation_package_id
            )
            if transformation_package.archived:
                raise ValueError(
                    "Transformation package is archived: "
                    f"{source_asset.transformation_package_id}"
                )

    def create_source_asset(self, source_asset: SourceAssetCreate) -> SourceAssetRecord:
        self._validate_source_asset_dependencies(source_asset)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_assets (
                    source_asset_id,
                    source_system_id,
                    dataset_contract_id,
                    column_mapping_id,
                    transformation_package_id,
                    name,
                    asset_type,
                    description,
                    enabled,
                    archived,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int(source_asset.enabled),
                    int(source_asset.archived),
                    source_asset.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_source_asset(source_asset.source_asset_id)

    def update_source_asset(self, source_asset: SourceAssetCreate) -> SourceAssetRecord:
        self._validate_source_asset_dependencies(source_asset)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_assets
                SET source_system_id = ?,
                    dataset_contract_id = ?,
                    column_mapping_id = ?,
                    transformation_package_id = ?,
                    name = ?,
                    asset_type = ?,
                    description = ?,
                    enabled = ?,
                    archived = ?
                WHERE source_asset_id = ?
                """,
                (
                    source_asset.source_system_id,
                    source_asset.dataset_contract_id,
                    source_asset.column_mapping_id,
                    source_asset.transformation_package_id,
                    source_asset.name,
                    source_asset.asset_type,
                    source_asset.description,
                    int(source_asset.enabled),
                    int(source_asset.archived),
                    source_asset.source_asset_id,
                ),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source asset: {source_asset.source_asset_id}")
        return self.get_source_asset(source_asset.source_asset_id)

    def get_source_asset(self, source_asset_id: str) -> SourceAssetRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    source_asset_id,
                    source_system_id,
                    dataset_contract_id,
                    column_mapping_id,
                    transformation_package_id,
                    name,
                    asset_type,
                    description,
                    enabled,
                    archived,
                    created_at
                FROM source_assets
                WHERE source_asset_id = ?
                """,
                (source_asset_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown source asset: {source_asset_id}")
        return _deserialize_source_asset_row(row)

    def list_source_assets(
        self,
        *,
        include_archived: bool = False,
    ) -> list[SourceAssetRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            sql = """
                SELECT
                    source_asset_id,
                    source_system_id,
                    dataset_contract_id,
                    column_mapping_id,
                    transformation_package_id,
                    name,
                    asset_type,
                    description,
                    enabled,
                    archived,
                    created_at
                FROM source_assets
            """
            if not include_archived:
                sql += " WHERE archived = 0"
            sql += " ORDER BY created_at, source_asset_id"
            rows = connection.execute(sql).fetchall()

        return [_deserialize_source_asset_row(row) for row in rows]

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
                SET archived = ?,
                    enabled = CASE WHEN ? = 1 THEN 0 ELSE enabled END
                WHERE source_asset_id = ?
                """,
                (int(archived), int(archived), source_asset_id),
            )
            connection.commit()
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
                "DELETE FROM source_assets WHERE source_asset_id = ?",
                (source_asset_id,),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source asset: {source_asset_id}")

    def find_source_asset_by_binding(
        self,
        *,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
    ) -> SourceAssetRecord | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    source_asset_id,
                    source_system_id,
                    dataset_contract_id,
                    column_mapping_id,
                    transformation_package_id,
                    name,
                    asset_type,
                    description,
                    enabled,
                    archived,
                    created_at
                FROM source_assets
                WHERE source_system_id = ?
                  AND dataset_contract_id = ?
                  AND column_mapping_id = ?
                  AND enabled = 1
                  AND archived = 0
                ORDER BY created_at, source_asset_id
                """,
                (
                    source_system_id,
                    dataset_contract_id,
                    column_mapping_id,
                ),
            ).fetchall()

        if not rows:
            return None
        if len(rows) > 1:
            raise ValueError(
                "Multiple source assets match the configured CSV binding; use source_asset_id-bound ingestion instead."
            )
        return _deserialize_source_asset_row(rows[0])

    def _validate_ingestion_definition_dependencies(
        self,
        ingestion_definition: IngestionDefinitionCreate,
    ) -> None:
        source_asset = self.get_source_asset(ingestion_definition.source_asset_id)
        if source_asset.archived:
            raise ValueError(
                f"Source asset is archived: {ingestion_definition.source_asset_id}"
            )

    def create_ingestion_definition(
        self,
        ingestion_definition: IngestionDefinitionCreate,
    ) -> IngestionDefinitionRecord:
        self._validate_ingestion_definition_dependencies(ingestion_definition)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_definitions (
                    ingestion_definition_id,
                    source_asset_id,
                    transport,
                    schedule_mode,
                    source_path,
                    file_pattern,
                    processed_path,
                    failed_path,
                    poll_interval_seconds,
                    request_url,
                    request_method,
                    request_headers_json,
                    request_timeout_seconds,
                    response_format,
                    output_file_name,
                    enabled,
                    archived,
                    source_name,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int(ingestion_definition.enabled),
                    int(ingestion_definition.archived),
                    ingestion_definition.source_name,
                    ingestion_definition.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_ingestion_definition(
            ingestion_definition.ingestion_definition_id
        )

    def update_ingestion_definition(
        self,
        ingestion_definition: IngestionDefinitionCreate,
    ) -> IngestionDefinitionRecord:
        self._validate_ingestion_definition_dependencies(ingestion_definition)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ingestion_definitions
                SET source_asset_id = ?,
                    transport = ?,
                    schedule_mode = ?,
                    source_path = ?,
                    file_pattern = ?,
                    processed_path = ?,
                    failed_path = ?,
                    poll_interval_seconds = ?,
                    request_url = ?,
                    request_method = ?,
                    request_headers_json = ?,
                    request_timeout_seconds = ?,
                    response_format = ?,
                    output_file_name = ?,
                    enabled = ?,
                    archived = ?,
                    source_name = ?
                WHERE ingestion_definition_id = ?
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
                    int(ingestion_definition.enabled),
                    int(ingestion_definition.archived),
                    ingestion_definition.source_name,
                    ingestion_definition.ingestion_definition_id,
                ),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(
                f"Unknown ingestion definition: {ingestion_definition.ingestion_definition_id}"
            )
        return self.get_ingestion_definition(
            ingestion_definition.ingestion_definition_id
        )

    def get_ingestion_definition(
        self,
        ingestion_definition_id: str,
    ) -> IngestionDefinitionRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    ingestion_definition_id,
                    source_asset_id,
                    transport,
                    schedule_mode,
                    source_path,
                    file_pattern,
                    processed_path,
                    failed_path,
                    poll_interval_seconds,
                    request_url,
                    request_method,
                    request_headers_json,
                    request_timeout_seconds,
                    response_format,
                    output_file_name,
                    enabled,
                    archived,
                    source_name,
                    created_at
                FROM ingestion_definitions
                WHERE ingestion_definition_id = ?
                """,
                (ingestion_definition_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown ingestion definition: {ingestion_definition_id}")
        return _deserialize_ingestion_definition_row(row)

    def list_ingestion_definitions(
        self,
        *,
        enabled_only: bool = False,
        include_archived: bool = False,
    ) -> list[IngestionDefinitionRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            query = """
                SELECT
                    ingestion_definition_id,
                    source_asset_id,
                    transport,
                    schedule_mode,
                    source_path,
                    file_pattern,
                    processed_path,
                    failed_path,
                    poll_interval_seconds,
                    request_url,
                    request_method,
                    request_headers_json,
                    request_timeout_seconds,
                    response_format,
                    output_file_name,
                    enabled,
                    archived,
                    source_name,
                    created_at
                FROM ingestion_definitions
            """
            clauses: list[str] = []
            if enabled_only:
                clauses.append("enabled = 1")
            if not include_archived:
                clauses.append("archived = 0")
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY created_at, ingestion_definition_id"
            rows = connection.execute(query).fetchall()

        return [_deserialize_ingestion_definition_row(row) for row in rows]

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
                SET archived = ?,
                    enabled = CASE WHEN ? = 1 THEN 0 ELSE enabled END
                WHERE ingestion_definition_id = ?
                """,
                (int(archived), int(archived), ingestion_definition_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown ingestion definition: {ingestion_definition_id}")
        return self.get_ingestion_definition(ingestion_definition_id)

    def delete_ingestion_definition(self, ingestion_definition_id: str) -> None:
        definition = self.get_ingestion_definition(ingestion_definition_id)
        if not definition.archived:
            raise ValueError("Archive ingestion definition before deleting it.")
        execution_store = cast(ExecutionStore, self)
        dependent_schedules = [
            record.schedule_id
            for record in execution_store.list_execution_schedules(include_archived=True)
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
                "DELETE FROM ingestion_definitions WHERE ingestion_definition_id = ?",
                (ingestion_definition_id,),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown ingestion definition: {ingestion_definition_id}")
