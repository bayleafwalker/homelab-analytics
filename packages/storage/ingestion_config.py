from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from packages.pipelines.csv_validation import ColumnContract, ColumnType, DatasetContract
from packages.shared.extensions import ExtensionRegistry


@dataclass(frozen=True)
class SourceSystemCreate:
    source_system_id: str
    name: str
    source_type: str
    transport: str
    schedule_mode: str
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SourceSystemRecord:
    source_system_id: str
    name: str
    source_type: str
    transport: str
    schedule_mode: str
    description: str | None
    created_at: datetime


@dataclass(frozen=True)
class DatasetColumnConfig:
    name: str
    type: ColumnType
    required: bool = True


@dataclass(frozen=True)
class DatasetContractConfigCreate:
    dataset_contract_id: str
    dataset_name: str
    version: int
    allow_extra_columns: bool
    columns: tuple[DatasetColumnConfig, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DatasetContractConfigRecord:
    dataset_contract_id: str
    dataset_name: str
    version: int
    allow_extra_columns: bool
    columns: tuple[DatasetColumnConfig, ...]
    created_at: datetime


@dataclass(frozen=True)
class ColumnMappingRule:
    target_column: str
    source_column: str | None = None
    default_value: str | None = None


@dataclass(frozen=True)
class ColumnMappingCreate:
    column_mapping_id: str
    source_system_id: str
    dataset_contract_id: str
    version: int
    rules: tuple[ColumnMappingRule, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ColumnMappingRecord:
    column_mapping_id: str
    source_system_id: str
    dataset_contract_id: str
    version: int
    rules: tuple[ColumnMappingRule, ...]
    created_at: datetime


@dataclass(frozen=True)
class SourceAssetCreate:
    source_asset_id: str
    source_system_id: str
    dataset_contract_id: str
    column_mapping_id: str
    name: str
    asset_type: str
    transformation_package_id: str | None = None
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SourceAssetRecord:
    source_asset_id: str
    source_system_id: str
    dataset_contract_id: str
    column_mapping_id: str
    transformation_package_id: str | None
    name: str
    asset_type: str
    description: str | None
    created_at: datetime


@dataclass(frozen=True)
class TransformationPackageCreate:
    transformation_package_id: str
    name: str
    handler_key: str
    version: int
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class TransformationPackageRecord:
    transformation_package_id: str
    name: str
    handler_key: str
    version: int
    description: str | None
    created_at: datetime


@dataclass(frozen=True)
class PublicationDefinitionCreate:
    publication_definition_id: str
    transformation_package_id: str
    publication_key: str
    name: str
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PublicationDefinitionRecord:
    publication_definition_id: str
    transformation_package_id: str
    publication_key: str
    name: str
    description: str | None
    created_at: datetime


@dataclass(frozen=True)
class RequestHeaderSecretRef:
    name: str
    secret_name: str
    secret_key: str


@dataclass(frozen=True)
class IngestionDefinitionCreate:
    ingestion_definition_id: str
    source_asset_id: str
    transport: str
    schedule_mode: str
    source_path: str
    file_pattern: str = "*.csv"
    processed_path: str | None = None
    failed_path: str | None = None
    poll_interval_seconds: int | None = None
    request_url: str | None = None
    request_method: str | None = None
    request_headers: tuple[RequestHeaderSecretRef, ...] = ()
    request_timeout_seconds: int | None = None
    response_format: str | None = None
    output_file_name: str | None = None
    enabled: bool = True
    source_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class IngestionDefinitionRecord:
    ingestion_definition_id: str
    source_asset_id: str
    transport: str
    schedule_mode: str
    source_path: str
    file_pattern: str
    processed_path: str | None
    failed_path: str | None
    poll_interval_seconds: int | None
    request_url: str | None
    request_method: str | None
    request_headers: tuple[RequestHeaderSecretRef, ...]
    request_timeout_seconds: int | None
    response_format: str | None
    output_file_name: str | None
    enabled: bool
    source_name: str | None
    created_at: datetime


class IngestionConfigRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_source_system(
        self,
        source_system: SourceSystemCreate,
    ) -> SourceSystemRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_systems (
                    source_system_id,
                    name,
                    source_type,
                    transport,
                    schedule_mode,
                    description,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_system.source_system_id,
                    source_system.name,
                    source_system.source_type,
                    source_system.transport,
                    source_system.schedule_mode,
                    source_system.description,
                    source_system.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_source_system(source_system.source_system_id)

    def get_source_system(self, source_system_id: str) -> SourceSystemRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    source_system_id,
                    name,
                    source_type,
                    transport,
                    schedule_mode,
                    description,
                    created_at
                FROM source_systems
                WHERE source_system_id = ?
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_source_systems(self) -> list[SourceSystemRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    source_system_id,
                    name,
                    source_type,
                    transport,
                    schedule_mode,
                    description,
                    created_at
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
                created_at=datetime.fromisoformat(row["created_at"]),
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
                    dataset_contract_id,
                    dataset_name,
                    version,
                    allow_extra_columns,
                    columns_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_contract.dataset_contract_id,
                    dataset_contract.dataset_name,
                    dataset_contract.version,
                    int(dataset_contract.allow_extra_columns),
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
                    dataset_contract.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_dataset_contract(dataset_contract.dataset_contract_id)

    def get_dataset_contract(
        self,
        dataset_contract_id: str,
    ) -> DatasetContractConfigRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    dataset_contract_id,
                    dataset_name,
                    version,
                    allow_extra_columns,
                    columns_json,
                    created_at
                FROM dataset_contracts
                WHERE dataset_contract_id = ?
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_dataset_contracts(self) -> list[DatasetContractConfigRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    dataset_contract_id,
                    dataset_name,
                    version,
                    allow_extra_columns,
                    columns_json,
                    created_at
                FROM dataset_contracts
                ORDER BY created_at, dataset_contract_id
                """
            ).fetchall()

        return [
            DatasetContractConfigRecord(
                dataset_contract_id=row["dataset_contract_id"],
                dataset_name=row["dataset_name"],
                version=row["version"],
                allow_extra_columns=bool(row["allow_extra_columns"]),
                columns=_deserialize_columns(row["columns_json"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def create_column_mapping(
        self,
        column_mapping: ColumnMappingCreate,
    ) -> ColumnMappingRecord:
        _validate_mapping_rules(column_mapping.rules)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO column_mappings (
                    column_mapping_id,
                    source_system_id,
                    dataset_contract_id,
                    version,
                    rules_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    column_mapping.column_mapping_id,
                    column_mapping.source_system_id,
                    column_mapping.dataset_contract_id,
                    column_mapping.version,
                    json.dumps([asdict(rule) for rule in column_mapping.rules]),
                    column_mapping.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_column_mapping(column_mapping.column_mapping_id)

    def get_column_mapping(self, column_mapping_id: str) -> ColumnMappingRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    column_mapping_id,
                    source_system_id,
                    dataset_contract_id,
                    version,
                    rules_json,
                    created_at
                FROM column_mappings
                WHERE column_mapping_id = ?
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_column_mappings(self) -> list[ColumnMappingRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    column_mapping_id,
                    source_system_id,
                    dataset_contract_id,
                    version,
                    rules_json,
                    created_at
                FROM column_mappings
                ORDER BY created_at, column_mapping_id
                """
            ).fetchall()

        return [
            ColumnMappingRecord(
                column_mapping_id=row["column_mapping_id"],
                source_system_id=row["source_system_id"],
                dataset_contract_id=row["dataset_contract_id"],
                version=row["version"],
                rules=_deserialize_rules(row["rules_json"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def create_transformation_package(
        self,
        transformation_package: TransformationPackageCreate,
    ) -> TransformationPackageRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO transformation_packages (
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
                    transformation_package.transformation_package_id,
                    transformation_package.name,
                    transformation_package.handler_key,
                    transformation_package.version,
                    transformation_package.description,
                    transformation_package.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_transformation_package(
            transformation_package.transformation_package_id
        )

    def get_transformation_package(
        self,
        transformation_package_id: str,
    ) -> TransformationPackageRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    transformation_package_id,
                    name,
                    handler_key,
                    version,
                    description,
                    created_at
                FROM transformation_packages
                WHERE transformation_package_id = ?
                """,
                (transformation_package_id,),
            ).fetchone()

        if row is None:
            raise KeyError(
                f"Unknown transformation package: {transformation_package_id}"
            )
        return TransformationPackageRecord(
            transformation_package_id=row["transformation_package_id"],
            name=row["name"],
            handler_key=row["handler_key"],
            version=row["version"],
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_transformation_packages(self) -> list[TransformationPackageRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    transformation_package_id,
                    name,
                    handler_key,
                    version,
                    description,
                    created_at
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
                created_at=datetime.fromisoformat(row["created_at"]),
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
                    publication_definition.publication_definition_id,
                    publication_definition.transformation_package_id,
                    publication_definition.publication_key,
                    publication_definition.name,
                    publication_definition.description,
                    publication_definition.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_publication_definition(
            publication_definition.publication_definition_id
        )

    def get_publication_definition(
        self,
        publication_definition_id: str,
    ) -> PublicationDefinitionRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    publication_definition_id,
                    transformation_package_id,
                    publication_key,
                    name,
                    description,
                    created_at
                FROM publication_definitions
                WHERE publication_definition_id = ?
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_publication_definitions(
        self,
        *,
        transformation_package_id: str | None = None,
    ) -> list[PublicationDefinitionRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            if transformation_package_id is None:
                rows = connection.execute(
                    """
                    SELECT
                        publication_definition_id,
                        transformation_package_id,
                        publication_key,
                        name,
                        description,
                        created_at
                    FROM publication_definitions
                    ORDER BY created_at, publication_definition_id
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        publication_definition_id,
                        transformation_package_id,
                        publication_key,
                        name,
                        description,
                        created_at
                    FROM publication_definitions
                    WHERE transformation_package_id = ?
                    ORDER BY created_at, publication_definition_id
                    """,
                    (transformation_package_id,),
                ).fetchall()

        return [
            PublicationDefinitionRecord(
                publication_definition_id=row["publication_definition_id"],
                transformation_package_id=row["transformation_package_id"],
                publication_key=row["publication_key"],
                name=row["name"],
                description=row["description"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def create_source_asset(self, source_asset: SourceAssetCreate) -> SourceAssetRecord:
        if source_asset.transformation_package_id is not None:
            self.get_transformation_package(source_asset.transformation_package_id)
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
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    source_asset.created_at.isoformat(),
                ),
            )
            connection.commit()
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
                    created_at
                FROM source_assets
                WHERE source_asset_id = ?
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_source_assets(self) -> list[SourceAssetRecord]:
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
                    created_at
                FROM source_assets
                ORDER BY created_at, source_asset_id
                """
            ).fetchall()

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
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

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
                    created_at
                FROM source_assets
                WHERE source_system_id = ?
                  AND dataset_contract_id = ?
                  AND column_mapping_id = ?
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def create_ingestion_definition(
        self,
        ingestion_definition: IngestionDefinitionCreate,
    ) -> IngestionDefinitionRecord:
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
                    source_name,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ingestion_definition.source_name,
                    ingestion_definition.created_at.isoformat(),
                ),
            )
            connection.commit()
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
                    source_name,
                    created_at
                FROM ingestion_definitions
                WHERE ingestion_definition_id = ?
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
            source_name=row["source_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_ingestion_definitions(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[IngestionDefinitionRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            if enabled_only:
                rows = connection.execute(
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
                        source_name,
                        created_at
                    FROM ingestion_definitions
                    WHERE enabled = 1
                    ORDER BY created_at, ingestion_definition_id
                    """
                ).fetchall()
            else:
                rows = connection.execute(
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
                        source_name,
                        created_at
                    FROM ingestion_definitions
                    ORDER BY created_at, ingestion_definition_id
                    """
                ).fetchall()

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
                source_name=row["source_name"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

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
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dataset_contracts (
                    dataset_contract_id TEXT PRIMARY KEY,
                    dataset_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    allow_extra_columns INTEGER NOT NULL,
                    columns_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS column_mappings (
                    column_mapping_id TEXT PRIMARY KEY,
                    source_system_id TEXT NOT NULL,
                    dataset_contract_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
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
                    source_name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_asset_id) REFERENCES source_assets (source_asset_id)
                );
                """
            )
            self._ensure_source_asset_columns(connection)
            self._ensure_ingestion_definition_columns(connection)
            self._seed_builtin_transformation_packages(connection)
            connection.commit()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)

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

    def _ensure_source_asset_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(source_assets)").fetchall()
        }
        if "transformation_package_id" in columns:
            return
        connection.execute(
            "ALTER TABLE source_assets ADD COLUMN transformation_package_id TEXT"
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


def resolve_dataset_contract(
    dataset_contract: DatasetContractConfigRecord,
) -> DatasetContract:
    return DatasetContract(
        dataset_name=dataset_contract.dataset_name,
        columns=tuple(
            ColumnContract(
                name=column.name,
                type=column.type,
                required=column.required,
            )
            for column in dataset_contract.columns
        ),
        allow_extra_columns=dataset_contract.allow_extra_columns,
    )


def _deserialize_columns(value: str) -> tuple[DatasetColumnConfig, ...]:
    return tuple(
        DatasetColumnConfig(
            name=column["name"],
            type=ColumnType(column["type"]),
            required=column["required"],
        )
        for column in json.loads(value)
    )


def _deserialize_rules(value: str) -> tuple[ColumnMappingRule, ...]:
    return tuple(
        ColumnMappingRule(
            target_column=rule["target_column"],
            source_column=rule.get("source_column"),
            default_value=rule.get("default_value"),
        )
        for rule in json.loads(value)
    )


def _serialize_request_headers(headers: tuple[RequestHeaderSecretRef, ...]) -> str:
    return json.dumps(
        [
            {
                "name": header.name,
                "secret_name": header.secret_name,
                "secret_key": header.secret_key,
            }
            for header in headers
        ]
    )


def _deserialize_request_headers(value: str | None) -> tuple[RequestHeaderSecretRef, ...]:
    if not value:
        return ()
    return tuple(
        RequestHeaderSecretRef(
            name=header["name"],
            secret_name=header["secret_name"],
            secret_key=header["secret_key"],
        )
        for header in json.loads(value)
    )


def _validate_mapping_rules(rules: tuple[ColumnMappingRule, ...]) -> None:
    seen_targets: set[str] = set()

    for rule in rules:
        if rule.target_column in seen_targets:
            raise ValueError(
                f"Duplicate mapping rule for target column: {rule.target_column}"
            )
        if rule.source_column is None and rule.default_value is None:
            raise ValueError(
                f"Mapping rule must define source_column or default_value for target column: {rule.target_column}"
            )
        seen_targets.add(rule.target_column)


_BUILTIN_TRANSFORMATION_PACKAGES = (
    TransformationPackageCreate(
        transformation_package_id="builtin_account_transactions",
        name="Built-in account transactions",
        handler_key="account_transactions",
        version=1,
        description="Canonical account transaction transformation and reporting flow.",
    ),
    TransformationPackageCreate(
        transformation_package_id="builtin_subscriptions",
        name="Built-in subscriptions",
        handler_key="subscriptions",
        version=1,
        description="Recurring subscription transformation and summary publications.",
    ),
    TransformationPackageCreate(
        transformation_package_id="builtin_contract_prices",
        name="Built-in contract prices",
        handler_key="contract_prices",
        version=1,
        description="Contract pricing and electricity tariff transformation and publications.",
    ),
    TransformationPackageCreate(
        transformation_package_id="builtin_utility_usage",
        name="Built-in utility usage",
        handler_key="utility_usage",
        version=1,
        description="Utility usage transformation and reporting publications.",
    ),
    TransformationPackageCreate(
        transformation_package_id="builtin_utility_bills",
        name="Built-in utility bills",
        handler_key="utility_bills",
        version=1,
        description="Utility bill transformation and reporting publications.",
    ),
)


_BUILTIN_PUBLICATION_DEFINITIONS = (
    PublicationDefinitionCreate(
        publication_definition_id="pub_account_transactions_monthly_cashflow",
        transformation_package_id="builtin_account_transactions",
        publication_key="mart_monthly_cashflow",
        name="Monthly cashflow mart",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_account_transactions_counterparty_cashflow",
        transformation_package_id="builtin_account_transactions",
        publication_key="mart_monthly_cashflow_by_counterparty",
        name="Monthly cashflow by counterparty mart",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_account_transactions_current_accounts",
        transformation_package_id="builtin_account_transactions",
        publication_key="rpt_current_dim_account",
        name="Current account view",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_account_transactions_current_counterparties",
        transformation_package_id="builtin_account_transactions",
        publication_key="rpt_current_dim_counterparty",
        name="Current counterparty view",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_subscriptions_summary",
        transformation_package_id="builtin_subscriptions",
        publication_key="mart_subscription_summary",
        name="Subscription summary mart",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_subscriptions_current_contracts",
        transformation_package_id="builtin_subscriptions",
        publication_key="rpt_current_dim_contract",
        name="Current contract view",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_contract_prices_current",
        transformation_package_id="builtin_contract_prices",
        publication_key="mart_contract_price_current",
        name="Current contract price mart",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_contract_prices_electricity_current",
        transformation_package_id="builtin_contract_prices",
        publication_key="mart_electricity_price_current",
        name="Current electricity price mart",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_contract_prices_current_contracts",
        transformation_package_id="builtin_contract_prices",
        publication_key="rpt_current_dim_contract",
        name="Current contract view",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_utility_usage_summary",
        transformation_package_id="builtin_utility_usage",
        publication_key="mart_utility_cost_summary",
        name="Utility cost summary mart",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_utility_usage_current_meters",
        transformation_package_id="builtin_utility_usage",
        publication_key="rpt_current_dim_meter",
        name="Current meter view",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_utility_bills_summary",
        transformation_package_id="builtin_utility_bills",
        publication_key="mart_utility_cost_summary",
        name="Utility cost summary mart",
    ),
    PublicationDefinitionCreate(
        publication_definition_id="pub_utility_bills_current_meters",
        transformation_package_id="builtin_utility_bills",
        publication_key="rpt_current_dim_meter",
        name="Current meter view",
    ),
)


def allowed_publication_keys(
    *,
    extension_registry: ExtensionRegistry | None = None,
) -> set[str]:
    from packages.pipelines.reporting_service import PUBLICATION_RELATIONS

    allowed_keys = set(PUBLICATION_RELATIONS)
    if extension_registry is not None:
        allowed_keys.update(
            publication.relation_name
            for publication in extension_registry.list_reporting_publications()
        )
    return allowed_keys


def validate_publication_key(
    publication_key: str,
    *,
    extension_registry: ExtensionRegistry | None = None,
) -> None:
    if publication_key in allowed_publication_keys(
        extension_registry=extension_registry
    ):
        return

    raise ValueError(
        "Unknown publication key. Register a published reporting relation or use an existing built-in publication key: "
        f"{publication_key!r}"
    )
