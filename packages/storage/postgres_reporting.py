from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row


def _postgres_dtype(dtype: str) -> str:
    translated = dtype
    translated = translated.replace("VARCHAR", "TEXT")
    translated = translated.replace("DECIMAL", "NUMERIC")
    return translated


class PostgresReportingStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def table_exists(self, table_name: str) -> bool:
        with psycopg.connect(self.dsn) as connection:
            row = connection.execute(
                "SELECT to_regclass(%s)",
                (table_name,),
            ).fetchone()
        return row is not None and row[0] is not None

    def ensure_table(self, table_name: str, columns: list[tuple[str, str]]) -> None:
        ddl_columns = ", ".join(
            f"{name} {_postgres_dtype(dtype)}" for name, dtype in columns
        )
        with psycopg.connect(self.dsn) as connection:
            connection.execute(
                f"CREATE TABLE IF NOT EXISTS {table_name} ({ddl_columns})"
            )

    def replace_rows(
        self,
        table_name: str,
        columns: list[tuple[str, str]],
        rows: list[dict[str, Any]],
    ) -> None:
        self.ensure_table(table_name, columns)
        column_names = [name for name, _ in columns]
        placeholders = ", ".join("%s" for _ in column_names)
        insert_sql = (
            f"INSERT INTO {table_name} ({', '.join(column_names)}) "
            f"VALUES ({placeholders})"
        )
        values = [
            [row.get(column_name) for column_name in column_names]
            for row in rows
        ]
        with psycopg.connect(self.dsn) as connection:
            connection.execute(f"TRUNCATE TABLE {table_name}")
            if values:
                with connection.cursor() as cursor:
                    cursor.executemany(insert_sql, values)

    def fetchall_dicts(
        self,
        sql: str,
        params: list[Any] | tuple[Any, ...] | None = None,
    ) -> list[dict[str, Any]]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            return list(connection.execute(sql, params or ()).fetchall())
