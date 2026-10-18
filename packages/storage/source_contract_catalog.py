"""Dialect-neutral source-contract catalog.

Covers source systems, dataset contracts, column mappings, transformation packages,
and publication definitions. ``SQLiteSourceContractCatalogMixin`` and
``PostgresSourceContractCatalogMixin`` only bind a ``_session()`` dialect hook.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import asdict
from typing import TYPE_CHECKING

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
from packages.storage.sql_dialect import (
    DialectSession,
    row_datetime,
    row_int,
    row_optional_str,
)

SOURCE_SYSTEM_COLUMNS = (
    "source_system_id, name, source_type, transport, schedule_mode, description,"
    " enabled, created_at"
)
DATASET_CONTRACT_COLUMNS = (
    "dataset_contract_id, dataset_name, version, allow_extra_columns, archived,"
    " columns_json, created_at"
)
COLUMN_MAPPING_COLUMNS = (
    "column_mapping_id, source_system_id, dataset_contract_id, version, archived,"
    " rules_json, created_at"
)
TRANSFORMATION_PACKAGE_COLUMNS = (
    "transformation_package_id, name, handler_key, version, description, archived,"
    " created_at"
)
PUBLICATION_DEFINITION_COLUMNS = (
    "publication_definition_id, transformation_package_id, publication_key, name,"
    " description, archived, created_at"
)


def deserialize_source_system_row(row: Mapping[str, object]) -> SourceSystemRecord:
    return SourceSystemRecord(
        source_system_id=str(row["source_system_id"]),
        name=str(row["name"]),
        source_type=str(row["source_type"]),
        transport=str(row["transport"]),
        schedule_mode=str(row["schedule_mode"]),
        description=row_optional_str(row["description"]),
        enabled=bool(row["enabled"]),
        created_at=row_datetime(row["created_at"]),
    )


def deserialize_dataset_contract_row(
    row: Mapping[str, object],
) -> DatasetContractConfigRecord:
    return DatasetContractConfigRecord(
        dataset_contract_id=str(row["dataset_contract_id"]),
        dataset_name=str(row["dataset_name"]),
        version=row_int(row["version"]),
        allow_extra_columns=bool(row["allow_extra_columns"]),
        columns=_deserialize_columns(str(row["columns_json"])),
        archived=bool(row["archived"]),
        created_at=row_datetime(row["created_at"]),
    )


def deserialize_column_mapping_row(row: Mapping[str, object]) -> ColumnMappingRecord:
    return ColumnMappingRecord(
        column_mapping_id=str(row["column_mapping_id"]),
        source_system_id=str(row["source_system_id"]),
        dataset_contract_id=str(row["dataset_contract_id"]),
        version=row_int(row["version"]),
        rules=_deserialize_rules(str(row["rules_json"])),
        archived=bool(row["archived"]),
        created_at=row_datetime(row["created_at"]),
    )


def deserialize_transformation_package_row(
    row: Mapping[str, object],
) -> TransformationPackageRecord:
    return TransformationPackageRecord(
        transformation_package_id=str(row["transformation_package_id"]),
        name=str(row["name"]),
        handler_key=str(row["handler_key"]),
        version=row_int(row["version"]),
        description=row_optional_str(row["description"]),
        archived=bool(row["archived"]),
        created_at=row_datetime(row["created_at"]),
    )


def deserialize_publication_definition_row(
    row: Mapping[str, object],
) -> PublicationDefinitionRecord:
    return PublicationDefinitionRecord(
        publication_definition_id=str(row["publication_definition_id"]),
        transformation_package_id=str(row["transformation_package_id"]),
        publication_key=str(row["publication_key"]),
        name=str(row["name"]),
        description=row_optional_str(row["description"]),
        archived=bool(row["archived"]),
        created_at=row_datetime(row["created_at"]),
    )


def _select_sql(
    columns: str,
    table: str,
    *,
    conditions: list[str],
    order_by: str,
) -> str:
    sql = f"SELECT {columns} FROM {table}"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    return sql + f" ORDER BY {order_by}"


class SourceContractCatalogMixin:
    if TYPE_CHECKING:
        # Supplied by the dialect binding (SQLiteSessionMixin / PostgresSessionMixin);
        # declared for type checking only so it never shadows the binding in the MRO.
        def _session(
            self, *, write_lock: bool = False
        ) -> AbstractContextManager[DialectSession]: ...

    # -- shared statement helpers -----------------------------------------

    def _fetch_one(self, sql: str, params: tuple[object, ...]) -> Mapping[str, object] | None:
        with self._session() as session:
            return session.fetchone(sql, params)

    def _fetch_all(
        self, sql: str, params: tuple[object, ...] = ()
    ) -> list[Mapping[str, object]]:
        with self._session() as session:
            return session.fetchall(sql, params)

    def _set_archived(self, table: str, id_column: str, record_id: str, archived: bool) -> int:
        with self._session() as session:
            return session.execute(
                f"UPDATE {table} SET archived = ? WHERE {id_column} = ?",
                (session.dialect.encode_bool(archived), record_id),
            )

    # -- dependency checks ------------------------------------------------

    def _list_active_source_asset_ids_for_transformation_package(
        self,
        transformation_package_id: str,
    ) -> list[str]:
        rows = self._fetch_all(
            _select_sql(
                "source_asset_id",
                "source_assets",
                conditions=["transformation_package_id = ?", "archived = FALSE"],
                order_by="source_asset_id",
            ),
            (transformation_package_id,),
        )
        return [str(row["source_asset_id"]) for row in rows]

    def _list_active_publication_definition_ids_for_transformation_package(
        self,
        transformation_package_id: str,
    ) -> list[str]:
        rows = self._fetch_all(
            _select_sql(
                "publication_definition_id",
                "publication_definitions",
                conditions=["transformation_package_id = ?", "archived = FALSE"],
                order_by="publication_definition_id",
            ),
            (transformation_package_id,),
        )
        return [str(row["publication_definition_id"]) for row in rows]

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

    # -- source systems ---------------------------------------------------

    def create_source_system(self, source_system: SourceSystemCreate) -> SourceSystemRecord:
        with self._session() as session:
            dialect = session.dialect
            session.execute(
                f"""
                INSERT INTO source_systems ({SOURCE_SYSTEM_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_system.source_system_id,
                    source_system.name,
                    source_system.source_type,
                    source_system.transport,
                    source_system.schedule_mode,
                    source_system.description,
                    dialect.encode_bool(source_system.enabled),
                    dialect.encode_datetime(source_system.created_at),
                ),
            )
        return self.get_source_system(source_system.source_system_id)

    def update_source_system(self, source_system: SourceSystemCreate) -> SourceSystemRecord:
        with self._session() as session:
            rowcount = session.execute(
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
                    session.dialect.encode_bool(source_system.enabled),
                    source_system.source_system_id,
                ),
            )
        if rowcount == 0:
            raise KeyError(f"Unknown source system: {source_system.source_system_id}")
        return self.get_source_system(source_system.source_system_id)

    def get_source_system(self, source_system_id: str) -> SourceSystemRecord:
        row = self._fetch_one(
            f"SELECT {SOURCE_SYSTEM_COLUMNS} FROM source_systems WHERE source_system_id = ?",
            (source_system_id,),
        )
        if row is None:
            raise KeyError(f"Unknown source system: {source_system_id}")
        return deserialize_source_system_row(row)

    def list_source_systems(self) -> list[SourceSystemRecord]:
        rows = self._fetch_all(
            _select_sql(
                SOURCE_SYSTEM_COLUMNS,
                "source_systems",
                conditions=[],
                order_by="created_at, source_system_id",
            )
        )
        return [deserialize_source_system_row(row) for row in rows]

    # -- dataset contracts ------------------------------------------------

    def create_dataset_contract(
        self,
        dataset_contract: DatasetContractConfigCreate,
    ) -> DatasetContractConfigRecord:
        with self._session() as session:
            dialect = session.dialect
            session.execute(
                f"""
                INSERT INTO dataset_contracts ({DATASET_CONTRACT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_contract.dataset_contract_id,
                    dataset_contract.dataset_name,
                    dataset_contract.version,
                    dialect.encode_bool(dataset_contract.allow_extra_columns),
                    dialect.encode_bool(dataset_contract.archived),
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
                    dialect.encode_datetime(dataset_contract.created_at),
                ),
            )
        return self.get_dataset_contract(dataset_contract.dataset_contract_id)

    def get_dataset_contract(self, dataset_contract_id: str) -> DatasetContractConfigRecord:
        row = self._fetch_one(
            f"SELECT {DATASET_CONTRACT_COLUMNS} FROM dataset_contracts"
            " WHERE dataset_contract_id = ?",
            (dataset_contract_id,),
        )
        if row is None:
            raise KeyError(f"Unknown dataset contract: {dataset_contract_id}")
        return deserialize_dataset_contract_row(row)

    def list_dataset_contracts(
        self,
        *,
        include_archived: bool = False,
    ) -> list[DatasetContractConfigRecord]:
        rows = self._fetch_all(
            _select_sql(
                DATASET_CONTRACT_COLUMNS,
                "dataset_contracts",
                conditions=[] if include_archived else ["archived = FALSE"],
                order_by="created_at, dataset_contract_id",
            )
        )
        return [deserialize_dataset_contract_row(row) for row in rows]

    def set_dataset_contract_archived_state(
        self,
        dataset_contract_id: str,
        *,
        archived: bool,
    ) -> DatasetContractConfigRecord:
        if self._set_archived(
            "dataset_contracts", "dataset_contract_id", dataset_contract_id, archived
        ) == 0:
            raise KeyError(f"Unknown dataset contract: {dataset_contract_id}")
        return self.get_dataset_contract(dataset_contract_id)

    # -- column mappings --------------------------------------------------

    def create_column_mapping(self, column_mapping: ColumnMappingCreate) -> ColumnMappingRecord:
        _validate_mapping_rules(column_mapping.rules)
        with self._session() as session:
            dialect = session.dialect
            session.execute(
                f"""
                INSERT INTO column_mappings ({COLUMN_MAPPING_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    column_mapping.column_mapping_id,
                    column_mapping.source_system_id,
                    column_mapping.dataset_contract_id,
                    column_mapping.version,
                    dialect.encode_bool(column_mapping.archived),
                    json.dumps([asdict(rule) for rule in column_mapping.rules]),
                    dialect.encode_datetime(column_mapping.created_at),
                ),
            )
        return self.get_column_mapping(column_mapping.column_mapping_id)

    def get_column_mapping(self, column_mapping_id: str) -> ColumnMappingRecord:
        row = self._fetch_one(
            f"SELECT {COLUMN_MAPPING_COLUMNS} FROM column_mappings WHERE column_mapping_id = ?",
            (column_mapping_id,),
        )
        if row is None:
            raise KeyError(f"Unknown column mapping: {column_mapping_id}")
        return deserialize_column_mapping_row(row)

    def list_column_mappings(
        self,
        *,
        include_archived: bool = False,
    ) -> list[ColumnMappingRecord]:
        rows = self._fetch_all(
            _select_sql(
                COLUMN_MAPPING_COLUMNS,
                "column_mappings",
                conditions=[] if include_archived else ["archived = FALSE"],
                order_by="created_at, column_mapping_id",
            )
        )
        return [deserialize_column_mapping_row(row) for row in rows]

    def set_column_mapping_archived_state(
        self,
        column_mapping_id: str,
        *,
        archived: bool,
    ) -> ColumnMappingRecord:
        if self._set_archived(
            "column_mappings", "column_mapping_id", column_mapping_id, archived
        ) == 0:
            raise KeyError(f"Unknown column mapping: {column_mapping_id}")
        return self.get_column_mapping(column_mapping_id)

    # -- transformation packages ------------------------------------------

    def _validate_transformation_package_handler(
        self,
        transformation_package: TransformationPackageCreate,
        *,
        extension_registry: ExtensionRegistry | None,
        promotion_handler_registry,
    ) -> None:
        if promotion_handler_registry is None:
            return
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

    def create_transformation_package(
        self,
        transformation_package: TransformationPackageCreate,
        *,
        extension_registry: ExtensionRegistry | None = None,
        promotion_handler_registry=None,
    ) -> TransformationPackageRecord:
        self._validate_transformation_package_handler(
            transformation_package,
            extension_registry=extension_registry,
            promotion_handler_registry=promotion_handler_registry,
        )
        with self._session() as session:
            dialect = session.dialect
            session.execute(
                f"""
                INSERT INTO transformation_packages ({TRANSFORMATION_PACKAGE_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transformation_package.transformation_package_id,
                    transformation_package.name,
                    transformation_package.handler_key,
                    transformation_package.version,
                    transformation_package.description,
                    dialect.encode_bool(transformation_package.archived),
                    dialect.encode_datetime(transformation_package.created_at),
                ),
            )
        return self.get_transformation_package(transformation_package.transformation_package_id)

    def update_transformation_package(
        self,
        transformation_package: TransformationPackageCreate,
        *,
        extension_registry: ExtensionRegistry | None = None,
        promotion_handler_registry=None,
    ) -> TransformationPackageRecord:
        self._validate_transformation_package_handler(
            transformation_package,
            extension_registry=extension_registry,
            promotion_handler_registry=promotion_handler_registry,
        )
        with self._session() as session:
            rowcount = session.execute(
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
                    session.dialect.encode_bool(transformation_package.archived),
                    transformation_package.transformation_package_id,
                ),
            )
        if rowcount == 0:
            raise KeyError(
                "Unknown transformation package: "
                f"{transformation_package.transformation_package_id}"
            )
        return self.get_transformation_package(transformation_package.transformation_package_id)

    def get_transformation_package(
        self,
        transformation_package_id: str,
    ) -> TransformationPackageRecord:
        row = self._fetch_one(
            f"SELECT {TRANSFORMATION_PACKAGE_COLUMNS} FROM transformation_packages"
            " WHERE transformation_package_id = ?",
            (transformation_package_id,),
        )
        if row is None:
            raise KeyError(f"Unknown transformation package: {transformation_package_id}")
        return deserialize_transformation_package_row(row)

    def list_transformation_packages(
        self,
        *,
        include_archived: bool = False,
    ) -> list[TransformationPackageRecord]:
        rows = self._fetch_all(
            _select_sql(
                TRANSFORMATION_PACKAGE_COLUMNS,
                "transformation_packages",
                conditions=[] if include_archived else ["archived = FALSE"],
                order_by="created_at, transformation_package_id",
            )
        )
        return [deserialize_transformation_package_row(row) for row in rows]

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
        if self._set_archived(
            "transformation_packages",
            "transformation_package_id",
            transformation_package_id,
            archived,
        ) == 0:
            raise KeyError(f"Unknown transformation package: {transformation_package_id}")
        return self.get_transformation_package(transformation_package_id)

    # -- publication definitions ------------------------------------------

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
        with self._session() as session:
            dialect = session.dialect
            session.execute(
                f"""
                INSERT INTO publication_definitions ({PUBLICATION_DEFINITION_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    publication_definition.publication_definition_id,
                    publication_definition.transformation_package_id,
                    publication_definition.publication_key,
                    publication_definition.name,
                    publication_definition.description,
                    dialect.encode_bool(publication_definition.archived),
                    dialect.encode_datetime(publication_definition.created_at),
                ),
            )
        return self.get_publication_definition(publication_definition.publication_definition_id)

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
        with self._session() as session:
            rowcount = session.execute(
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
                    session.dialect.encode_bool(publication_definition.archived),
                    publication_definition.publication_definition_id,
                ),
            )
        if rowcount == 0:
            raise KeyError(
                "Unknown publication definition: "
                f"{publication_definition.publication_definition_id}"
            )
        return self.get_publication_definition(publication_definition.publication_definition_id)

    def get_publication_definition(
        self,
        publication_definition_id: str,
    ) -> PublicationDefinitionRecord:
        row = self._fetch_one(
            f"SELECT {PUBLICATION_DEFINITION_COLUMNS} FROM publication_definitions"
            " WHERE publication_definition_id = ?",
            (publication_definition_id,),
        )
        if row is None:
            raise KeyError(f"Unknown publication definition: {publication_definition_id}")
        return deserialize_publication_definition_row(row)

    def list_publication_definitions(
        self,
        *,
        transformation_package_id: str | None = None,
        include_archived: bool = False,
    ) -> list[PublicationDefinitionRecord]:
        conditions: list[str] = []
        params: tuple[object, ...] = ()
        if transformation_package_id is not None:
            conditions.append("transformation_package_id = ?")
            params += (transformation_package_id,)
        if not include_archived:
            conditions.append("archived = FALSE")
        rows = self._fetch_all(
            _select_sql(
                PUBLICATION_DEFINITION_COLUMNS,
                "publication_definitions",
                conditions=conditions,
                order_by="created_at, publication_definition_id",
            ),
            params,
        )
        return [deserialize_publication_definition_row(row) for row in rows]

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
        if self._set_archived(
            "publication_definitions",
            "publication_definition_id",
            publication_definition_id,
            archived,
        ) == 0:
            raise KeyError(f"Unknown publication definition: {publication_definition_id}")
        return self.get_publication_definition(publication_definition_id)
