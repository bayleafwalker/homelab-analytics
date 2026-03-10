from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from packages.pipelines.csv_validation import ValidationIssue


class IngestionRunStatus(StrEnum):
    RECEIVED = "received"
    LANDED = "landed"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class IngestionRunCreate:
    run_id: str
    source_name: str
    dataset_name: str
    file_name: str
    raw_path: str
    manifest_path: str
    sha256: str
    row_count: int
    header: tuple[str, ...]
    status: IngestionRunStatus
    passed: bool
    issues: tuple[ValidationIssue, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class IngestionRunRecord:
    run_id: str
    source_name: str
    dataset_name: str
    file_name: str
    raw_path: str
    manifest_path: str
    sha256: str
    row_count: int
    header: tuple[str, ...]
    status: IngestionRunStatus
    passed: bool
    issues: list[ValidationIssue]
    created_at: datetime


class RunMetadataStore(Protocol):
    def create_run(self, run: IngestionRunCreate) -> IngestionRunRecord:
        ...

    def get_run(self, run_id: str) -> IngestionRunRecord:
        ...

    def list_runs(
        self,
        dataset_name: str | None = None,
        status: IngestionRunStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[IngestionRunRecord]:
        ...

    def count_runs(
        self,
        dataset_name: str | None = None,
        status: IngestionRunStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        ...

    def find_run_by_sha256(
        self,
        sha256: str,
        dataset_name: str | None = None,
    ) -> IngestionRunRecord | None:
        ...


def _build_filter_clause(
    dataset_name: str | None,
    status: IngestionRunStatus | None,
    from_date: datetime | None,
    to_date: datetime | None,
) -> tuple[str, list[Any]]:
    """Build a SQL WHERE clause and bound-parameter list from optional filter values."""
    clauses: list[str] = []
    params: list[Any] = []
    if dataset_name is not None:
        clauses.append("dataset_name = ?")
        params.append(dataset_name)
    if status is not None:
        clauses.append("status = ?")
        params.append(status.value)
    if from_date is not None:
        clauses.append("created_at >= ?")
        params.append(from_date.isoformat())
    if to_date is not None:
        clauses.append("created_at <= ?")
        params.append(to_date.isoformat())
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params


class RunMetadataRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_run(self, run: IngestionRunCreate) -> IngestionRunRecord:
        with closing(sqlite3.connect(self.database_path)) as connection:
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int(run.passed),
                    run.created_at.isoformat(),
                ),
            )
            connection.executemany(
                """
                INSERT INTO ingestion_run_issues (
                    run_id,
                    issue_order,
                    code,
                    message,
                    column_name,
                    row_number
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run.run_id,
                        issue_order,
                        issue.code,
                        issue.message,
                        issue.column,
                        issue.row_number,
                    )
                    for issue_order, issue in enumerate(run.issues)
                ],
            )
            connection.commit()
        return self.get_run(run.run_id)

    def get_run(self, run_id: str) -> IngestionRunRecord:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
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
                WHERE run_id = ?
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
                WHERE run_id = ?
                ORDER BY issue_order
                """,
                (run_id,),
            ).fetchall()

        return IngestionRunRecord(
            run_id=run_row["run_id"],
            source_name=run_row["source_name"],
            dataset_name=run_row["dataset_name"],
            file_name=run_row["file_name"],
            raw_path=run_row["raw_path"],
            manifest_path=run_row["manifest_path"],
            sha256=run_row["sha256"],
            row_count=run_row["row_count"],
            header=tuple(json.loads(run_row["header_json"])),
            status=IngestionRunStatus(run_row["status"]),
            passed=bool(run_row["passed"]),
            issues=[
                ValidationIssue(
                    code=row["code"],
                    message=row["message"],
                    column=row["column_name"],
                    row_number=row["row_number"],
                )
                for row in issue_rows
            ],
            created_at=datetime.fromisoformat(run_row["created_at"]),
        )

    def find_run_by_sha256(
        self,
        sha256: str,
        dataset_name: str | None = None,
    ) -> IngestionRunRecord | None:
        """Return the earliest landed run matching *sha256* within the dataset scope."""
        with closing(sqlite3.connect(self.database_path)) as connection:
            clauses = ["sha256 = ?", "passed = 1"]
            params: list[Any] = [sha256]
            if dataset_name is not None:
                clauses.append("dataset_name = ?")
                params.append(dataset_name)
            row = connection.execute(
                f"""
                SELECT run_id FROM ingestion_runs
                WHERE {" AND ".join(clauses)}
                ORDER BY created_at ASC
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            return None
        return self.get_run(row[0])

    def list_runs(
        self,
        dataset_name: str | None = None,
        status: IngestionRunStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[IngestionRunRecord]:
        where_sql, params = _build_filter_clause(dataset_name, status, from_date, to_date)
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
            query += " LIMIT ? OFFSET ?"
            params = list(params) + [limit, offset]
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            run_rows = connection.execute(query, params).fetchall()
            issues_by_run = self._load_issues_for_run_ids(
                connection,
                [row["run_id"] for row in run_rows],
            )
        return [
            IngestionRunRecord(
                run_id=row["run_id"],
                source_name=row["source_name"],
                dataset_name=row["dataset_name"],
                file_name=row["file_name"],
                raw_path=row["raw_path"],
                manifest_path=row["manifest_path"],
                sha256=row["sha256"],
                row_count=row["row_count"],
                header=tuple(json.loads(row["header_json"])),
                status=IngestionRunStatus(row["status"]),
                passed=bool(row["passed"]),
                issues=issues_by_run[row["run_id"]],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in run_rows
        ]

    def count_runs(
        self,
        dataset_name: str | None = None,
        status: IngestionRunStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        """Return the total number of runs matching the given filters."""
        where_sql, params = _build_filter_clause(dataset_name, status, from_date, to_date)
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM ingestion_runs {where_sql}",
                params,
            ).fetchone()
        return row[0]

    def _initialize(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    run_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    dataset_name TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    raw_path TEXT NOT NULL,
                    manifest_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    header_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ingestion_run_issues (
                    run_id TEXT NOT NULL,
                    issue_order INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    message TEXT NOT NULL,
                    column_name TEXT,
                    row_number INTEGER,
                    PRIMARY KEY (run_id, issue_order),
                    FOREIGN KEY (run_id) REFERENCES ingestion_runs (run_id)
                );
                """
            )
            connection.commit()

    def _load_issues_for_run_ids(
        self,
        connection: sqlite3.Connection,
        run_ids: list[str],
    ) -> dict[str, list[ValidationIssue]]:
        issues_by_run: dict[str, list[ValidationIssue]] = {
            run_id: [] for run_id in run_ids
        }
        if not run_ids:
            return issues_by_run

        placeholders = ", ".join("?" for _ in run_ids)
        issue_rows = connection.execute(
            f"""
            SELECT
                run_id,
                code,
                message,
                column_name,
                row_number
            FROM ingestion_run_issues
            WHERE run_id IN ({placeholders})
            ORDER BY run_id, issue_order
            """,
            run_ids,
        ).fetchall()
        for row in issue_rows:
            issues_by_run[row["run_id"]].append(
                ValidationIssue(
                    code=row["code"],
                    message=row["message"],
                    column=row["column_name"],
                    row_number=row["row_number"],
                )
            )
        return issues_by_run
