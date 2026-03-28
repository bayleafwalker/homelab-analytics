from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import cast

import psycopg
from psycopg.rows import dict_row

from packages.storage.ingestion_catalog import (
    ReferenceFactCreate,
    ReferenceFactRecord,
)


def _deserialize_reference_fact_row(row: dict[str, object]) -> ReferenceFactRecord:
    return ReferenceFactRecord(
        fact_id=str(row["fact_id"]),
        entity_type=str(row["entity_type"]),
        entity_key=str(row["entity_key"]),
        attribute=str(row["attribute"]),
        value=str(row["value"]),
        effective_from=_coerce_date_value(row["effective_from"]),
        effective_to=(
            _coerce_date_value(row["effective_to"])
            if row["effective_to"] is not None
            else None
        ),
        source=str(row["source"]),
        created_by=str(row["created_by"]),
        note=str(row["note"]) if row["note"] is not None else None,
        created_at=_coerce_datetime_value(row["created_at"]),
        closed_by=str(row["closed_by"]) if row["closed_by"] is not None else None,
        closed_at=(
            _coerce_datetime_value(row["closed_at"])
            if row["closed_at"] is not None
            else None
        ),
    )


def _coerce_datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _coerce_date_value(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date value: {value!r}")


def _coerce_row_mapping(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise TypeError(f"Unsupported row value: {row!r}")
    return cast(dict[str, object], row)


class PostgresReferenceFactCatalogMixin:
    def _connect(
        self,
        *,
        row_factory: object = None,
    ) -> psycopg.Connection[object]:
        raise NotImplementedError

    def create_reference_fact(
        self,
        reference_fact: ReferenceFactCreate,
    ) -> ReferenceFactRecord:
        fact_id = reference_fact.fact_id or uuid.uuid4().hex
        with self._connect(row_factory=dict_row) as connection:
            current = None
            if reference_fact.effective_to is None:
                current = connection.execute(
                    """
                    SELECT fact_id, effective_from
                    FROM reference_facts
                    WHERE entity_type = %s
                      AND entity_key = %s
                      AND attribute = %s
                      AND effective_to IS NULL
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
                    current_row = _coerce_row_mapping(current)
                    current_effective_from = _coerce_date_value(
                        current_row["effective_from"]
                    )
                    if current_effective_from >= reference_fact.effective_from:
                        raise ValueError(
                            "Reference fact effective_from must advance beyond the current version."
                        )
                    connection.execute(
                        """
                        UPDATE reference_facts
                        SET effective_to = %s,
                            closed_by = %s,
                            closed_at = %s
                        WHERE fact_id = %s
                        """,
                        (
                            reference_fact.effective_from - timedelta(days=1),
                            reference_fact.created_by,
                            reference_fact.closed_at or reference_fact.created_at,
                            current_row["fact_id"],
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    fact_id,
                    reference_fact.entity_type,
                    reference_fact.entity_key,
                    reference_fact.attribute,
                    reference_fact.value,
                    reference_fact.effective_from,
                    reference_fact.effective_to,
                    reference_fact.source,
                    reference_fact.created_by,
                    reference_fact.note,
                    reference_fact.created_at,
                    reference_fact.closed_by,
                    reference_fact.closed_at,
                ),
            )
        return self.get_reference_fact(fact_id)

    def close_reference_fact(
        self,
        fact_id: str,
        *,
        effective_to: date | None = None,
        closed_by: str | None = None,
        closed_at: datetime | None = None,
    ) -> ReferenceFactRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT fact_id, effective_from, effective_to
                FROM reference_facts
                WHERE fact_id = %s
                """,
                (fact_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown reference fact: {fact_id}")
            current_row = _coerce_row_mapping(row)
            current_effective_from = _coerce_date_value(current_row["effective_from"])
            current_effective_to = (
                _coerce_date_value(current_row["effective_to"])
                if current_row["effective_to"] is not None
                else None
            )
            resolved_effective_to = effective_to or current_effective_to or date.today()
            if resolved_effective_to < current_effective_from:
                raise ValueError("Reference fact effective_to cannot precede effective_from.")
            connection.execute(
                """
                UPDATE reference_facts
                SET effective_to = %s,
                    closed_by = %s,
                    closed_at = %s
                WHERE fact_id = %s
                """,
                (
                    resolved_effective_to,
                    closed_by,
                    closed_at or datetime.now(UTC),
                    fact_id,
                ),
            )
        return self.get_reference_fact(fact_id)

    def get_reference_fact(self, fact_id: str) -> ReferenceFactRecord:
        with self._connect(row_factory=dict_row) as connection:
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
                WHERE fact_id = %s
                """,
                (fact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown reference fact: {fact_id}")
        return _deserialize_reference_fact_row(_coerce_row_mapping(row))

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
            clauses.append("entity_type = %s")
            params.append(entity_type)
        if entity_key is not None:
            clauses.append("entity_key = %s")
            params.append(entity_key)
        if attribute is not None:
            clauses.append("attribute = %s")
            params.append(attribute)
        if not include_closed:
            clauses.append("effective_to IS NULL")
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
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
        return [_deserialize_reference_fact_row(_coerce_row_mapping(row)) for row in rows]
