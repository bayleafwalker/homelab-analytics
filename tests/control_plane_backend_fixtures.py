from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from packages.storage.control_plane import ControlPlaneStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.postgres_ingestion_config import PostgresIngestionConfigRepository
from tests.postgres_test_support import running_postgres_container

BACKEND_PARAMS = (
    pytest.param("sqlite", id="sqlite"),
    pytest.param(
        "postgres",
        marks=[pytest.mark.integration, pytest.mark.slow],
        id="postgres",
    ),
)


@pytest.fixture(params=BACKEND_PARAMS)
def control_plane_store(request: pytest.FixtureRequest) -> Iterator[ControlPlaneStore]:
    backend = request.param
    if backend == "sqlite":
        with TemporaryDirectory() as temp_dir:
            yield IngestionConfigRepository(Path(temp_dir) / "config.db")
        return

    with running_postgres_container() as dsn:
        yield PostgresIngestionConfigRepository(dsn, schema="control")
