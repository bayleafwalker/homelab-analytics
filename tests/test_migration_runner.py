"""Tests for the versioned SQL migration runner (SQLite path, fast/no-infra)."""

from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path

from packages.storage.migration_runner import (
    _split_statements,
    apply_pending_sqlite_migrations,
)

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "sqlite"


# ---------------------------------------------------------------------------
# Unit: statement splitter
# ---------------------------------------------------------------------------


def test_split_statements_basic() -> None:
    sql = "CREATE TABLE foo (id TEXT PRIMARY KEY); CREATE TABLE bar (id TEXT PRIMARY KEY)"
    stmts = _split_statements(sql)
    assert len(stmts) == 2
    assert "foo" in stmts[0]
    assert "bar" in stmts[1]


def test_split_statements_strips_comments() -> None:
    sql = textwrap.dedent("""\
        -- this is a comment
        CREATE TABLE foo (id TEXT PRIMARY KEY)
        ;
        -- another comment
    """)
    stmts = _split_statements(sql)
    assert len(stmts) == 1
    assert "CREATE TABLE foo" in stmts[0]


def test_split_statements_empty_input() -> None:
    assert _split_statements("") == []
    assert _split_statements("   -- just comments\n") == []


# ---------------------------------------------------------------------------
# Integration: apply_pending_sqlite_migrations against an in-memory database
# ---------------------------------------------------------------------------


def _in_memory() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_first_run_applies_all_migrations(tmp_path: Path) -> None:
    sql = "CREATE TABLE test_table (id TEXT PRIMARY KEY)"
    (tmp_path / "0001_create_test.sql").write_text(sql)

    conn = _in_memory()
    applied = apply_pending_sqlite_migrations(conn, tmp_path)

    assert applied == ["0001_create_test"]
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "test_table" in tables
    assert "schema_migrations" in tables


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "0001_create_test.sql").write_text(
        "CREATE TABLE test_table (id TEXT PRIMARY KEY)"
    )
    conn = _in_memory()
    apply_pending_sqlite_migrations(conn, tmp_path)

    # second call — nothing new to apply
    applied_again = apply_pending_sqlite_migrations(conn, tmp_path)
    assert applied_again == []


def test_incremental_migrations_applied_in_order(tmp_path: Path) -> None:
    (tmp_path / "0001_first.sql").write_text(
        "CREATE TABLE first_table (id TEXT PRIMARY KEY)"
    )
    (tmp_path / "0002_second.sql").write_text(
        "CREATE TABLE second_table (id TEXT PRIMARY KEY)"
    )

    conn = _in_memory()
    apply_pending_sqlite_migrations(conn, tmp_path)

    # add a third migration after the fact
    (tmp_path / "0003_third.sql").write_text(
        "CREATE TABLE third_table (id TEXT PRIMARY KEY)"
    )
    applied = apply_pending_sqlite_migrations(conn, tmp_path)

    assert applied == ["0003_third"]
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "third_table" in tables


def test_version_recorded_in_schema_migrations(tmp_path: Path) -> None:
    (tmp_path / "0001_baseline.sql").write_text(
        "CREATE TABLE dummy (id TEXT PRIMARY KEY)"
    )
    conn = _in_memory()
    apply_pending_sqlite_migrations(conn, tmp_path)

    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "0001_baseline"


def test_empty_migrations_dir_is_safe(tmp_path: Path) -> None:
    conn = _in_memory()
    applied = apply_pending_sqlite_migrations(conn, tmp_path)
    assert applied == []



# ---------------------------------------------------------------------------
# Smoke: real sqlite baseline migration against an in-memory DB
# ---------------------------------------------------------------------------


def test_baseline_sqlite_migration_applies_cleanly() -> None:
    """The actual 0001_initial_schema.sql must execute without error."""
    assert MIGRATIONS_DIR.exists(), f"migrations/sqlite/ not found at {MIGRATIONS_DIR}"

    conn = _in_memory()
    applied = apply_pending_sqlite_migrations(conn, MIGRATIONS_DIR)

    assert "0001_initial_schema" in applied

    # spot-check a few tables from the baseline
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for expected in (
        "source_systems",
        "ingestion_runs",
        "local_users",
        "service_tokens",
        "execution_schedules",
    ):
        assert expected in tables, f"Expected table {expected!r} not found after migration"


def test_baseline_sqlite_migration_is_idempotent() -> None:
    """Running the baseline migration twice must not raise."""
    conn = _in_memory()
    apply_pending_sqlite_migrations(conn, MIGRATIONS_DIR)
    second = apply_pending_sqlite_migrations(conn, MIGRATIONS_DIR)
    assert second == []
