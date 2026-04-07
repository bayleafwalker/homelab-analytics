from __future__ import annotations

from typing import cast

import psycopg
from psycopg.rows import dict_row

from packages.storage.control_plane import (
    PublicationAuditCreate,
    PublicationAuditRecord,
    PublicationConfidenceSnapshotCreate,
    PublicationConfidenceSnapshotRecord,
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
        target_name: str | None = None,
        source_asset_id: str | None = None,
    ) -> list[SourceLineageRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if input_run_id is not None:
            clauses.append("input_run_id = %s")
            params.append(input_run_id)
        if target_layer is not None:
            clauses.append("target_layer = %s")
            params.append(target_layer)
        if target_name is not None:
            clauses.append("target_name = %s")
            params.append(target_name)
        if source_asset_id is not None:
            clauses.append("source_system = %s")
            params.append(source_asset_id)
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

    def record_publication_confidence_snapshot(
        self,
        entries: tuple[PublicationConfidenceSnapshotCreate, ...],
    ) -> list[PublicationConfidenceSnapshotRecord]:
        """Record publication confidence snapshots."""
        if not entries:
            return []
        import json

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO publication_confidence_snapshot (
                        snapshot_id, publication_key, assessed_at, freshness_state,
                        completeness_pct, confidence_verdict, quality_flags,
                        contributing_run_ids, source_freshness_states, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            entry.snapshot_id,
                            entry.publication_key,
                            entry.assessed_at,
                            entry.freshness_state,
                            entry.completeness_pct,
                            entry.confidence_verdict,
                            json.dumps(entry.quality_flags) if entry.quality_flags else None,
                            list(entry.contributing_run_ids) if entry.contributing_run_ids else None,
                            json.dumps(entry.source_freshness_states) if entry.source_freshness_states else None,
                            entry.created_at,
                        )
                        for entry in entries
                    ],
                )
        return self.list_publication_confidence_snapshots()

    def list_publication_confidence_snapshots(
        self,
        *,
        publication_key: str | None = None,
        limit: int | None = None,
    ) -> list[PublicationConfidenceSnapshotRecord]:
        """List publication confidence snapshots."""
        import json

        clauses: list[str] = []
        params: list[object] = []
        if publication_key is not None:
            clauses.append("publication_key = %s")
            params.append(publication_key)

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_sql = f"LIMIT {limit}" if limit is not None else ""

        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"""
                SELECT snapshot_id, publication_key, assessed_at, freshness_state,
                       completeness_pct, confidence_verdict, quality_flags,
                       contributing_run_ids, source_freshness_states, created_at
                FROM publication_confidence_snapshot
                {where_sql}
                ORDER BY assessed_at DESC, snapshot_id
                {limit_sql}
                """,
                params,
            ).fetchall()

        records = []
        for row in rows:
            row_dict = _coerce_row_mapping(row)
            quality_flags_raw = row_dict["quality_flags"]
            contributing_run_ids_raw = row_dict["contributing_run_ids"]
            source_freshness_states_raw = row_dict["source_freshness_states"]
            records.append(
                PublicationConfidenceSnapshotRecord(
                    snapshot_id=str(row_dict["snapshot_id"]),
                    publication_key=str(row_dict["publication_key"]),
                    assessed_at=row_dict["assessed_at"],  # type: ignore
                    freshness_state=str(row_dict["freshness_state"]),
                    completeness_pct=int(row_dict["completeness_pct"]),  # type: ignore
                    confidence_verdict=str(row_dict["confidence_verdict"]),
                    quality_flags=json.loads(quality_flags_raw)
                    if isinstance(quality_flags_raw, (str, bytes, bytearray))
                    else None,
                    contributing_run_ids=tuple(str(value) for value in contributing_run_ids_raw)
                    if isinstance(contributing_run_ids_raw, (list, tuple))
                    else (),
                    source_freshness_states=json.loads(source_freshness_states_raw)
                    if isinstance(source_freshness_states_raw, (str, bytes, bytearray))
                    else None,
                    created_at=row_dict["created_at"],  # type: ignore
                )
            )
        return records
