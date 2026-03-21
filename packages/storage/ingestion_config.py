from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import cast

from packages.storage.control_plane import (
    ControlPlaneSnapshot,
    ControlPlaneStore,
)
from packages.storage.control_plane_snapshot import (
    export_control_plane_snapshot,
    import_control_plane_snapshot,
)
from packages.storage.external_registry_catalog import (
    ExtensionRegistryActivationRecord,
    ExtensionRegistryRevisionCreate,
    ExtensionRegistryRevisionRecord,
    ExtensionRegistrySourceCreate,
    ExtensionRegistrySourceRecord,
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
    allowed_transformation_handler_keys,
    resolve_dataset_contract,
    validate_publication_key,
    validate_publication_support,
    validate_transformation_handler_key,
)
from packages.storage.sqlite_asset_definition_catalog import (
    SQLiteAssetDefinitionCatalogMixin,
)
from packages.storage.sqlite_auth_control_plane import SQLiteAuthControlPlaneMixin
from packages.storage.sqlite_control_plane_schema import (
    initialize_sqlite_control_plane_schema,
)
from packages.storage.sqlite_execution_control_plane import (
    SQLiteExecutionControlPlaneMixin,
)
from packages.storage.sqlite_external_registry_catalog import (
    SQLiteExternalRegistryCatalogMixin,
)
from packages.storage.sqlite_provenance_control_plane import (
    SQLiteProvenanceControlPlaneMixin,
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
    "ExtensionRegistryActivationRecord",
    "ExtensionRegistryRevisionCreate",
    "ExtensionRegistryRevisionRecord",
    "ExtensionRegistrySourceCreate",
    "ExtensionRegistrySourceRecord",
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
    "allowed_transformation_handler_keys",
    "resolve_dataset_contract",
    "validate_publication_support",
    "validate_publication_key",
    "validate_transformation_handler_key",
    "_BUILTIN_PUBLICATION_DEFINITIONS",
    "_BUILTIN_TRANSFORMATION_PACKAGES",
]


class IngestionConfigRepository(
    SQLiteSourceContractCatalogMixin,
    SQLiteAssetDefinitionCatalogMixin,
    SQLiteExternalRegistryCatalogMixin,
    SQLiteExecutionControlPlaneMixin,
    SQLiteProvenanceControlPlaneMixin,
    SQLiteAuthControlPlaneMixin,
):
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def export_snapshot(self) -> ControlPlaneSnapshot:
        return export_control_plane_snapshot(
            cast(ControlPlaneStore, self),
        )

    def import_snapshot(self, snapshot: ControlPlaneSnapshot) -> None:
        import_control_plane_snapshot(
            cast(ControlPlaneStore, self),
            snapshot,
            duplicate_exceptions=(sqlite3.IntegrityError,),
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            initialize_sqlite_control_plane_schema(connection)
            connection.commit()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)
