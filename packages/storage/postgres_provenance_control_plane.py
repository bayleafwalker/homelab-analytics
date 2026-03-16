from __future__ import annotations

from typing import cast

import psycopg
from psycopg.rows import dict_row

from packages.storage.control_plane import (
    PublicationAuditCreate,
    PublicationAuditRecord,
    SourceLineageCreate,
    SourceLineageRecord,
)
from packages.storage.control_plane_support import (
    _deserialize_publication_audit_row,
    _deserialize_source_lineage_row,
)


def _coerce_row_mapping(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise TypeError(f"Unsupported row value: {row!r}")
    return cast(dict[str, object], row)


class PostgresProvenanceControlPlaneMixin:
    def _connect(
        self,
        *,
        row_factory: object = None,
    ) -> psycopg.Connection[object]:
        raise NotImplementedError

    def record_source_lineage(
        self,
        entries: tuple[SourceLineageCreate, ...],
    ) -> list[SourceLineageRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO source_lineage (
                        lineage_id, input_run_id, target_layer, target_name, target_kind,
                        row_count, source_system, source_run_id, recorded_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            entry.lineage_id,
                            entry.input_run_id,
                            entry.target_layer,
                            entry.target_name,
                            entry.target_kind,
                            entry.row_count,
                            entry.source_system,
                            entry.source_run_id,
                            entry.recorded_at,
                        )
                        for entry in entries
                    ],
                )
        return self.list_source_lineage()

    def list_source_lineage(
        self,
        *,
        input_run_id: str | None = None,
        target_layer: str | None = None,
    ) -> list[SourceLineageRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if input_run_id is not None:
            clauses.append("input_run_id = %s")
            params.append(input_run_id)
        if target_layer is not None:
            clauses.append("target_layer = %s")
            params.append(target_layer)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"""
                SELECT lineage_id, input_run_id, target_layer, target_name, target_kind,
                       row_count, source_system, source_run_id, recorded_at
                FROM source_lineage
                {where_sql}
                ORDER BY recorded_at, lineage_id
                """,
                params,
            ).fetchall()
        return [_deserialize_source_lineage_row(_coerce_row_mapping(row)) for row in rows]

    def record_publication_audit(
        self,
        entries: tuple[PublicationAuditCreate, ...],
    ) -> list[PublicationAuditRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO publication_audit (
                        publication_audit_id, run_id, publication_key, relation_name, status, published_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            entry.publication_audit_id,
                            entry.run_id,
                            entry.publication_key,
                            entry.relation_name,
                            entry.status,
                            entry.published_at,
                        )
                        for entry in entries
                    ],
                )
        return self.list_publication_audit()

    def list_publication_audit(
        self,
        *,
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> list[PublicationAuditRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if run_id is not None:
            clauses.append("run_id = %s")
            params.append(run_id)
        if publication_key is not None:
            clauses.append("publication_key = %s")
            params.append(publication_key)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"""
                SELECT publication_audit_id, run_id, publication_key, relation_name, status, published_at
                FROM publication_audit
                {where_sql}
                ORDER BY published_at, publication_audit_id
                """,
                params,
            ).fetchall()
        return [_deserialize_publication_audit_row(_coerce_row_mapping(row)) for row in rows]
