"""Versioned SQL migration runner.

Migration files live under ``migrations/{backend}/NNNN_description.sql`` and are
applied in lexicographic order.  Applied versions are tracked in the
``schema_migrations`` table so each migration runs exactly once.

The runner is intentionally dependency-free: it uses only the raw dbapi2
connections (sqlite3 / psycopg) and the DuckDB connection that the rest of
the storage layer already holds.

Usage (SQLite)::

    import sqlite3
    from pathlib import Path
    from packages.storage.migration_runner import apply_pending_sqlite_migrations

    conn = sqlite3.connect("config.db")
    applied = apply_pending_sqlite_migrations(conn, Path("migrations/sqlite"))

Usage (Postgres)::

    import psycopg
    from pathlib import Path
    from packages.storage.migration_runner import apply_pending_postgres_migrations

    with psycopg.connect(dsn) as conn:
        applied = apply_pending_postgres_migrations(conn, Path("migrations/postgres"))

Usage (DuckDB)::

    import duckdb
    from pathlib import Path
    from packages.storage.migration_runner import apply_pending_duckdb_migrations

    con = duckdb.connect("warehouse.duckdb")
    applied = apply_pending_duckdb_migrations(con, Path("migrations/duckdb"))

    # Or pass a DuckDBStore directly:
    from packages.storage.duckdb_store import DuckDBStore
    store = DuckDBStore.open("warehouse.duckdb")
    applied = apply_pending_duckdb_migrations(store.connection, Path("migrations/duckdb"))

Future migrations (ALTER TABLE, new tables, etc.) belong in new numbered .sql
files.  The Python schema-init functions (``ensure_table`` / ``ensure_dimension``
et al.) remain as a backward-compat bridge for existing deployments but are
considered deprecated for production use — prefer migration files so that schema
evolution is tracked and auditable.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "apply_pending_sqlite_migrations",
    "apply_pending_postgres_migrations",
    "apply_pending_duckdb_migrations",
]

_TRACKING_DDL = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
"""

_SELECT_APPLIED = "SELECT version FROM schema_migrations"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_pending_sqlite_migrations(
    connection: sqlite3.Connection,
    migrations_dir: Path,
) -> list[str]:
    """Apply all pending SQLite migrations and return newly applied version names."""
    connection.execute(_TRACKING_DDL)
    connection.commit()
    applied = _fetch_applied(connection)
    return _apply_pending(connection, migrations_dir, applied, placeholder="?")


def apply_pending_postgres_migrations(
    connection: Any,  # psycopg.Connection[Any]
    migrations_dir: Path,
) -> list[str]:
    """Apply all pending Postgres migrations and return newly applied version names."""
    connection.execute(_TRACKING_DDL)
    connection.commit()
    applied = _fetch_applied(connection)
    return _apply_pending(connection, migrations_dir, applied, placeholder="%s")


_DUCKDB_TRACKING_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_migrations"
    " (version VARCHAR PRIMARY KEY, applied_at VARCHAR NOT NULL)"
)


def apply_pending_duckdb_migrations(
    connection: Any,  # duckdb.DuckDBPyConnection
    migrations_dir: Path,
) -> list[str]:
    """Apply all pending DuckDB warehouse migrations and return newly applied versions.

    Accepts a raw ``duckdb.DuckDBPyConnection``.  To use with a
    ``DuckDBStore``, pass ``store.connection``.
    """
    connection.execute(_DUCKDB_TRACKING_DDL)
    applied = _fetch_applied(connection)
    return _apply_pending(connection, migrations_dir, applied, placeholder="?")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_applied(connection: Any) -> set[str]:
    cursor = connection.execute(_SELECT_APPLIED)
    return {row[0] for row in cursor.fetchall()}


def _apply_pending(
    connection: Any,
    migrations_dir: Path,
    applied: set[str],
    placeholder: str,
) -> list[str]:
    newly_applied: list[str] = []

    for migration_file in sorted(migrations_dir.glob("*.sql")):
        version = migration_file.stem  # e.g. "0001_initial_schema"
        if version in applied:
            continue

        sql = migration_file.read_text()
        for statement in _split_statements(sql):
            connection.execute(statement)

        now = datetime.now(UTC).isoformat()
        connection.execute(
            f"INSERT INTO schema_migrations (version, applied_at) VALUES ({placeholder}, {placeholder})",
            (version, now),
        )
        connection.commit()
        newly_applied.append(version)

    return newly_applied


def _split_statements(sql: str) -> list[str]:
    """Split SQL text on semicolons, filtering empty blocks and comment-only chunks."""
    result = []
    for chunk in sql.split(";"):
        lines = [
            line for line in chunk.splitlines() if not line.strip().startswith("--")
        ]
        stmt = "\n".join(lines).strip()
        if stmt:
            result.append(stmt)
    return result
