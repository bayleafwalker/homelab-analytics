"""Postgres control-plane integration tests plus explicit snapshot portability contracts."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.postgres_ingestion_config import PostgresIngestionConfigRepository
from tests.control_plane_test_support import seed_source_asset_graph
from tests.postgres_test_support import running_postgres_container

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_sqlite_snapshot_imports_into_postgres_control_plane_store() -> None:
    # Snapshot portability is an intentional cross-backend contract worth preserving.
    with TemporaryDirectory() as temp_dir:
        source_repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seeded = seed_source_asset_graph(source_repository)
        snapshot = source_repository.export_snapshot()

        with running_postgres_container() as dsn:
            target_repository = PostgresIngestionConfigRepository(dsn, schema="control")
            target_repository.import_snapshot(snapshot)

            assert (
                target_repository.get_source_system(
                    seeded["source_system"].source_system_id
                ).name
                == seeded["source_system"].name
            )
            assert (
                target_repository.find_source_asset_by_binding(
                    source_system_id=seeded["source_system"].source_system_id,
                    dataset_contract_id=seeded["dataset_contract"].dataset_contract_id,
                    column_mapping_id=seeded["column_mapping"].column_mapping_id,
                ).source_asset_id
                == seeded["source_asset"].source_asset_id
            )
            assert [record.schedule_id for record in target_repository.list_execution_schedules()] == [
                "bank_partner_poll"
            ]
            assert [record.lineage_id for record in target_repository.list_source_lineage()] == [
                "lineage-001"
            ]
            assert [
                record.publication_audit_id
                for record in target_repository.list_publication_audit()
            ] == ["publication-001"]
