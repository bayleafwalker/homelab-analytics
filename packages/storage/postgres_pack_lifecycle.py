"""Postgres control-plane storage for pack lifecycle state and history.

Mirrors ``SQLitePackLifecycleMixin``; the schema lands via
``migrations/postgres/0018_pack_lifecycle.sql``. The compare-and-set in
``apply_pack_lifecycle_change`` locks the installation row with
``SELECT ... FOR UPDATE``; a concurrent first install loses on the primary key.
"""

from __future__ import annotations

from typing import Any

from psycopg import errors as psycopg_errors
from psycopg.rows import dict_row

from packages.storage.pack_lifecycle import (
    PackInstallationRecord,
    PackLifecycleConflictError,
    PackLifecycleEventCreate,
    PackLifecycleEventRecord,
    PackStateExpectation,
    matches_expectation,
    validate_event,
)
from packages.storage.sqlite_pack_lifecycle import (
    _EVENT_COLUMN_NAMES,
    _INSTALLATION_COLUMN_NAMES,
    EVENT_COLUMNS,
    INSTALLATION_COLUMNS,
    INSTALLATION_UPDATE_ASSIGNMENTS,
    deserialize_event,
    deserialize_installation,
    event_params,
    installation_params,
)

_INSTALLATION_PLACEHOLDERS = ", ".join("%s" for _ in _INSTALLATION_COLUMN_NAMES)
_EVENT_PLACEHOLDERS = ", ".join("%s" for _ in _EVENT_COLUMN_NAMES)


class PostgresPackLifecycleMixin:
    def _connect(self, *, row_factory: Any = None) -> Any:
        raise NotImplementedError

    def get_pack_installation(self, pack_key: str) -> PackInstallationRecord | None:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                f"SELECT {INSTALLATION_COLUMNS} FROM pack_installations WHERE pack_key = %s",
                (pack_key,),
            ).fetchone()
        return deserialize_installation(row) if row is not None else None

    def list_pack_installations(self) -> list[PackInstallationRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"SELECT {INSTALLATION_COLUMNS} FROM pack_installations ORDER BY pack_key"
            ).fetchall()
        return [deserialize_installation(row) for row in rows]

    def apply_pack_lifecycle_change(
        self,
        installation: PackInstallationRecord,
        event: PackLifecycleEventCreate,
        *,
        expected: PackStateExpectation,
    ) -> PackLifecycleEventRecord:
        validate_event(event)
        if event.pack_key != installation.pack_key:
            raise ValueError("Event and installation must name the same pack.")
        with self._connect(row_factory=dict_row) as connection:
            try:
                row = connection.execute(
                    f"SELECT {INSTALLATION_COLUMNS} FROM pack_installations"
                    " WHERE pack_key = %s FOR UPDATE",
                    (installation.pack_key,),
                ).fetchone()
                current = deserialize_installation(row) if row is not None else None
                if not matches_expectation(current, expected):
                    raise PackLifecycleConflictError(
                        f"Pack {installation.pack_key!r} changed since the plan was made."
                    )
                connection.execute(
                    f"INSERT INTO pack_installations ({INSTALLATION_COLUMNS})"
                    f" VALUES ({_INSTALLATION_PLACEHOLDERS})"
                    f" ON CONFLICT (pack_key) DO UPDATE SET {INSTALLATION_UPDATE_ASSIGNMENTS}"
                    if current is not None
                    else f"INSERT INTO pack_installations ({INSTALLATION_COLUMNS})"
                    f" VALUES ({_INSTALLATION_PLACEHOLDERS})",
                    installation_params(installation, native=True),
                )
                connection.execute(
                    f"INSERT INTO pack_lifecycle_events ({EVENT_COLUMNS})"
                    f" VALUES ({_EVENT_PLACEHOLDERS})",
                    event_params(event, native=True),
                )
                connection.commit()
            except psycopg_errors.UniqueViolation as exc:
                connection.rollback()
                raise PackLifecycleConflictError(
                    f"Pack {installation.pack_key!r} was installed concurrently."
                ) from exc
            except BaseException:
                connection.rollback()
                raise
        return self._get_pack_lifecycle_event(event.event_id)

    def record_pack_lifecycle_event(
        self, event: PackLifecycleEventCreate
    ) -> PackLifecycleEventRecord:
        validate_event(event)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO pack_lifecycle_events ({EVENT_COLUMNS})"
                f" VALUES ({_EVENT_PLACEHOLDERS})",
                event_params(event, native=True),
            )
            connection.commit()
        return self._get_pack_lifecycle_event(event.event_id)

    def list_pack_lifecycle_events(
        self, *, pack_key: str | None = None, limit: int | None = None
    ) -> list[PackLifecycleEventRecord]:
        where = "WHERE pack_key = %s" if pack_key is not None else ""
        params: list[object] = [pack_key] if pack_key is not None else []
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s"
            params.append(int(limit))
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"SELECT {EVENT_COLUMNS} FROM pack_lifecycle_events {where}"
                f" ORDER BY occurred_at DESC, event_id DESC{limit_clause}",
                params,
            ).fetchall()
        return [deserialize_event(row) for row in rows]

    def _get_pack_lifecycle_event(self, event_id: str) -> PackLifecycleEventRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                f"SELECT {EVENT_COLUMNS} FROM pack_lifecycle_events WHERE event_id = %s",
                (event_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown pack lifecycle event: {event_id}")
        return deserialize_event(row)
