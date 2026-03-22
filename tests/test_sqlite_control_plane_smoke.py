"""SQLite control-plane coverage is local/dev smoke, not parity with Postgres."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from packages.storage.ingestion_config import IngestionConfigRepository
from tests.control_plane_test_support import FIXED_DUE_AT, seed_source_asset_graph


def test_sqlite_control_plane_bootstrap_supports_catalog_and_dispatch_smoke() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seeded = seed_source_asset_graph(repository)

        dispatches = repository.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)

        assert len(dispatches) == 1
        assert dispatches[0].schedule_id == "bank_partner_poll"
        assert (
            repository.get_source_system(seeded["source_system"].source_system_id).name
            == "Bank Partner Export"
        )


def test_sqlite_control_plane_snapshot_portability_smoke() -> None:
    with TemporaryDirectory() as temp_dir:
        source_repository = IngestionConfigRepository(Path(temp_dir) / "source.db")
        seeded = seed_source_asset_graph(source_repository)
        snapshot = source_repository.export_snapshot()

        target_repository = IngestionConfigRepository(Path(temp_dir) / "target.db")
        target_repository.import_snapshot(snapshot)

        assert (
            target_repository.get_source_asset(
                seeded["source_asset"].source_asset_id
            ).source_asset_id
            == seeded["source_asset"].source_asset_id
        )
        assert [record.lineage_id for record in target_repository.list_source_lineage()] == [
            "lineage-001"
        ]
