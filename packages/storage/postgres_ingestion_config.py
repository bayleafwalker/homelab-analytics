from __future__ import annotations

from pathlib import Path
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
from packages.storage.migration_runner import (
    apply_pending_postgres_migrations,
    resolve_migrations_dir,
)
from packages.storage.postgres_asset_definition_catalog import (
    PostgresAssetDefinitionCatalogMixin,
)
from packages.storage.postgres_auth_control_plane import (
    PostgresAuthControlPlaneMixin,
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
from packages.storage.postgres_support import (
    configure_search_path,
    connect_with_retry,
    initialize_schema,
)


class PostgresIngestionConfigRepository(
    PostgresSourceContractCatalogMixin,
    PostgresAssetDefinitionCatalogMixin,
    PostgresExternalRegistryCatalogMixin,
    PostgresExecutionControlPlaneMixin,
    PostgresProvenanceControlPlaneMixin,
    PostgresAuthControlPlaneMixin,
):
    """Canonical Postgres-backed control-plane repository.

    Postgres schema evolution is owned by versioned SQL migrations under
    ``migrations/postgres``.
    """

    def __init__(self, dsn: str, *, schema: str = "public") -> None:
        self.dsn = dsn
        self.schema = schema
        initialize_schema(dsn, schema)
        self._initialize()

    def _connect(self, *, row_factory=None):
        connection = connect_with_retry(self.dsn, row_factory=row_factory)
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
            apply_pending_postgres_migrations(
                connection,
                resolve_migrations_dir("postgres", anchor_file=Path(__file__)),
            )
