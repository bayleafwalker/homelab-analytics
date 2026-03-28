from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, date, datetime, timedelta

from packages.storage.ingestion_catalog import (
    ReferenceFactCreate,
    ReferenceFactRecord,
)


def _deserialize_reference_fact_row(row: sqlite3.Row) -> ReferenceFactRecord:
    return ReferenceFactRecord(
        fact_id=row["fact_id"],
        entity_type=row["entity_type"],
        entity_key=row["entity_key"],
        attribute=row["attribute"],
        value=row["value"],
        effective_from=date.fromisoformat(row["effective_from"]),
        effective_to=(
            date.fromisoformat(row["effective_to"])
            if row["effective_to"] is not None
            else None
        ),
        source=row["source"],
        created_by=row["created_by"],
        note=row["note"],
        created_at=datetime.fromisoformat(row["created_at"]),
        closed_by=row["closed_by"],
        closed_at=(
            datetime.fromisoformat(row["closed_at"])
            if row["closed_at"] is not None
            else None
        ),
    )


class SQLiteReferenceFactCatalogMixin:
    def _connect(self) -> sqlite3.Connection:
        raise NotImplementedError

    def create_reference_fact(
        self,
        reference_fact: ReferenceFactCreate,
    ) -> ReferenceFactRecord:
        fact_id = reference_fact.fact_id or uuid.uuid4().hex
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            current = None
            if reference_fact.effective_to is None:
                current = connection.execute(
                    """
                    SELECT fact_id, effective_from
                    FROM reference_facts
                    WHERE entity_type = ? AND entity_key = ? AND attribute = ? AND effective_to IS NULL
                    ORDER BY effective_from DESC, fact_id DESC
                    LIMIT 1
                    """,
                    (
                        reference_fact.entity_type,
                        reference_fact.entity_key,
                        reference_fact.attribute,
                    ),
                ).fetchone()
            if current is not None:
                current_effective_from = date.fromisoformat(current["effective_from"])
                if current_effective_from >= reference_fact.effective_from:
                    raise ValueError(
                        "Reference fact effective_from must advance beyond the current version."
                    )
                closed_at = reference_fact.closed_at or reference_fact.created_at
                connection.execute(
                    """
                    UPDATE reference_facts
                    SET effective_to = ?,
                        closed_by = ?,
                        closed_at = ?
                    WHERE fact_id = ?
                    """,
                    (
                        (reference_fact.effective_from - timedelta(days=1)).isoformat(),
                        reference_fact.created_by,
                        closed_at.isoformat(),
                        current["fact_id"],
                    ),
                )
            connection.execute(
                """
                INSERT INTO reference_facts (
                    fact_id,
                    entity_type,
                    entity_key,
                    attribute,
                    value,
                    effective_from,
                    effective_to,
                    source,
                    created_by,
                    note,
                    created_at,
                    closed_by,
                    closed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    reference_fact.entity_type,
                    reference_fact.entity_key,
                    reference_fact.attribute,
                    reference_fact.value,
                    reference_fact.effective_from.isoformat(),
                    reference_fact.effective_to.isoformat()
                    if reference_fact.effective_to is not None
                    else None,
                    reference_fact.source,
                    reference_fact.created_by,
                    reference_fact.note,
                    reference_fact.created_at.isoformat(),
                    reference_fact.closed_by,
                    reference_fact.closed_at.isoformat()
                    if reference_fact.closed_at is not None
                    else None,
                ),
            )
            connection.commit()
        return self.get_reference_fact(fact_id)

    def close_reference_fact(
        self,
        fact_id: str,
        *,
        effective_to: date | None = None,
        closed_by: str | None = None,
        closed_at: datetime | None = None,
    ) -> ReferenceFactRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT fact_id, effective_from, effective_to
                FROM reference_facts
                WHERE fact_id = ?
                """,
                (fact_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown reference fact: {fact_id}")
            current_effective_from = date.fromisoformat(row["effective_from"])
            current_effective_to = (
                date.fromisoformat(row["effective_to"])
                if row["effective_to"] is not None
                else None
            )
            resolved_effective_to = effective_to or current_effective_to or date.today()
            if resolved_effective_to < current_effective_from:
                raise ValueError("Reference fact effective_to cannot precede effective_from.")
            connection.execute(
                """
                UPDATE reference_facts
                SET effective_to = ?,
                    closed_by = ?,
                    closed_at = ?
                WHERE fact_id = ?
                """,
                (
                    resolved_effective_to.isoformat(),
                    closed_by,
                    (closed_at or datetime.now(UTC)).isoformat(),
                    fact_id,
                ),
            )
            connection.commit()
        return self.get_reference_fact(fact_id)

    def get_reference_fact(self, fact_id: str) -> ReferenceFactRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    fact_id,
                    entity_type,
                    entity_key,
                    attribute,
                    value,
                    effective_from,
                    effective_to,
                    source,
                    created_by,
                    note,
                    created_at,
                    closed_by,
                    closed_at
                FROM reference_facts
                WHERE fact_id = ?
                """,
                (fact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown reference fact: {fact_id}")
        return _deserialize_reference_fact_row(row)

    def list_reference_facts(
        self,
        *,
        entity_type: str | None = None,
        entity_key: str | None = None,
        attribute: str | None = None,
        include_closed: bool = True,
    ) -> list[ReferenceFactRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if entity_type is not None:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        if entity_key is not None:
            clauses.append("entity_key = ?")
            params.append(entity_key)
        if attribute is not None:
            clauses.append("attribute = ?")
            params.append(attribute)
        if not include_closed:
            clauses.append("effective_to IS NULL")
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    fact_id,
                    entity_type,
                    entity_key,
                    attribute,
                    value,
                    effective_from,
                    effective_to,
                    source,
                    created_by,
                    note,
                    created_at,
                    closed_by,
                    closed_at
                FROM reference_facts
                {where_sql}
                ORDER BY entity_type, entity_key, attribute, effective_from, fact_id
                """,
                params,
            ).fetchall()
        return [_deserialize_reference_fact_row(row) for row in rows]
