"""Pack lifecycle control-plane storage: migrations, bootstrap and store contract."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.migration_runner import apply_pending_sqlite_migrations
from packages.storage.pack_lifecycle import PackLifecycleStore
from tests.pack_lifecycle_test_support import assert_pack_lifecycle_store_behaviour

ROOT = Path(__file__).resolve().parents[1]
SQLITE_MIGRATION = ROOT / "migrations/sqlite/0011_pack_lifecycle.sql"
POSTGRES_MIGRATION = ROOT / "migrations/postgres/0018_pack_lifecycle.sql"
TABLES = {"pack_installations", "pack_lifecycle_events"}


def _columns(sql: str) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    current: str | None = None
    for line in sql.splitlines():
        stripped = line.strip()
        match = re.match(r"CREATE TABLE IF NOT EXISTS (\w+)", stripped)
        if match:
            current = match.group(1)
            tables[current] = []
            continue
        if stripped.startswith(")"):
            current = None
            continue
        if current and stripped and not stripped.startswith("--"):
            tables[current].append(stripped.split()[0])
    return tables


def test_sqlite_migration_0011_creates_pack_lifecycle_tables_idempotently() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations"
        " (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = apply_pending_sqlite_migrations(conn, ROOT / "migrations" / "sqlite")
    assert "0011_pack_lifecycle" in applied
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert TABLES <= tables
    assert "0011_pack_lifecycle" not in apply_pending_sqlite_migrations(
        conn, ROOT / "migrations" / "sqlite"
    )


def test_postgres_migration_mirrors_sqlite_columns_without_duplicates() -> None:
    sqlite_columns = _columns(SQLITE_MIGRATION.read_text())
    postgres_columns = _columns(POSTGRES_MIGRATION.read_text())
    assert set(sqlite_columns) == TABLES
    assert sqlite_columns == postgres_columns
    for columns in sqlite_columns.values():
        assert len(columns) == len(set(columns))
    postgres_sql = POSTGRES_MIGRATION.read_text()
    assert "TIMESTAMPTZ" in postgres_sql and "ALTER TABLE" not in postgres_sql


def test_inline_sqlite_bootstrap_matches_migration(tmp_path: Path) -> None:
    repository = IngestionConfigRepository(tmp_path / "config.db")
    connection = sqlite3.connect(tmp_path / "config.db")
    migrated = sqlite3.connect(":memory:")
    migrated.executescript(SQLITE_MIGRATION.read_text())
    for table in TABLES:
        bootstrap_cols = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        migration_cols = [row[1] for row in migrated.execute(f"PRAGMA table_info({table})")]
        assert bootstrap_cols == migration_cols
    assert isinstance(repository, PackLifecycleStore)


def test_sqlite_control_plane_pack_lifecycle_smoke(tmp_path: Path) -> None:
    assert_pack_lifecycle_store_behaviour(IngestionConfigRepository(tmp_path / "config.db"))


@pytest.fixture
def postgres_store() -> Iterator[object]:
    from packages.storage.postgres_ingestion_config import PostgresIngestionConfigRepository
    from tests.postgres_test_support import running_postgres_container

    with running_postgres_container() as dsn:
        yield PostgresIngestionConfigRepository(dsn, schema="control")


@pytest.mark.integration
@pytest.mark.slow
def test_postgres_control_plane_pack_lifecycle_contract(postgres_store: object) -> None:
    assert_pack_lifecycle_store_behaviour(postgres_store)
