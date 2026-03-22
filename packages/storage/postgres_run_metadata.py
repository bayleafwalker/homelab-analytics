from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from packages.pipelines.csv_validation import ValidationIssue
from packages.storage.migration_runner import apply_pending_postgres_migrations
from packages.storage.postgres_support import configure_search_path, initialize_schema
from packages.storage.run_metadata import (
    IngestionRunCreate,
    IngestionRunRecord,
    IngestionRunStatus,
    _build_filter_clause,
)

_POSTGRES_RUN_METADATA_MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2] / "migrations" / "postgres_run_metadata"
)


class PostgresRunMetadataRepository:
    """Postgres-backed ingestion run metadata for the control-plane path.

    Run-metadata schema evolution is owned by ``migrations/postgres_run_metadata``
    so this repository can initialize only its own tables.
    """

    def __init__(self, dsn: str, *, schema: str = "public") -> None:
        self.dsn = dsn
        self.schema = schema
        initialize_schema(dsn, schema)
        self._initialize()

    def _connect(self, *, row_factory=None):
        connection = psycopg.connect(self.dsn, row_factory=row_factory)
        configure_search_path(connection, self.schema)
        return connection

    def create_run(self, run: IngestionRunCreate) -> IngestionRunRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_runs (
                    run_id,
                    source_name,
                    dataset_name,
                    file_name,
                    raw_path,
                    manifest_path,
                    sha256,
                    row_count,
                    header_json,
                    status,
                    passed,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run.run_id,
                    run.source_name,
                    run.dataset_name,
                    run.file_name,
                    run.raw_path,
                    run.manifest_path,
                    run.sha256,
                    run.row_count,
                    json.dumps(run.header),
                    run.status.value,
                    run.passed,
                    run.created_at,
                ),
            )
            issue_rows = [
                (
                    run.run_id,
                    issue_order,
                    issue.code,
                    issue.message,
                    issue.column,
                    issue.row_number,
                )
                for issue_order, issue in enumerate(run.issues)
            ]
            if issue_rows:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO ingestion_run_issues (
                            run_id,
                            issue_order,
                            code,
                            message,
                            column_name,
                            row_number
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        issue_rows,
                    )
        return self.get_run(run.run_id)

    def get_run(self, run_id: str) -> IngestionRunRecord:
        with self._connect(row_factory=dict_row) as connection:
            run_row = connection.execute(
                """
                SELECT
                    run_id,
                    source_name,
                    dataset_name,
                    file_name,
                    raw_path,
                    manifest_path,
                    sha256,
                    row_count,
                    header_json,
                    status,
                    passed,
                    created_at
                FROM ingestion_runs
                WHERE run_id = %s
                """,
                (run_id,),
            ).fetchone()

            if run_row is None:
                raise KeyError(f"Unknown ingestion run: {run_id}")

            issue_rows = connection.execute(
                """
                SELECT
                    code,
                    message,
                    column_name,
                    row_number
                FROM ingestion_run_issues
                WHERE run_id = %s
                ORDER BY issue_order
                """,
                (run_id,),
            ).fetchall()

        return _deserialize_run_row(run_row, issue_rows)

    def list_runs(
        self,
        dataset_name: str | None = None,
        status: IngestionRunStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[IngestionRunRecord]:
        where_sql, params = _build_postgres_filter_clause(
            dataset_name,
            status,
            from_date,
            to_date,
        )
        query = f"""
            SELECT
                run_id,
                source_name,
                dataset_name,
                file_name,
                raw_path,
                manifest_path,
                sha256,
                row_count,
                header_json,
                status,
                passed,
                created_at
            FROM ingestion_runs
            {where_sql}
            ORDER BY created_at DESC, run_id DESC
        """
        if limit is not None:
            query += " LIMIT %s OFFSET %s"
            params = [*params, limit, offset]

        with self._connect(row_factory=dict_row) as connection:
            run_rows = connection.execute(query, params).fetchall()
            issues_by_run = self._load_issues_for_run_ids(
                connection,
                [str(row["run_id"]) for row in run_rows],
            )

        return [
            _deserialize_run_row(row, issues_by_run[str(row["run_id"])])
            for row in run_rows
        ]

    def count_runs(
        self,
        dataset_name: str | None = None,
        status: IngestionRunStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        where_sql, params = _build_postgres_filter_clause(
            dataset_name,
            status,
            from_date,
            to_date,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM ingestion_runs {where_sql}",
                params,
            ).fetchone()
        if row is None:
            return 0
        return int(row[0])

    def find_run_by_sha256(
        self,
        sha256: str,
        dataset_name: str | None = None,
    ) -> IngestionRunRecord | None:
        clauses = ["sha256 = %s", "passed = TRUE"]
        params: list[Any] = [sha256]
        if dataset_name is not None:
            clauses.append("dataset_name = %s")
            params.append(dataset_name)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT run_id
                FROM ingestion_runs
                WHERE {" AND ".join(clauses)}
                ORDER BY created_at ASC
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            return None
        return self.get_run(str(row[0]))

    def _initialize(self) -> None:
        with self._connect() as connection:
            apply_pending_postgres_migrations(
                connection,
                _POSTGRES_RUN_METADATA_MIGRATIONS_DIR,
            )

    def _load_issues_for_run_ids(
        self,
        connection: psycopg.Connection[Any],
        run_ids: list[str],
    ) -> dict[str, list[ValidationIssue]]:
        issues_by_run: dict[str, list[ValidationIssue]] = {
            run_id: [] for run_id in run_ids
        }
        if not run_ids:
            return issues_by_run

        issue_rows = connection.execute(
            """
            SELECT
                run_id,
                code,
                message,
                column_name,
                row_number
            FROM ingestion_run_issues
            WHERE run_id = ANY(%s)
            ORDER BY run_id, issue_order
            """,
            (run_ids,),
        ).fetchall()
        for row in issue_rows:
            issues_by_run[str(row["run_id"])].append(
                ValidationIssue(
                    code=str(row["code"]),
                    message=str(row["message"]),
                    column=row["column_name"],
                    row_number=row["row_number"],
                )
            )
        return issues_by_run


def _deserialize_run_row(
    run_row: dict[str, Any],
    issue_rows: list[dict[str, Any]] | list[ValidationIssue],
) -> IngestionRunRecord:
    issues = [
        issue
        if isinstance(issue, ValidationIssue)
        else ValidationIssue(
            code=str(issue["code"]),
            message=str(issue["message"]),
            column=issue["column_name"],
            row_number=issue["row_number"],
        )
        for issue in issue_rows
    ]
    created_at = run_row["created_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    return IngestionRunRecord(
        run_id=str(run_row["run_id"]),
        source_name=str(run_row["source_name"]),
        dataset_name=str(run_row["dataset_name"]),
        file_name=str(run_row["file_name"]),
        raw_path=str(run_row["raw_path"]),
        manifest_path=str(run_row["manifest_path"]),
        sha256=str(run_row["sha256"]),
        row_count=int(run_row["row_count"]),
        header=tuple(json.loads(str(run_row["header_json"]))),
        status=IngestionRunStatus(str(run_row["status"])),
        passed=bool(run_row["passed"]),
        issues=issues,
        created_at=created_at,
    )


def _build_postgres_filter_clause(
    dataset_name: str | None,
    status: IngestionRunStatus | None,
    from_date: datetime | None,
    to_date: datetime | None,
) -> tuple[str, list[Any]]:
    where_sql, params = _build_filter_clause(
        dataset_name,
        status,
        from_date,
        to_date,
    )
    numbered_params = list(params)
    while "?" in where_sql:
        where_sql = where_sql.replace("?", "%s", 1)
    return where_sql, numbered_params
