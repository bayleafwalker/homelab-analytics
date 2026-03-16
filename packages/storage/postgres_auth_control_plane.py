from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

import psycopg
from psycopg.rows import dict_row

from packages.storage.auth_store import (
    LocalUserCreate,
    LocalUserRecord,
    ServiceTokenCreate,
    ServiceTokenRecord,
    UserRole,
    normalize_service_token_name,
    normalize_service_token_scopes,
    normalize_username,
)
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    AuthAuditEventRecord,
)
from packages.storage.control_plane_support import (
    _deserialize_auth_audit_event_row,
    _deserialize_local_user_row,
    _deserialize_service_token_row,
)


def _coerce_row_mapping(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise TypeError(f"Unsupported row value: {row!r}")
    return cast(dict[str, object], row)


class PostgresAuthControlPlaneMixin:
    def _connect(
        self,
        *,
        row_factory: object = None,
    ) -> psycopg.Connection[object]:
        raise NotImplementedError

    def create_local_user(self, user: LocalUserCreate) -> LocalUserRecord:
        username = normalize_username(user.username)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO local_users (
                    user_id, username, password_hash, role, enabled, created_at, last_login_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user.user_id,
                    username,
                    user.password_hash,
                    user.role.value,
                    user.enabled,
                    user.created_at,
                    user.last_login_at,
                ),
            )
        return self.get_local_user(user.user_id)

    def get_local_user(self, user_id: str) -> LocalUserRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT user_id, username, password_hash, role, enabled, created_at, last_login_at
                FROM local_users
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown local user: {user_id}")
        return _deserialize_local_user_row(_coerce_row_mapping(row))

    def get_local_user_by_username(self, username: str) -> LocalUserRecord:
        normalized_username = normalize_username(username)
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT user_id, username, password_hash, role, enabled, created_at, last_login_at
                FROM local_users
                WHERE username = %s
                """,
                (normalized_username,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown local user: {normalized_username}")
        return _deserialize_local_user_row(_coerce_row_mapping(row))

    def list_local_users(self, *, enabled_only: bool = False) -> list[LocalUserRecord]:
        sql = """
            SELECT user_id, username, password_hash, role, enabled, created_at, last_login_at
            FROM local_users
        """
        params: list[object] = []
        if enabled_only:
            sql += " WHERE enabled = %s"
            params.append(True)
        sql += " ORDER BY created_at, username"
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_deserialize_local_user_row(_coerce_row_mapping(row)) for row in rows]

    def update_local_user(
        self,
        user_id: str,
        *,
        role: UserRole | None = None,
        enabled: bool | None = None,
    ) -> LocalUserRecord:
        assignments: list[str] = []
        params: list[object] = []
        if role is not None:
            assignments.append("role = %s")
            params.append(role.value)
        if enabled is not None:
            assignments.append("enabled = %s")
            params.append(enabled)
        if not assignments:
            return self.get_local_user(user_id)
        params.append(user_id)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE local_users
                    SET {", ".join(assignments)}
                    WHERE user_id = %s
                    """,
                    params,
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"Unknown local user: {user_id}")
        return self.get_local_user(user_id)

    def update_local_user_password(
        self,
        user_id: str,
        *,
        password_hash: str,
    ) -> LocalUserRecord:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE local_users
                    SET password_hash = %s
                    WHERE user_id = %s
                    """,
                    (password_hash, user_id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"Unknown local user: {user_id}")
        return self.get_local_user(user_id)

    def record_local_user_login(
        self,
        user_id: str,
        *,
        logged_in_at: datetime | None = None,
    ) -> LocalUserRecord:
        resolved_logged_in_at = logged_in_at or datetime.now(UTC)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE local_users
                    SET last_login_at = %s
                    WHERE user_id = %s
                    """,
                    (resolved_logged_in_at, user_id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"Unknown local user: {user_id}")
        return self.get_local_user(user_id)

    def create_service_token(self, token: ServiceTokenCreate) -> ServiceTokenRecord:
        token_name = normalize_service_token_name(token.token_name)
        scopes = normalize_service_token_scopes(token.scopes)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO service_tokens (
                    token_id,
                    token_name,
                    token_secret_hash,
                    role,
                    scopes_json,
                    expires_at,
                    created_at,
                    last_used_at,
                    revoked_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                """,
                (
                    token.token_id,
                    token_name,
                    token.token_secret_hash,
                    token.role.value,
                    json.dumps(list(scopes)),
                    token.expires_at,
                    token.created_at,
                    token.last_used_at,
                    token.revoked_at,
                ),
            )
        return self.get_service_token(token.token_id)

    def get_service_token(self, token_id: str) -> ServiceTokenRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT
                    token_id,
                    token_name,
                    token_secret_hash,
                    role,
                    scopes_json,
                    expires_at,
                    created_at,
                    last_used_at,
                    revoked_at
                FROM service_tokens
                WHERE token_id = %s
                """,
                (token_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown service token: {token_id}")
        return _deserialize_service_token_row(_coerce_row_mapping(row))

    def list_service_tokens(
        self,
        *,
        include_revoked: bool = False,
    ) -> list[ServiceTokenRecord]:
        sql = """
            SELECT
                token_id,
                token_name,
                token_secret_hash,
                role,
                scopes_json,
                expires_at,
                created_at,
                last_used_at,
                revoked_at
            FROM service_tokens
        """
        params: list[object] = []
        if not include_revoked:
            sql += " WHERE revoked_at IS NULL"
        sql += " ORDER BY created_at, token_name"
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_deserialize_service_token_row(_coerce_row_mapping(row)) for row in rows]

    def revoke_service_token(
        self,
        token_id: str,
        *,
        revoked_at: datetime | None = None,
    ) -> ServiceTokenRecord:
        resolved_revoked_at = revoked_at or datetime.now(UTC)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE service_tokens
                    SET revoked_at = COALESCE(revoked_at, %s)
                    WHERE token_id = %s
                    """,
                    (resolved_revoked_at, token_id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"Unknown service token: {token_id}")
        return self.get_service_token(token_id)

    def record_service_token_use(
        self,
        token_id: str,
        *,
        used_at: datetime | None = None,
    ) -> ServiceTokenRecord:
        resolved_used_at = used_at or datetime.now(UTC)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE service_tokens
                    SET last_used_at = %s
                    WHERE token_id = %s
                    """,
                    (resolved_used_at, token_id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"Unknown service token: {token_id}")
        return self.get_service_token(token_id)

    def record_auth_audit_events(
        self,
        entries: tuple[AuthAuditEventCreate, ...],
    ) -> list[AuthAuditEventRecord]:
        if not entries:
            return []
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO auth_audit_events (
                        event_id,
                        event_type,
                        success,
                        actor_user_id,
                        actor_username,
                        subject_user_id,
                        subject_username,
                        remote_addr,
                        user_agent,
                        detail,
                        occurred_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            entry.event_id,
                            entry.event_type,
                            entry.success,
                            entry.actor_user_id,
                            entry.actor_username,
                            entry.subject_user_id,
                            normalize_username(entry.subject_username)
                            if entry.subject_username
                            else None,
                            entry.remote_addr,
                            entry.user_agent,
                            entry.detail,
                            entry.occurred_at,
                        )
                        for entry in entries
                    ],
                )
        recorded_ids = {entry.event_id for entry in entries}
        return [
            record
            for record in self.list_auth_audit_events(limit=len(entries))
            if record.event_id in recorded_ids
        ]

    def list_auth_audit_events(
        self,
        *,
        event_type: str | None = None,
        success: bool | None = None,
        actor_user_id: str | None = None,
        subject_user_id: str | None = None,
        subject_username: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[AuthAuditEventRecord]:
        sql = """
            SELECT
                event_id,
                event_type,
                success,
                actor_user_id,
                actor_username,
                subject_user_id,
                subject_username,
                remote_addr,
                user_agent,
                detail,
                occurred_at
            FROM auth_audit_events
        """
        clauses: list[str] = []
        params: list[object] = []
        if event_type is not None:
            clauses.append("event_type = %s")
            params.append(event_type)
        if success is not None:
            clauses.append("success = %s")
            params.append(success)
        if actor_user_id is not None:
            clauses.append("actor_user_id = %s")
            params.append(actor_user_id)
        if subject_user_id is not None:
            clauses.append("subject_user_id = %s")
            params.append(subject_user_id)
        if subject_username is not None:
            clauses.append("subject_username = %s")
            params.append(normalize_username(subject_username))
        if since is not None:
            clauses.append("occurred_at >= %s")
            params.append(since)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY occurred_at DESC, event_id DESC"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_deserialize_auth_audit_event_row(_coerce_row_mapping(row)) for row in rows]
