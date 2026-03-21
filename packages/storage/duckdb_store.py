"""DuckDB-backed analytical store for transformation and reporting layers.

Provides:
- SCD Type 2 dimension management (insert, update, close, point-in-time query)
- Fact table persistence
- Mart materialisation

Tables live in a single DuckDB database file.  For tests an in-memory
database is used via ``connect(":memory:")``.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any, Generator

import duckdb

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SURROGATE_KEY_TYPE = "VARCHAR"
_SCD_VALID_FROM = "valid_from"
_SCD_VALID_TO = "valid_to"
_SCD_IS_CURRENT = "is_current"
_SCD_SOURCE_SYSTEM = "source_system"
_SCD_SOURCE_RUN_ID = "source_run_id"
_SCD_META_COLUMNS = (
    _SCD_VALID_FROM,
    _SCD_VALID_TO,
    _SCD_IS_CURRENT,
    _SCD_SOURCE_SYSTEM,
    _SCD_SOURCE_RUN_ID,
)

# Sentinel date used as valid_to for current rows.
_FAR_FUTURE = date(9999, 12, 31)


def _new_key() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Dimension definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DimensionColumn:
    """One business column in a dimension table."""

    name: str
    dtype: str  # DuckDB SQL type, e.g. "VARCHAR", "DATE"


@dataclass(frozen=True)
class DimensionDefinition:
    """Blueprint for an SCD Type 2 dimension table."""

    table_name: str
    natural_key_columns: tuple[str, ...]
    attribute_columns: tuple[DimensionColumn, ...]
    surrogate_key_column: str = "sk"

    @property
    def all_business_columns(self) -> tuple[str, ...]:
        return self.natural_key_columns + tuple(
            c.name for c in self.attribute_columns
        )


# ---------------------------------------------------------------------------
# DuckDB analytical store
# ---------------------------------------------------------------------------


class DuckDBStore:
    """Thin wrapper around a DuckDB connection providing SCD-2 helpers."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._con = connection

    # -- connection helpers --------------------------------------------------

    @classmethod
    def open(cls, path: str) -> DuckDBStore:
        """Open (or create) a persistent DuckDB database."""
        return cls(duckdb.connect(path))

    @classmethod
    def memory(cls) -> DuckDBStore:
        """Create an in-memory database suitable for tests."""
        return cls(duckdb.connect(":memory:"))

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._con

    def close(self) -> None:
        self._con.close()

    # -- transaction helpers -------------------------------------------------

    @contextmanager
    def atomic(self) -> Generator["DuckDBStore", None, None]:
        """Context manager that wraps a block of DuckDB statements in a single
        transaction.  If the block raises, the transaction is rolled back and
        the exception is re-raised; otherwise it is committed.
        """
        self._con.begin()
        try:
            yield self
            self._con.commit()
        except Exception:
            self._con.rollback()
            raise

    # -- DDL helpers ---------------------------------------------------------

    def ensure_dimension(self, defn: DimensionDefinition) -> None:
        """Create the SCD-2 dimension table if it does not exist."""
        cols: list[str] = [f"{defn.surrogate_key_column} {_SURROGATE_KEY_TYPE} PRIMARY KEY"]
        for nk in defn.natural_key_columns:
            cols.append(f"{nk} VARCHAR NOT NULL")
        for ac in defn.attribute_columns:
            cols.append(f"{ac.name} {ac.dtype}")
        cols.append(f"{_SCD_VALID_FROM} DATE NOT NULL")
        cols.append(f"{_SCD_VALID_TO} DATE NOT NULL")
        cols.append(f"{_SCD_IS_CURRENT} BOOLEAN NOT NULL")
        cols.append(f"{_SCD_SOURCE_SYSTEM} VARCHAR")
        cols.append(f"{_SCD_SOURCE_RUN_ID} VARCHAR")
        ddl = f"CREATE TABLE IF NOT EXISTS {defn.table_name} ({', '.join(cols)})"
        self._con.execute(ddl)
        existing_columns = {
            row[1] for row in self._con.execute(f"PRAGMA table_info('{defn.table_name}')").fetchall()
        }
        # Add any attribute columns that exist in the definition but not in the table.
        # This handles schema migrations when a definition gains new columns after
        # a database was first created (e.g. dim_category gaining domain/is_system).
        for ac in defn.attribute_columns:
            if ac.name not in existing_columns:
                self._con.execute(
                    f"ALTER TABLE {defn.table_name} ADD COLUMN {ac.name} {ac.dtype}"
                )
        if _SCD_SOURCE_SYSTEM not in existing_columns:
            self._con.execute(
                f"ALTER TABLE {defn.table_name} ADD COLUMN {_SCD_SOURCE_SYSTEM} VARCHAR"
            )
        if _SCD_SOURCE_RUN_ID not in existing_columns:
            self._con.execute(
                f"ALTER TABLE {defn.table_name} ADD COLUMN {_SCD_SOURCE_RUN_ID} VARCHAR"
            )

    def ensure_current_dimension_view(
        self,
        defn: DimensionDefinition,
        view_name: str,
    ) -> None:
        """Publish a reporting-layer view over the current SCD rows."""
        cols = [defn.surrogate_key_column] + list(defn.all_business_columns)
        self._con.execute(
            f"""
            CREATE OR REPLACE VIEW {view_name} AS
            SELECT {', '.join(cols)}
            FROM {defn.table_name}
            WHERE {_SCD_IS_CURRENT} = TRUE
            """
        )

    def ensure_table(self, table_name: str, columns: list[tuple[str, str]]) -> None:
        """Create a plain table (fact / mart) if it does not exist."""
        cols = ", ".join(f"{name} {dtype}" for name, dtype in columns)
        self._con.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({cols})")

    # -- SCD Type 2 operations -----------------------------------------------

    def upsert_dimension_rows(
        self,
        defn: DimensionDefinition,
        rows: list[dict[str, Any]],
        *,
        effective_date: date | None = None,
        source_system: str | None = None,
        source_run_id: str | None = None,
    ) -> int:
        """Insert-or-update dimension rows using SCD Type 2 semantics.

        Each *row* must contain all business columns (natural key + attributes).
        Returns the number of new version rows inserted.
        """
        if not rows:
            return 0

        eff = effective_date or date.today()
        inserted = 0

        for row in rows:
            nk_filter = " AND ".join(
                f"{col} = ?" for col in defn.natural_key_columns
            )
            nk_values = [row[col] for col in defn.natural_key_columns]

            # Fetch current version (if any)
            current = self._con.execute(
                f"SELECT {defn.surrogate_key_column}, "
                + ", ".join(c.name for c in defn.attribute_columns)
                + f" FROM {defn.table_name}"
                f" WHERE {nk_filter} AND {_SCD_IS_CURRENT} = TRUE",
                nk_values,
            ).fetchone()

            if current is None:
                # New natural key → simple insert
                sk = _new_key()
                col_names = [defn.surrogate_key_column] + list(defn.all_business_columns) + list(_SCD_META_COLUMNS)
                placeholders = ", ".join("?" for _ in col_names)
                values = (
                    [sk]
                    + [row[c] for c in defn.all_business_columns]
                    + [eff, _FAR_FUTURE, True, source_system, source_run_id]
                )
                self._con.execute(
                    f"INSERT INTO {defn.table_name} ({', '.join(col_names)}) VALUES ({placeholders})",
                    values,
                )
                inserted += 1
            else:
                # Check whether attributes actually changed
                existing_attrs = current[1:]  # skip sk
                new_attrs = tuple(row[c.name] for c in defn.attribute_columns)
                if existing_attrs == new_attrs:
                    continue  # no change – skip

                old_sk = current[0]
                # Close old version
                self._con.execute(
                    f"UPDATE {defn.table_name}"
                    f" SET {_SCD_VALID_TO} = ?, {_SCD_IS_CURRENT} = FALSE"
                    f" WHERE {defn.surrogate_key_column} = ?",
                    [eff, old_sk],
                )
                # Insert new version
                sk = _new_key()
                col_names = [defn.surrogate_key_column] + list(defn.all_business_columns) + list(_SCD_META_COLUMNS)
                placeholders = ", ".join("?" for _ in col_names)
                values = (
                    [sk]
                    + [row[c] for c in defn.all_business_columns]
                    + [eff, _FAR_FUTURE, True, source_system, source_run_id]
                )
                self._con.execute(
                    f"INSERT INTO {defn.table_name} ({', '.join(col_names)}) VALUES ({placeholders})",
                    values,
                )
                inserted += 1

        return inserted

    def query_current(self, defn: DimensionDefinition) -> list[dict[str, Any]]:
        """Return all current rows for a dimension."""
        cols = list(defn.all_business_columns)
        result = self._con.execute(
            f"SELECT {defn.surrogate_key_column}, {', '.join(cols)}"
            f" FROM {defn.table_name}"
            f" WHERE {_SCD_IS_CURRENT} = TRUE"
            f" ORDER BY {', '.join(defn.natural_key_columns)}",
        ).fetchall()
        col_names = [defn.surrogate_key_column] + cols
        return [dict(zip(col_names, r)) for r in result]

    def query_as_of(
        self, defn: DimensionDefinition, as_of: date
    ) -> list[dict[str, Any]]:
        """Point-in-time query for a dimension."""
        cols = list(defn.all_business_columns)
        result = self._con.execute(
            f"SELECT {defn.surrogate_key_column}, {', '.join(cols)}"
            f" FROM {defn.table_name}"
            f" WHERE {_SCD_VALID_FROM} <= ? AND {_SCD_VALID_TO} > ?"
            f" ORDER BY {', '.join(defn.natural_key_columns)}",
            [as_of, as_of],
        ).fetchall()
        col_names = [defn.surrogate_key_column] + cols
        return [dict(zip(col_names, r)) for r in result]

    # -- Fact / mart helpers -------------------------------------------------

    def insert_rows(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        """Bulk-insert rows into a plain table.  Returns rows inserted."""
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        stmt = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})"
        for row in rows:
            self._con.execute(stmt, [row[c] for c in cols])
        return len(rows)

    def execute(self, sql: str, params: list[Any] | None = None) -> Any:
        """Execute arbitrary SQL (for mart materialisation, etc.)."""
        return self._con.execute(sql, params or [])

    def fetchall(self, sql: str, params: list[Any] | None = None) -> list[tuple]:
        """Execute SQL and return all result rows as tuples."""
        return self._con.execute(sql, params or []).fetchall()

    def fetchall_dicts(
        self, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute SQL and return all result rows as dicts."""
        cur = self._con.execute(sql, params or [])
        col_names = [desc[0] for desc in cur.description]
        return [dict(zip(col_names, row)) for row in cur.fetchall()]
