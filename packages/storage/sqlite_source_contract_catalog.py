from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime

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
    validate_publication_support,
    validate_transformation_handler_key,
)


def _deserialize_source_system_row(row: sqlite3.Row) -> SourceSystemRecord:
    return SourceSystemRecord(
        source_system_id=row["source_system_id"],
        name=row["name"],
        source_type=row["source_type"],
        transport=row["transport"],
        schedule_mode=row["schedule_mode"],
        description=row["description"],
        enabled=bool(row["enabled"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _deserialize_transformation_package_row(
    row: sqlite3.Row,
) -> TransformationPackageRecord:
    return TransformationPackageRecord(
        transformation_package_id=row["transformation_package_id"],
        name=row["name"],
        handler_key=row["handler_key"],
        version=row["version"],
        description=row["description"],
        archived=bool(row["archived"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _deserialize_publication_definition_row(
    row: sqlite3.Row,
) -> PublicationDefinitionRecord:
    return PublicationDefinitionRecord(
        publication_definition_id=row["publication_definition_id"],
        transformation_package_id=row["transformation_package_id"],
        publication_key=row["publication_key"],
        name=row["name"],
        description=row["description"],
        archived=bool(row["archived"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class SQLiteSourceContractCatalogMixin:
    def _connect(self) -> sqlite3.Connection:
        raise NotImplementedError

    def _list_active_source_asset_ids_for_transformation_package(
        self,
        transformation_package_id: str,
    ) -> list[str]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT source_asset_id
                FROM source_assets
                WHERE transformation_package_id = ?
                  AND archived = 0
                ORDER BY source_asset_id
                """,
                (transformation_package_id,),
            ).fetchall()
        return [row["source_asset_id"] for row in rows]

    def _list_active_publication_definition_ids_for_transformation_package(
        self,
        transformation_package_id: str,
    ) -> list[str]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT publication_definition_id
                FROM publication_definitions
                WHERE transformation_package_id = ?
                  AND archived = 0
                ORDER BY publication_definition_id
                """,
                (transformation_package_id,),
            ).fetchall()
        return [row["publication_definition_id"] for row in rows]

    def _validate_publication_definition_dependencies(
        self,
        publication_definition: PublicationDefinitionCreate,
        *,
        extension_registry: ExtensionRegistry | None = None,
        promotion_handler_registry=None,
    ) -> None:
        validate_publication_key(
            publication_definition.publication_key,
            extension_registry=extension_registry,
        )
        transformation_package = self.get_transformation_package(
            publication_definition.transformation_package_id
        )
        if transformation_package.archived:
            raise ValueError(
                "Transformation package is archived: "
                f"{publication_definition.transformation_package_id}"
            )
        if promotion_handler_registry is not None:
            validate_publication_support(
                publication_definition.publication_key,
                handler_key=transformation_package.handler_key,
                transformation_package_id=transformation_package.transformation_package_id,
                extension_registry=extension_registry,
                promotion_handler_registry=promotion_handler_registry,
            )

    def _validate_existing_publication_support_for_transformation_package(
        self,
        transformation_package_id: str,
        *,
        handler_key: str,
        extension_registry: ExtensionRegistry | None = None,
        promotion_handler_registry=None,
    ) -> None:
        if promotion_handler_registry is None:
            return
        for publication_definition in self.list_publication_definitions(
            transformation_package_id=transformation_package_id,
        ):
            validate_publication_support(
                publication_definition.publication_key,
                handler_key=handler_key,
                transformation_package_id=transformation_package_id,
                extension_registry=extension_registry,
                promotion_handler_registry=promotion_handler_registry,
            )

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
                    enabled,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_system.source_system_id,
                    source_system.name,
                    source_system.source_type,
                    source_system.transport,
                    source_system.schedule_mode,
                    source_system.description,
                    int(source_system.enabled),
                    source_system.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_source_system(source_system.source_system_id)

    def update_source_system(
        self,
        source_system: SourceSystemCreate,
    ) -> SourceSystemRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_systems
                SET name = ?,
                    source_type = ?,
                    transport = ?,
                    schedule_mode = ?,
                    description = ?,
                    enabled = ?
                WHERE source_system_id = ?
                """,
                (
                    source_system.name,
                    source_system.source_type,
                    source_system.transport,
                    source_system.schedule_mode,
                    source_system.description,
                    int(source_system.enabled),
                    source_system.source_system_id,
                ),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source system: {source_system.source_system_id}")
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
                    enabled,
                    created_at
                FROM source_systems
                WHERE source_system_id = ?
                """,
                (source_system_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown source system: {source_system_id}")
        return _deserialize_source_system_row(row)

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
                    enabled,
                    created_at
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
                    dataset_contract_id,
                    dataset_name,
                    version,
                    allow_extra_columns,
                    archived,
                    columns_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_contract.dataset_contract_id,
                    dataset_contract.dataset_name,
                    dataset_contract.version,
                    int(dataset_contract.allow_extra_columns),
                    int(dataset_contract.archived),
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
                    archived,
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
            archived=bool(row["archived"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_dataset_contracts(
        self,
        *,
        include_archived: bool = False,
    ) -> list[DatasetContractConfigRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            sql = """
                SELECT
                    dataset_contract_id,
                    dataset_name,
                    version,
                    allow_extra_columns,
                    archived,
                    columns_json,
                    created_at
                FROM dataset_contracts
            """
            if not include_archived:
                sql += " WHERE archived = 0"
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
                created_at=datetime.fromisoformat(row["created_at"]),
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
                SET archived = ?
                WHERE dataset_contract_id = ?
                """,
                (int(archived), dataset_contract_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown dataset contract: {dataset_contract_id}")
        return self.get_dataset_contract(dataset_contract_id)

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
                    archived,
                    rules_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    column_mapping.column_mapping_id,
                    column_mapping.source_system_id,
                    column_mapping.dataset_contract_id,
                    column_mapping.version,
                    int(column_mapping.archived),
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
                    archived,
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
            archived=bool(row["archived"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_column_mappings(
        self,
        *,
        include_archived: bool = False,
    ) -> list[ColumnMappingRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            sql = """
                SELECT
                    column_mapping_id,
                    source_system_id,
                    dataset_contract_id,
                    version,
                    archived,
                    rules_json,
                    created_at
                FROM column_mappings
            """
            if not include_archived:
                sql += " WHERE archived = 0"
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
                created_at=datetime.fromisoformat(row["created_at"]),
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
                SET archived = ?
                WHERE column_mapping_id = ?
                """,
                (int(archived), column_mapping_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown column mapping: {column_mapping_id}")
        return self.get_column_mapping(column_mapping_id)

    def create_transformation_package(
        self,
        transformation_package: TransformationPackageCreate,
        *,
        extension_registry: ExtensionRegistry | None = None,
        promotion_handler_registry=None,
    ) -> TransformationPackageRecord:
        if promotion_handler_registry is not None:
            validate_transformation_handler_key(
                transformation_package.handler_key,
                promotion_handler_registry=promotion_handler_registry,
            )
            self._validate_existing_publication_support_for_transformation_package(
                transformation_package.transformation_package_id,
                handler_key=transformation_package.handler_key,
                extension_registry=extension_registry,
                promotion_handler_registry=promotion_handler_registry,
            )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO transformation_packages (
                    transformation_package_id,
                    name,
                    handler_key,
                    version,
                    description,
                    archived,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transformation_package.transformation_package_id,
                    transformation_package.name,
                    transformation_package.handler_key,
                    transformation_package.version,
                    transformation_package.description,
                    int(transformation_package.archived),
                    transformation_package.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_transformation_package(
            transformation_package.transformation_package_id
        )

    def update_transformation_package(
        self,
        transformation_package: TransformationPackageCreate,
        *,
        extension_registry: ExtensionRegistry | None = None,
        promotion_handler_registry=None,
    ) -> TransformationPackageRecord:
        if promotion_handler_registry is not None:
            validate_transformation_handler_key(
                transformation_package.handler_key,
                promotion_handler_registry=promotion_handler_registry,
            )
            self._validate_existing_publication_support_for_transformation_package(
                transformation_package.transformation_package_id,
                handler_key=transformation_package.handler_key,
                extension_registry=extension_registry,
                promotion_handler_registry=promotion_handler_registry,
            )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE transformation_packages
                SET name = ?,
                    handler_key = ?,
                    version = ?,
                    description = ?,
                    archived = ?
                WHERE transformation_package_id = ?
                """,
                (
                    transformation_package.name,
                    transformation_package.handler_key,
                    transformation_package.version,
                    transformation_package.description,
                    int(transformation_package.archived),
                    transformation_package.transformation_package_id,
                ),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(
                "Unknown transformation package: "
                f"{transformation_package.transformation_package_id}"
            )
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
                    archived,
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
        return _deserialize_transformation_package_row(row)

    def list_transformation_packages(
        self,
        *,
        include_archived: bool = False,
    ) -> list[TransformationPackageRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            if include_archived:
                rows = connection.execute(
                    """
                    SELECT
                        transformation_package_id,
                        name,
                        handler_key,
                        version,
                        description,
                        archived,
                        created_at
                    FROM transformation_packages
                    ORDER BY created_at, transformation_package_id
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        transformation_package_id,
                        name,
                        handler_key,
                        version,
                        description,
                        archived,
                        created_at
                    FROM transformation_packages
                    WHERE archived = 0
                    ORDER BY created_at, transformation_package_id
                    """
                ).fetchall()

        return [_deserialize_transformation_package_row(row) for row in rows]

    def set_transformation_package_archived_state(
        self,
        transformation_package_id: str,
        *,
        archived: bool,
    ) -> TransformationPackageRecord:
        if archived:
            source_asset_ids = self._list_active_source_asset_ids_for_transformation_package(
                transformation_package_id
            )
            if source_asset_ids:
                raise ValueError(
                    "Transformation package is referenced by active source assets: "
                    + ", ".join(source_asset_ids)
                )
            publication_definition_ids = (
                self._list_active_publication_definition_ids_for_transformation_package(
                    transformation_package_id
                )
            )
            if publication_definition_ids:
                raise ValueError(
                    "Transformation package is referenced by active publication definitions: "
                    + ", ".join(publication_definition_ids)
                )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE transformation_packages
                SET archived = ?
                WHERE transformation_package_id = ?
                """,
                (int(archived), transformation_package_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown transformation package: {transformation_package_id}")
        return self.get_transformation_package(transformation_package_id)

    def create_publication_definition(
        self,
        publication_definition: PublicationDefinitionCreate,
        *,
        extension_registry: ExtensionRegistry | None = None,
        promotion_handler_registry=None,
    ) -> PublicationDefinitionRecord:
        self._validate_publication_definition_dependencies(
            publication_definition,
            extension_registry=extension_registry,
            promotion_handler_registry=promotion_handler_registry,
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
                    archived,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    publication_definition.publication_definition_id,
                    publication_definition.transformation_package_id,
                    publication_definition.publication_key,
                    publication_definition.name,
                    publication_definition.description,
                    int(publication_definition.archived),
                    publication_definition.created_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_publication_definition(
            publication_definition.publication_definition_id
        )

    def update_publication_definition(
        self,
        publication_definition: PublicationDefinitionCreate,
        *,
        extension_registry: ExtensionRegistry | None = None,
        promotion_handler_registry=None,
    ) -> PublicationDefinitionRecord:
        self._validate_publication_definition_dependencies(
            publication_definition,
            extension_registry=extension_registry,
            promotion_handler_registry=promotion_handler_registry,
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE publication_definitions
                SET transformation_package_id = ?,
                    publication_key = ?,
                    name = ?,
                    description = ?,
                    archived = ?
                WHERE publication_definition_id = ?
                """,
                (
                    publication_definition.transformation_package_id,
                    publication_definition.publication_key,
                    publication_definition.name,
                    publication_definition.description,
                    int(publication_definition.archived),
                    publication_definition.publication_definition_id,
                ),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(
                "Unknown publication definition: "
                f"{publication_definition.publication_definition_id}"
            )
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
                    archived,
                    created_at
                FROM publication_definitions
                WHERE publication_definition_id = ?
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
        include_archived: bool = False,
    ) -> list[PublicationDefinitionRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            if transformation_package_id is None:
                if include_archived:
                    rows = connection.execute(
                        """
                        SELECT
                            publication_definition_id,
                            transformation_package_id,
                            publication_key,
                            name,
                            description,
                            archived,
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
                            archived,
                            created_at
                        FROM publication_definitions
                        WHERE archived = 0
                        ORDER BY created_at, publication_definition_id
                        """
                    ).fetchall()
            else:
                if include_archived:
                    rows = connection.execute(
                        """
                        SELECT
                            publication_definition_id,
                            transformation_package_id,
                            publication_key,
                            name,
                            description,
                            archived,
                            created_at
                        FROM publication_definitions
                        WHERE transformation_package_id = ?
                        ORDER BY created_at, publication_definition_id
                        """,
                        (transformation_package_id,),
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
                            archived,
                            created_at
                        FROM publication_definitions
                        WHERE transformation_package_id = ?
                          AND archived = 0
                        ORDER BY created_at, publication_definition_id
                        """,
                        (transformation_package_id,),
                    ).fetchall()

        return [_deserialize_publication_definition_row(row) for row in rows]

    def set_publication_definition_archived_state(
        self,
        publication_definition_id: str,
        *,
        archived: bool,
    ) -> PublicationDefinitionRecord:
        if not archived:
            publication_definition = self.get_publication_definition(
                publication_definition_id
            )
            transformation_package = self.get_transformation_package(
                publication_definition.transformation_package_id
            )
            if transformation_package.archived:
                raise ValueError(
                    "Transformation package is archived: "
                    f"{publication_definition.transformation_package_id}"
                )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE publication_definitions
                SET archived = ?
                WHERE publication_definition_id = ?
                """,
                (int(archived), publication_definition_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown publication definition: {publication_definition_id}")
        return self.get_publication_definition(publication_definition_id)
