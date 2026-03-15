from __future__ import annotations

import re

import psycopg

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(value: str, *, kind: str = "identifier") -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid PostgreSQL {kind}: {value!r}")
    return value


def initialize_schema(dsn: str, schema: str) -> None:
    validated = validate_identifier(schema, kind="schema")
    with psycopg.connect(dsn) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {validated}")


def configure_search_path(connection: psycopg.Connection, schema: str) -> None:
    validated = validate_identifier(schema, kind="schema")
    connection.execute(f"SET search_path TO {validated}")
