from __future__ import annotations

from datetime import datetime
from typing import cast

import psycopg
from psycopg.rows import dict_row

from packages.storage.control_plane import ExecutionStore
from packages.storage.ingestion_catalog import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    IngestionDefinitionRecord,
    SourceAssetCreate,
    SourceAssetRecord,
    SourceFreshnessConfigCreate,
    SourceFreshnessConfigRecord,
    TransformationPackageRecord,
    _deserialize_request_headers,
    _serialize_request_headers,
)


def _deserialize_source_asset_row(row: dict[str, object]) -> SourceAssetRecord:
    return SourceAssetRecord(
        source_asset_id=str(row["source_asset_id"]),
        source_system_id=str(row["source_system_id"]),
        dataset_contract_id=str(row["dataset_contract_id"]),
        column_mapping_id=str(row["column_mapping_id"]),
        transformation_package_id=(
            str(row["transformation_package_id"])
            if row["transformation_package_id"] is not None
            else None
        ),
        name=str(row["name"]),
        asset_type=str(row["asset_type"]),
        description=str(row["description"]) if row["description"] is not None else None,
        enabled=bool(row["enabled"]),
        archived=bool(row["archived"]),
        created_at=_coerce_datetime_value(row["created_at"]),
    )


def _deserialize_ingestion_definition_row(
    row: dict[str, object],
) -> IngestionDefinitionRecord:
    return IngestionDefinitionRecord(
        ingestion_definition_id=str(row["ingestion_definition_id"]),
        source_asset_id=str(row["source_asset_id"]),
        transport=str(row["transport"]),
        schedule_mode=str(row["schedule_mode"]),
        source_path=str(row["source_path"]),
        file_pattern=str(row["file_pattern"]),
        processed_path=str(row["processed_path"]) if row["processed_path"] is not None else None,
        failed_path=str(row["failed_path"]) if row["failed_path"] is not None else None,
        poll_interval_seconds=(
            _coerce_int_value(row["poll_interval_seconds"])
            if row["poll_interval_seconds"] is not None
            else None
        ),
        request_url=str(row["request_url"]) if row["request_url"] is not None else None,
        request_method=(
            str(row["request_method"]) if row["request_method"] is not None else None
        ),
        request_headers=_deserialize_request_headers(
            str(row["request_headers_json"])
            if row["request_headers_json"] is not None
            else None
        ),
        request_timeout_seconds=(
            _coerce_int_value(row["request_timeout_seconds"])
            if row["request_timeout_seconds"] is not None
            else None
        ),
        response_format=(
            str(row["response_format"]) if row["response_format"] is not None else None
        ),
        output_file_name=(
            str(row["output_file_name"]) if row["output_file_name"] is not None else None
        ),
        enabled=bool(row["enabled"]),
        archived=bool(row["archived"]),
        source_name=str(row["source_name"]) if row["source_name"] is not None else None,
        created_at=_coerce_datetime_value(row["created_at"]),
    )


def _deserialize_source_freshness_config_row(
    row: dict[str, object],
) -> SourceFreshnessConfigRecord:
    return SourceFreshnessConfigRecord(
        source_asset_id=str(row["source_asset_id"]),
        acquisition_mode=str(row["acquisition_mode"]),
        expected_frequency=str(row["expected_frequency"]),
        coverage_kind=str(row["coverage_kind"]),
        due_day_of_month=(
            _coerce_int_value(row["due_day_of_month"])
            if row["due_day_of_month"] is not None
            else None
        ),
        expected_window_days=_coerce_int_value(row["expected_window_days"]),
        freshness_sla_days=_coerce_int_value(row["freshness_sla_days"]),
        sensitivity_class=str(row["sensitivity_class"]),
        reminder_channel=str(row["reminder_channel"]),
        requires_human_action=bool(row["requires_human_action"]),
        created_at=_coerce_datetime_value(row["created_at"]),
        updated_at=_coerce_datetime_value(row["updated_at"]),
    )


