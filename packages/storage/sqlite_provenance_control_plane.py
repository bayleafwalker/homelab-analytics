from __future__ import annotations

import sqlite3

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


class SQLiteProvenanceControlPlaneMixin:
    def _connect(self) -> sqlite3.Connection:
        raise NotImplementedError

    def record_source_lineage(
        self,
        entries: tuple[SourceLineageCreate, ...],
    ) -> list[SourceLineageRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO source_lineage (
                    lineage_id,
                    input_run_id,
                    target_layer,
                    target_name,
                    target_kind,
                    row_count,
                    source_system,
                    source_run_id,
                    recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        entry.recorded_at.isoformat(),
                    )
                    for entry in entries
                ],
            )
            connection.commit()
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
        params: list[str] = []
        if input_run_id is not None:
            clauses.append("input_run_id = ?")
            params.append(input_run_id)
        if target_layer is not None:
            clauses.append("target_layer = ?")
            params.append(target_layer)
        if target_name is not None:
            clauses.append("target_name = ?")
            params.append(target_name)
        if source_asset_id is not None:
            clauses.append("source_system = ?")
            params.append(source_asset_id)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    lineage_id,
                    input_run_id,
                    target_layer,
                    target_name,
                    target_kind,
                    row_count,
                    source_system,
                    source_run_id,
                    recorded_at
                FROM source_lineage
                {where_sql}
                ORDER BY recorded_at, lineage_id
                """,
                params,
            ).fetchall()
        return [_deserialize_source_lineage_row(row) for row in rows]

    def record_publication_audit(
        self,
        entries: tuple[PublicationAuditCreate, ...],
    ) -> list[PublicationAuditRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO publication_audit (
                    publication_audit_id,
                    run_id,
                    publication_key,
                    relation_name,
                    status,
                    published_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.publication_audit_id,
                        entry.run_id,
                        entry.publication_key,
                        entry.relation_name,
                        entry.status,
                        entry.published_at.isoformat(),
                    )
                    for entry in entries
                ],
            )
            connection.commit()
        return self.list_publication_audit()

    def list_publication_audit(
        self,
        *,
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> list[PublicationAuditRecord]:
        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if publication_key is not None:
            clauses.append("publication_key = ?")
            params.append(publication_key)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    publication_audit_id,
                    run_id,
                    publication_key,
                    relation_name,
                    status,
                    published_at
                FROM publication_audit
                {where_sql}
                ORDER BY published_at, publication_audit_id
                """,
                params,
            ).fetchall()
        return [_deserialize_publication_audit_row(row) for row in rows]

    def record_publication_confidence_snapshot(
        self,
        entries: tuple[PublicationConfidenceSnapshotCreate, ...],
    ) -> list[PublicationConfidenceSnapshotRecord]:
        """Record publication confidence snapshots."""
        import json

        if not entries:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO publication_confidence_snapshot (
                    snapshot_id,
                    publication_key,
                    assessed_at,
                    freshness_state,
                    completeness_pct,
                    confidence_verdict,
                    quality_flags,
                    contributing_run_ids,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.snapshot_id,
                        entry.publication_key,
                        entry.assessed_at.isoformat(),
                        entry.freshness_state,
                        entry.completeness_pct,
                        entry.confidence_verdict,
                        json.dumps(entry.quality_flags) if entry.quality_flags else None,
                        json.dumps(list(entry.contributing_run_ids))
                        if entry.contributing_run_ids
                        else None,
                        entry.created_at.isoformat(),
                    )
                    for entry in entries
                ],
            )
            connection.commit()
        return self.list_publication_confidence_snapshots()

    def list_publication_confidence_snapshots(
        self,
        *,
        publication_key: str | None = None,
        limit: int | None = None,
    ) -> list[PublicationConfidenceSnapshotRecord]:
        """List publication confidence snapshots."""
        import json
        from datetime import datetime

        clauses: list[str] = []
        params: list[str] = []
        if publication_key is not None:
            clauses.append("publication_key = ?")
            params.append(publication_key)

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_sql = f"LIMIT {limit}" if limit is not None else ""

        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    snapshot_id,
                    publication_key,
                    assessed_at,
                    freshness_state,
                    completeness_pct,
                    confidence_verdict,
                    quality_flags,
                    contributing_run_ids,
                    created_at
                FROM publication_confidence_snapshot
                {where_sql}
                ORDER BY assessed_at DESC, snapshot_id
                {limit_sql}
                """,
                params,
            ).fetchall()

        records = []
        for row in rows:
            contributing = json.loads(row["contributing_run_ids"]) if row["contributing_run_ids"] else []
            quality = json.loads(row["quality_flags"]) if row["quality_flags"] else None
            records.append(
                PublicationConfidenceSnapshotRecord(
                    snapshot_id=row["snapshot_id"],
                    publication_key=row["publication_key"],
                    assessed_at=datetime.fromisoformat(row["assessed_at"]),
                    freshness_state=row["freshness_state"],
                    completeness_pct=row["completeness_pct"],
                    confidence_verdict=row["confidence_verdict"],
                    quality_flags=quality,
                    contributing_run_ids=tuple(contributing),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        return records
