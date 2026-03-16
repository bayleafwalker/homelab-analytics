from __future__ import annotations

import json
from dataclasses import asdict

from psycopg.rows import dict_row

from packages.shared.extensions import ExtensionRegistry
from packages.storage.ingestion_catalog import (
    ColumnMappingCreate,
    ColumnMappingRecord,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
    PublicationDefinitionCreate,
    PublicationDefinitionRecord,
    SourceSystemCreate,
    SourceSystemRecord,
    TransformationPackageCreate,
    TransformationPackageRecord,
    _deserialize_columns,
    _deserialize_rules,
    _validate_mapping_rules,
    validate_publication_key,
)


def _deserialize_source_system_row(row: dict[str, object]) -> SourceSystemRecord:
    return SourceSystemRecord(
        source_system_id=str(row["source_system_id"]),
        name=str(row["name"]),
        source_type=str(row["source_type"]),
        transport=str(row["transport"]),
        schedule_mode=str(row["schedule_mode"]),
        description=str(row["description"]) if row["description"] is not None else None,
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],  # type: ignore[arg-type]
    )


def _deserialize_transformation_package_row(
    row: dict[str, object],
) -> TransformationPackageRecord:
    return TransformationPackageRecord(
        transformation_package_id=str(row["transformation_package_id"]),
        name=str(row["name"]),
        handler_key=str(row["handler_key"]),
        version=int(row["version"]),
        description=str(row["description"]) if row["description"] is not None else None,
        created_at=row["created_at"],  # type: ignore[arg-type]
    )


def _deserialize_publication_definition_row(
    row: dict[str, object],
) -> PublicationDefinitionRecord:
    return PublicationDefinitionRecord(
        publication_definition_id=str(row["publication_definition_id"]),
        transformation_package_id=str(row["transformation_package_id"]),
        publication_key=str(row["publication_key"]),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] is not None else None,
        created_at=row["created_at"],  # type: ignore[arg-type]
    )


class PostgresSourceContractCatalogMixin:
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
        return _deserialize_source_system_row(row)

    def list_source_systems(self) -> list[SourceSystemRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT source_system_id, name, source_type, transport, schedule_mode, description, enabled, created_at
                FROM source_systems
                ORDER BY created_at, source_system_id
                """
            ).fetchall()
        return [_deserialize_source_system_row(row) for row in rows]

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
            dataset_contract_id=str(row["dataset_contract_id"]),
            dataset_name=str(row["dataset_name"]),
            version=int(row["version"]),
            allow_extra_columns=bool(row["allow_extra_columns"]),
            columns=_deserialize_columns(str(row["columns_json"])),
            archived=bool(row["archived"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
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
                dataset_contract_id=str(row["dataset_contract_id"]),
                dataset_name=str(row["dataset_name"]),
                version=int(row["version"]),
                allow_extra_columns=bool(row["allow_extra_columns"]),
                columns=_deserialize_columns(str(row["columns_json"])),
                archived=bool(row["archived"]),
                created_at=row["created_at"],  # type: ignore[arg-type]
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
            column_mapping_id=str(row["column_mapping_id"]),
            source_system_id=str(row["source_system_id"]),
            dataset_contract_id=str(row["dataset_contract_id"]),
            version=int(row["version"]),
            rules=_deserialize_rules(str(row["rules_json"])),
            archived=bool(row["archived"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
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
                column_mapping_id=str(row["column_mapping_id"]),
                source_system_id=str(row["source_system_id"]),
                dataset_contract_id=str(row["dataset_contract_id"]),
                version=int(row["version"]),
                rules=_deserialize_rules(str(row["rules_json"])),
                archived=bool(row["archived"]),
                created_at=row["created_at"],  # type: ignore[arg-type]
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
        return _deserialize_transformation_package_row(row)

    def list_transformation_packages(self) -> list[TransformationPackageRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT transformation_package_id, name, handler_key, version, description, created_at
                FROM transformation_packages
                ORDER BY created_at, transformation_package_id
                """
            ).fetchall()
        return [_deserialize_transformation_package_row(row) for row in rows]

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
        return _deserialize_publication_definition_row(row)

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
        return [_deserialize_publication_definition_row(row) for row in rows]
