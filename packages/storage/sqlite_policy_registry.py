from __future__ import annotations

import sqlite3
from datetime import datetime

from packages.storage.control_plane import (
    PolicyDefinitionCreate,
    PolicyDefinitionRecord,
    PolicyDefinitionUpdate,
)


def _deserialize_policy_row(row: sqlite3.Row) -> PolicyDefinitionRecord:
    return PolicyDefinitionRecord(
        policy_id=row["policy_id"],
        display_name=row["display_name"],
        policy_kind=row["policy_kind"],
        rule_schema_version=row["rule_schema_version"],
        rule_document=row["rule_document"],
        enabled=bool(row["enabled"]),
        source_kind=row["source_kind"],
        description=row["description"],
        creator=row["creator"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class SQLitePolicyRegistryMixin:
    def _connect(self) -> sqlite3.Connection:
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.policy_id,
                    policy.display_name,
                    policy.description,
                    policy.policy_kind,
                    policy.rule_schema_version,
                    policy.rule_document,
                    int(policy.enabled),
                    policy.source_kind,
                    policy.creator,
                    policy.created_at.isoformat(),
                    policy.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_policy_definition(policy.policy_id)

    def get_policy_definition(self, policy_id: str) -> PolicyDefinitionRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT policy_id, display_name, description, policy_kind,
                       rule_schema_version, rule_document, enabled, source_kind,
                       creator, created_at, updated_at
                FROM policy_definitions
                WHERE policy_id = ?
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
            clauses.append("source_kind = ?")
            params.append(source_kind)
        if enabled_only:
            clauses.append("enabled = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT policy_id, display_name, description, policy_kind,
                       rule_schema_version, rule_document, enabled, source_kind,
                       creator, created_at, updated_at
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
            set_clauses.append("display_name = ?")
            params.append(update.display_name)
        if update.description is not None:
            set_clauses.append("description = ?")
            params.append(update.description)
        if update.policy_kind is not None:
            set_clauses.append("policy_kind = ?")
            params.append(update.policy_kind)
        if update.rule_schema_version is not None:
            set_clauses.append("rule_schema_version = ?")
            params.append(update.rule_schema_version)
        if update.rule_document is not None:
            set_clauses.append("rule_document = ?")
            params.append(update.rule_document)
        if update.enabled is not None:
            set_clauses.append("enabled = ?")
            params.append(int(update.enabled))
        set_clauses.append("updated_at = ?")
        params.append(update.updated_at.isoformat())
        params.append(policy_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE policy_definitions SET {', '.join(set_clauses)} WHERE policy_id = ?",
                params,
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown policy definition: {policy_id}")
        return self.get_policy_definition(policy_id)

    def delete_policy_definition(self, policy_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM policy_definitions WHERE policy_id = ?",
                (policy_id,),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown policy definition: {policy_id}")
