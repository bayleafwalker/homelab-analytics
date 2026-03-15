from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from packages.storage.ingestion_config import IngestionConfigRepository
from tests.control_plane_test_support import (
    assert_auth_audit_behaviour,
    assert_control_plane_store_round_trip,
    assert_control_plane_store_update_behaviour,
    assert_schedule_dispatch_behaviour,
    assert_schedule_dispatch_claim_is_exclusive,
    assert_schedule_dispatch_resilience_behaviour,
)


def test_sqlite_control_plane_store_round_trips_config_and_control_plane_entities() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

        assert_control_plane_store_round_trip(repository)


def test_sqlite_control_plane_store_enqueues_due_schedules_and_respects_concurrency() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

        assert_schedule_dispatch_behaviour(repository)


def test_sqlite_control_plane_store_renews_and_recovers_stale_dispatches() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

        assert_schedule_dispatch_resilience_behaviour(repository)


def test_sqlite_control_plane_store_claims_dispatches_exclusively() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

        assert_schedule_dispatch_claim_is_exclusive(repository)


def test_sqlite_control_plane_store_updates_entities_and_supports_manual_dispatch() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

        assert_control_plane_store_update_behaviour(repository)


def test_sqlite_control_plane_store_records_and_filters_auth_audit_events() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

        assert_auth_audit_behaviour(repository)
