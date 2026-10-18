"""SQLite control-plane storage for pack lifecycle state and history.

Schema: ``migrations/sqlite/0011_pack_lifecycle.sql`` (mirrored in the inline
bootstrap ``sqlite_control_plane_schema.py``).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from packages.storage.pack_lifecycle import (
    PackInstallationRecord,
    PackLifecycleActor,
    PackLifecycleConflictError,
    PackLifecycleEventCreate,
    PackLifecycleEventRecord,
    PackStateExpectation,
    aware_utc,
    coerce_datetime,
    matches_expectation,
    validate_event,
)

_INSTALLATION_COLUMN_NAMES = (
    "pack_key",
    "display_name",
    "pack_kind",
    "trust_level",
    "installed_version",
    "previous_version",
    "pinned_version",
    "enabled",
    "extension_registry_source_id",
    "extension_registry_revision_id",
    "entry_digest",
    "previous_entry_digest",
    "available_versions",
    "compatibility_snapshot",
    "installed_at",
    "updated_at",
)
_EVENT_COLUMN_NAMES = (
    "event_id",
    "pack_key",
    "action",
    "outcome",
    "from_version",
    "to_version",
    "reason",
    "extension_registry_source_id",
    "extension_registry_revision_id",
    "entry_digest",
    "compatibility_snapshot",
    "plan",
    "actor",
    "actor_role",
    "actor_auth_provider",
    "actor_authenticated",
    "occurred_at",
)
INSTALLATION_COLUMNS = ", ".join(_INSTALLATION_COLUMN_NAMES)
EVENT_COLUMNS = ", ".join(_EVENT_COLUMN_NAMES)
INSTALLATION_UPDATE_ASSIGNMENTS = ", ".join(
    f"{name} = excluded.{name}" for name in _INSTALLATION_COLUMN_NAMES if name != "pack_key"
)


def deserialize_installation(row: Any) -> PackInstallationRecord:
    return PackInstallationRecord(
        pack_key=str(row["pack_key"]),
        display_name=str(row["display_name"]),
        pack_kind=str(row["pack_kind"]),
        trust_level=str(row["trust_level"]),
        installed_version=str(row["installed_version"]),
        previous_version=row["previous_version"],
        pinned_version=row["pinned_version"],
        enabled=bool(row["enabled"]),
        extension_registry_source_id=str(row["extension_registry_source_id"]),
        extension_registry_revision_id=str(row["extension_registry_revision_id"]),
        entry_digest=str(row["entry_digest"]),
        previous_entry_digest=row["previous_entry_digest"],
        available_versions=str(row["available_versions"]),
        compatibility_snapshot=str(row["compatibility_snapshot"]),
        installed_at=coerce_datetime(row["installed_at"]),
        updated_at=coerce_datetime(row["updated_at"]),
    )


def deserialize_event(row: Any) -> PackLifecycleEventRecord:
    return PackLifecycleEventRecord(
        event_id=str(row["event_id"]),
        pack_key=str(row["pack_key"]),
        action=str(row["action"]),
        outcome=str(row["outcome"]),
        from_version=row["from_version"],
        to_version=row["to_version"],
        reason=str(row["reason"]),
        extension_registry_source_id=row["extension_registry_source_id"],
        extension_registry_revision_id=row["extension_registry_revision_id"],
        entry_digest=row["entry_digest"],
        compatibility_snapshot=str(row["compatibility_snapshot"]),
        plan=str(row["plan"]),
        actor=PackLifecycleActor(
            actor=row["actor"],
            actor_role=row["actor_role"],
            actor_auth_provider=row["actor_auth_provider"],
            actor_authenticated=bool(row["actor_authenticated"]),
        ),
        occurred_at=coerce_datetime(row["occurred_at"]),
    )


def installation_params(record: PackInstallationRecord, *, native: bool) -> tuple[object, ...]:
    """Bind parameters in ``INSTALLATION_COLUMNS`` order.

    ``native`` keeps booleans and datetimes as Python objects (Postgres);
    otherwise they are stored as ``INTEGER``/ISO text (SQLite).
    """
    return (
        record.pack_key,
        record.display_name,
        record.pack_kind,
        record.trust_level,
        record.installed_version,
        record.previous_version,
        record.pinned_version,
        record.enabled if native else int(record.enabled),
        record.extension_registry_source_id,
        record.extension_registry_revision_id,
        record.entry_digest,
        record.previous_entry_digest,
        record.available_versions,
        record.compatibility_snapshot,
        aware_utc(record.installed_at) if native else aware_utc(record.installed_at).isoformat(),
        aware_utc(record.updated_at) if native else aware_utc(record.updated_at).isoformat(),
    )


def event_params(event: PackLifecycleEventCreate, *, native: bool) -> tuple[object, ...]:
    return (
        event.event_id,
        event.pack_key,
        event.action,
        event.outcome,
        event.from_version,
        event.to_version,
        event.reason,
        event.extension_registry_source_id,
        event.extension_registry_revision_id,
        event.entry_digest,
        event.compatibility_snapshot,
        event.plan,
        event.actor.actor,
        event.actor.actor_role,
        event.actor.actor_auth_provider,
        event.actor.actor_authenticated if native else int(event.actor.actor_authenticated),
        aware_utc(event.occurred_at) if native else aware_utc(event.occurred_at).isoformat(),
    )


class SQLitePackLifecycleMixin:
    def _connect(self) -> Any:
        raise NotImplementedError

    def get_pack_installation(self, pack_key: str) -> PackInstallationRecord | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"SELECT {INSTALLATION_COLUMNS} FROM pack_installations WHERE pack_key = ?",
                (pack_key,),
            ).fetchone()
        return deserialize_installation(row) if row is not None else None

    def list_pack_installations(self) -> list[PackInstallationRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
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
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    f"SELECT {INSTALLATION_COLUMNS} FROM pack_installations"
                    " WHERE pack_key = ?",
                    (installation.pack_key,),
                ).fetchone()
                current = deserialize_installation(row) if row is not None else None
                if not matches_expectation(current, expected):
                    raise PackLifecycleConflictError(
                        f"Pack {installation.pack_key!r} changed since the plan was made."
                    )
                connection.execute(
                    f"INSERT INTO pack_installations ({INSTALLATION_COLUMNS})"
                    f" VALUES ({', '.join('?' for _ in _INSTALLATION_COLUMN_NAMES)})"
                    f" ON CONFLICT (pack_key) DO UPDATE SET {INSTALLATION_UPDATE_ASSIGNMENTS}",
                    installation_params(installation, native=False),
                )
                connection.execute(
                    f"INSERT INTO pack_lifecycle_events ({EVENT_COLUMNS})"
                    f" VALUES ({', '.join('?' for _ in _EVENT_COLUMN_NAMES)})",
                    event_params(event, native=False),
                )
                connection.commit()
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
                f" VALUES ({', '.join('?' for _ in _EVENT_COLUMN_NAMES)})",
                event_params(event, native=False),
            )
            connection.commit()
        return self._get_pack_lifecycle_event(event.event_id)

    def list_pack_lifecycle_events(
        self, *, pack_key: str | None = None, limit: int | None = None
    ) -> list[PackLifecycleEventRecord]:
        where = "WHERE pack_key = ?" if pack_key is not None else ""
        params: list[object] = [pack_key] if pack_key is not None else []
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT ?"
            params.append(int(limit))
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT {EVENT_COLUMNS} FROM pack_lifecycle_events {where}"
                f" ORDER BY occurred_at DESC, event_id DESC{limit_clause}",
                params,
            ).fetchall()
        return [deserialize_event(row) for row in rows]

    def _get_pack_lifecycle_event(self, event_id: str) -> PackLifecycleEventRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"SELECT {EVENT_COLUMNS} FROM pack_lifecycle_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown pack lifecycle event: {event_id}")
        return deserialize_event(row)