def _coerce_datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _coerce_int_value(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def _coerce_row_mapping(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise TypeError(f"Unsupported row value: {row!r}")
    return cast(dict[str, object], row)


class PostgresAssetDefinitionCatalogMixin:
    def _connect(
        self,
        *,
        row_factory: object = None,
    ) -> psycopg.Connection[object]:
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
        self._validate_source_asset_dependencies(source_asset)
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
        return _deserialize_source_asset_row(_coerce_row_mapping(row))

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
        return [_deserialize_source_asset_row(_coerce_row_mapping(row)) for row in rows]

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

    def create_source_freshness_config(
        self,
        freshness_config: SourceFreshnessConfigCreate,
    ) -> SourceFreshnessConfigRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_freshness_configs (
                    source_asset_id,
                    acquisition_mode,
                    expected_frequency,
                    coverage_kind,
                    due_day_of_month,
                    expected_window_days,
                    freshness_sla_days,
                    sensitivity_class,
                    reminder_channel,
                    requires_human_action,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    freshness_config.source_asset_id,
                    freshness_config.acquisition_mode,
                    freshness_config.expected_frequency,
                    freshness_config.coverage_kind,
                    freshness_config.due_day_of_month,
                    freshness_config.expected_window_days,
                    freshness_config.freshness_sla_days,
                    freshness_config.sensitivity_class,
                    freshness_config.reminder_channel,
                    freshness_config.requires_human_action,
                    freshness_config.created_at,
                    freshness_config.updated_at,
                ),
            )
        return self.get_source_freshness_config(freshness_config.source_asset_id)

    def update_source_freshness_config(
        self,
        freshness_config: SourceFreshnessConfigCreate,
    ) -> SourceFreshnessConfigRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_freshness_configs
                SET acquisition_mode = %s,
                    expected_frequency = %s,
                    coverage_kind = %s,
                    due_day_of_month = %s,
                    expected_window_days = %s,
                    freshness_sla_days = %s,
                    sensitivity_class = %s,
                    reminder_channel = %s,
                    requires_human_action = %s,
                    updated_at = %s
                WHERE source_asset_id = %s
                """,
                (
                    freshness_config.acquisition_mode,
                    freshness_config.expected_frequency,
                    freshness_config.coverage_kind,
                    freshness_config.due_day_of_month,
                    freshness_config.expected_window_days,
                    freshness_config.freshness_sla_days,
                    freshness_config.sensitivity_class,
                    freshness_config.reminder_channel,
                    freshness_config.requires_human_action,
                    freshness_config.updated_at,
                    freshness_config.source_asset_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(
                f"Unknown source freshness config: {freshness_config.source_asset_id}"
            )
        return self.get_source_freshness_config(freshness_config.source_asset_id)

    def get_source_freshness_config(self, source_asset_id: str) -> SourceFreshnessConfigRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT
                    source_asset_id,
                    acquisition_mode,
                    expected_frequency,
                    coverage_kind,
                    due_day_of_month,
                    expected_window_days,
                    freshness_sla_days,
                    sensitivity_class,
                    reminder_channel,
                    requires_human_action,
                    created_at,
                    updated_at
                FROM source_freshness_configs
                WHERE source_asset_id = %s
                """,
                (source_asset_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown source freshness config: {source_asset_id}")
        return _deserialize_source_freshness_config_row(_coerce_row_mapping(row))

    def list_source_freshness_configs(self) -> list[SourceFreshnessConfigRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT
                    source_asset_id,
                    acquisition_mode,
                    expected_frequency,
                    coverage_kind,
                    due_day_of_month,
                    expected_window_days,
                    freshness_sla_days,
                    sensitivity_class,
                    reminder_channel,
                    requires_human_action,
                    created_at,
                    updated_at
                FROM source_freshness_configs
                ORDER BY created_at, source_asset_id
                """
            ).fetchall()
        return [_deserialize_source_freshness_config_row(_coerce_row_mapping(row)) for row in rows]

    def delete_source_freshness_config(self, source_asset_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM source_freshness_configs WHERE source_asset_id = %s",
                (source_asset_id,),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source freshness config: {source_asset_id}")

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
        return _deserialize_source_asset_row(_coerce_row_mapping(rows[0]))

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
        self._validate_ingestion_definition_dependencies(ingestion_definition)
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
        return _deserialize_ingestion_definition_row(_coerce_row_mapping(row))

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
            _deserialize_ingestion_definition_row(_coerce_row_mapping(row))
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
                "DELETE FROM ingestion_definitions WHERE ingestion_definition_id = %s",
                (ingestion_definition_id,),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown ingestion definition: {ingestion_definition_id}")
