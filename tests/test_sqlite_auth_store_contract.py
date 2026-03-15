from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from packages.storage.ingestion_config import IngestionConfigRepository
from tests.auth_test_support import assert_auth_store_round_trip


def test_sqlite_auth_store_round_trips_local_users() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

        assert_auth_store_round_trip(repository)
