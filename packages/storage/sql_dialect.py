"""Dialect hooks shared by the SQLite and Postgres control-plane stores.

Dialect-neutral store logic writes SQL with ``?`` placeholders and ``TRUE``/``FALSE``
literals (SQLite >= 3.23 understands both), encodes parameters through the active
``SqlDialect``, and reads rows as plain mappings through a ``DialectSession``. Each
backend supplies a ``_session()`` context manager that owns connection setup,
transaction boundaries, and write locking.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, cast

from psycopg.rows import dict_row


@dataclass(frozen=True)
class SqlDialect:
    """Per-backend SQL rendering and parameter encoding."""

    name: str
    placeholder: str
    # Appended to a single-row SELECT that is about to be updated in the same session.
    row_lock_clause: str
    # Appended to a queue-style SELECT where concurrent workers should skip locked rows.
    skip_locked_clause: str
    encode_datetime: Callable[[datetime | None], object]
    encode_bool: Callable[[bool], object]

    def render(self, statement: str) -> str:
        if self.placeholder == "?":
            return statement
        return statement.replace("?", self.placeholder)


def _sqlite_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _native_datetime(value: datetime | None) -> datetime | None:
    return value


SQLITE_DIALECT = SqlDialect(
    name="sqlite",
    placeholder="?",
    row_lock_clause="",
    skip_locked_clause="",
    encode_datetime=_sqlite_datetime,
    encode_bool=int,
)

POSTGRES_DIALECT = SqlDialect(
    name="postgres",
    placeholder="%s",
    row_lock_clause="FOR UPDATE",
    skip_locked_clause="FOR UPDATE SKIP LOCKED",
    encode_datetime=_native_datetime,
    encode_bool=bool,
)


Row = Mapping[str, object]


class DialectSession(Protocol):
    dialect: SqlDialect

    def fetchone(self, statement: str, params: Sequence[object] = ()) -> Row | None: ...

    def fetchall(self, statement: str, params: Sequence[object] = ()) -> list[Row]: ...

    def execute(self, statement: str, params: Sequence[object] = ()) -> int: ...


class DbApiSession:
    """Adapts a DB-API connection with ``execute()`` to ``DialectSession``."""

    def __init__(self, connection: Any, dialect: SqlDialect) -> None:
        self._connection = connection
        self.dialect = dialect

    def _run(self, statement: str, params: Sequence[object]) -> Any:
        rendered = self.dialect.render(statement)
        if not params:
            return self._connection.execute(rendered)
        return self._connection.execute(rendered, tuple(params))

    def fetchone(self, statement: str, params: Sequence[object] = ()) -> Row | None:
        row = self._run(statement, params).fetchone()
        return _as_row(row) if row is not None else None

    def fetchall(self, statement: str, params: Sequence[object] = ()) -> list[Row]:
        return [_as_row(row) for row in self._run(statement, params).fetchall()]

    def execute(self, statement: str, params: Sequence[object] = ()) -> int:
        return int(self._run(statement, params).rowcount)


def _as_row(row: object) -> Row:
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    if isinstance(row, dict):
        return cast(Row, row)
    raise TypeError(f"Unsupported row value: {row!r}")


@contextmanager
def sqlite_session(
    connect: Callable[[], Any],
    *,
    write_lock: bool = False,
) -> Iterator[DialectSession]:
    """Open a SQLite session; commits on success, rolls back (via close) on error."""
    with connect() as connection:
        connection.row_factory = sqlite3.Row
        if write_lock:
            connection.execute("BEGIN IMMEDIATE")
        yield DbApiSession(connection, SQLITE_DIALECT)
        connection.commit()


@contextmanager
def postgres_session(connect: Callable[[], Any]) -> Iterator[DialectSession]:
    """Open a Postgres session; psycopg commits on success and rolls back on error."""
    with connect() as connection:
        yield DbApiSession(connection, POSTGRES_DIALECT)


def row_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def row_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def row_optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


class SQLiteSessionMixin:
    """Provides ``_session()`` for stores whose ``_connect()`` yields a sqlite3 connection."""

    if TYPE_CHECKING:

        def _connect(self) -> Any: ...

    def _session(self, *, write_lock: bool = False) -> AbstractContextManager[DialectSession]:
        return sqlite_session(self._connect, write_lock=write_lock)


class PostgresSessionMixin:
    """Provides ``_session()`` for stores whose ``_connect()`` opens a psycopg connection.

    Row locking (``FOR UPDATE`` / ``SKIP LOCKED``) is rendered from the dialect, so
    ``write_lock`` needs no extra statement here.
    """

    if TYPE_CHECKING:

        def _connect(self, *, row_factory: Any = None) -> Any: ...

    def _session(self, *, write_lock: bool = False) -> AbstractContextManager[DialectSession]:
        return postgres_session(lambda: self._connect(row_factory=dict_row))
