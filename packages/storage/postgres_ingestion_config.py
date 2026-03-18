from __future__ import annotations

from typing import cast

import psycopg

from packages.storage.control_plane import (
    ControlPlaneSnapshot,
    ControlPlaneStore,
)
from packages.storage.control_plane_snapshot import (
    export_control_plane_snapshot,
    import_control_plane_snapshot,
)
from packages.storage.postgres_asset_definition_catalog import (
    PostgresAssetDefinitionCatalogMixin,
)
from packages.storage.postgres_auth_control_plane import (
    PostgresAuthControlPlaneMixin,
)
from packages.storage.postgres_control_plane_schema import (
    initialize_postgres_control_plane_schema,
)
from packages.storage.postgres_execution_control_plane import (
    PostgresExecutionControlPlaneMixin,
)
from packages.storage.postgres_external_registry_catalog import (
    PostgresExternalRegistryCatalogMixin,
)
from packages.storage.postgres_provenance_control_plane import (
    PostgresProvenanceControlPlaneMixin,
)
from packages.storage.postgres_source_contract_catalog import (
    PostgresSourceContractCatalogMixin,
)
from packages.storage.postgres_support import configure_search_path, initialize_schema


class PostgresIngestionConfigRepository(
    PostgresSourceContractCatalogMixin,
    PostgresAssetDefinitionCatalogMixin,
    PostgresExternalRegistryCatalogMixin,
    PostgresExecutionControlPlaneMixin,
    PostgresProvenanceControlPlaneMixin,
    PostgresAuthControlPlaneMixin,
):
    def __init__(self, dsn: str, *, schema: str = "public") -> None:
        self.dsn = dsn
        self.schema = schema
        initialize_schema(dsn, schema)
        self._initialize()

    def _connect(self, *, row_factory=None):
        connection = psycopg.connect(self.dsn, row_factory=row_factory)
        configure_search_path(connection, self.schema)
        return connection

    def export_snapshot(self) -> ControlPlaneSnapshot:
        return export_control_plane_snapshot(
            cast(ControlPlaneStore, self),
        )

    def import_snapshot(self, snapshot: ControlPlaneSnapshot) -> None:
        import_control_plane_snapshot(
            cast(ControlPlaneStore, self),
            snapshot,
            duplicate_exceptions=(psycopg.Error,),
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            initialize_postgres_control_plane_schema(connection)
