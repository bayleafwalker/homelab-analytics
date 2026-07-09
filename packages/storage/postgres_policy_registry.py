from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from packages.storage.control_plane import (
    PolicyDefinitionCreate,
    PolicyDefinitionRecord,
    PolicyDefinitionUpdate,
)

_POLICY_COLUMNS = """
    policy_id, display_name, description, policy_kind,
    rule_schema_version, rule_document, enabled, source_kind,
    creator, created_at, updated_at
"""


def _coerce_datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _deserialize_policy_row(row: dict[str, Any]) -> PolicyDefinitionRecord:
    return PolicyDefinitionRecord(
        policy_id=str(row["policy_id"]),
        display_name=str(row["display_name"]),
        policy_kind=str(row["policy_kind"]),
        rule_schema_version=str(row["rule_schema_version"]),
        rule_document=str(row["rule_document"]),
        enabled=bool(row["enabled"]),
        source_kind=str(row["source_kind"]),
        description=str(row["description"]) if row["description"] is not None else None,
        creator=str(row["creator"]) if row["creator"] is not None else None,
        created_at=_coerce_datetime_value(row["created_at"]),
        updated_at=_coerce_datetime_value(row["updated_at"]),
    )


class PostgresPolicyRegistryMixin:
    """Policy definition CRUD against the Postgres control plane.

    Mirrors ``SQLitePolicyRegistryMixin``; the schema lands via
    ``migrations/postgres/0009_policy_registry.sql``.
    """

    def _connect(self, *, row_factory=None):
        raise NotImplementedError

    def create_policy_definition(
        self, policy: PolicyDefinitionCreate
    ) -> PolicyDefinitionRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO policy_definitions (
                    policy_id,
                    display_name,
                    description,
                    policy_kind,
                    rule_schema_version,
                    rule_document,
                    enabled,
                    source_kind,
                    creator,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    policy.policy_id,
                    policy.display_name,
                    policy.description,
                    policy.policy_kind,
                    policy.rule_schema_version,
                    policy.rule_document,
                    policy.enabled,
                    policy.source_kind,
                    policy.creator,
                    policy.created_at,
                    policy.updated_at,
                ),
            )
            connection.commit()
        return self.get_policy_definition(policy.policy_id)

    def get_policy_definition(self, policy_id: str) -> PolicyDefinitionRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                f"""
                SELECT {_POLICY_COLUMNS}
                FROM policy_definitions
                WHERE policy_id = %s
                """,
                (policy_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown policy definition: {policy_id}")
        return _deserialize_policy_row(row)

    def list_policy_definitions(
        self,
        *,
        source_kind: str | None = None,
        enabled_only: bool = False,
    ) -> list[PolicyDefinitionRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if source_kind is not None:
            clauses.append("source_kind = %s")
            params.append(source_kind)
        if enabled_only:
            clauses.append("enabled = TRUE")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"""
                SELECT {_POLICY_COLUMNS}
                FROM policy_definitions
                {where}
                ORDER BY created_at, policy_id
                """,
                params,
            ).fetchall()
        return [_deserialize_policy_row(row) for row in rows]

    def update_policy_definition(
        self, policy_id: str, update: PolicyDefinitionUpdate
    ) -> PolicyDefinitionRecord:
        set_clauses: list[str] = []
        params: list[object] = []
        if update.display_name is not None:
            set_clauses.append("display_name = %s")
            params.append(update.display_name)
        if update.description is not None:
            set_clauses.append("description = %s")
            params.append(update.description)
        if update.policy_kind is not None:
            set_clauses.append("policy_kind = %s")
            params.append(update.policy_kind)
        if update.rule_schema_version is not None:
            set_clauses.append("rule_schema_version = %s")
            params.append(update.rule_schema_version)
        if update.rule_document is not None:
            set_clauses.append("rule_document = %s")
            params.append(update.rule_document)
        if update.enabled is not None:
            set_clauses.append("enabled = %s")
            params.append(update.enabled)
        set_clauses.append("updated_at = %s")
        params.append(update.updated_at)
        params.append(policy_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE policy_definitions SET {', '.join(set_clauses)} WHERE policy_id = %s",
                params,
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown policy definition: {policy_id}")
        return self.get_policy_definition(policy_id)

    def delete_policy_definition(self, policy_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM policy_definitions WHERE policy_id = %s",
                (policy_id,),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown policy definition: {policy_id}")
