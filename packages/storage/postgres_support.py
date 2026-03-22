from __future__ import annotations

import re
import time
from typing import Any

import psycopg

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONNECT_RETRY_ATTEMPTS = 20
_CONNECT_RETRY_DELAY_SECONDS = 0.5


def validate_identifier(value: str, *, kind: str = "identifier") -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid PostgreSQL {kind}: {value!r}")
    return value


def connect_with_retry(
    dsn: str,
    *,
    row_factory: Any | None = None,
) -> psycopg.Connection[Any]:
    last_exc: psycopg.OperationalError | None = None
    for attempt in range(1, _CONNECT_RETRY_ATTEMPTS + 1):
        try:
            return psycopg.connect(dsn, row_factory=row_factory)
        except psycopg.OperationalError as exc:
            last_exc = exc
            if attempt == _CONNECT_RETRY_ATTEMPTS:
                break
            time.sleep(_CONNECT_RETRY_DELAY_SECONDS)
    if last_exc is None:
        raise RuntimeError("connect_with_retry exhausted without psycopg.OperationalError")
    raise last_exc


def initialize_schema(dsn: str, schema: str) -> None:
    validated = validate_identifier(schema, kind="schema")
    with connect_with_retry(dsn) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {validated}")


def configure_search_path(connection: psycopg.Connection, schema: str) -> None:
    validated = validate_identifier(schema, kind="schema")
    connection.execute(f"SET search_path TO {validated}")
