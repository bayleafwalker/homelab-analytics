from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import psycopg
from psycopg.rows import dict_row

from packages.storage.control_plane import (
    ExecutionScheduleCreate,
    ExecutionScheduleRecord,
    ScheduleDispatchRecord,
    ScheduleDispatchRecoveryRecord,
    WorkerHeartbeatCreate,
    WorkerHeartbeatRecord,
)
from packages.storage.control_plane_support import (
    _build_requeued_dispatch_worker_detail,
    _build_stale_dispatch_failure_reason,
    _build_stale_dispatch_worker_detail,
    _deserialize_schedule_dispatch_row,
    _deserialize_worker_heartbeat_row,
)
from packages.storage.ingestion_catalog import IngestionDefinitionRecord
from packages.storage.scheduling import next_cron_occurrence


def _coerce_datetime_value(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _coerce_int_value(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def _coerce_row_mapping(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise TypeError(f"Unsupported row value: {row!r}")
    return cast(dict[str, object], row)


def _deserialize_execution_schedule_row(
    row: dict[str, object],
) -> ExecutionScheduleRecord:
    return ExecutionScheduleRecord(
        schedule_id=str(row["schedule_id"]),
        target_kind=str(row["target_kind"]),
        target_ref=str(row["target_ref"]),
        cron_expression=str(row["cron_expression"]),
        timezone=str(row["timezone"]),
        enabled=bool(row["enabled"]),
        archived=bool(row["archived"]),
        max_concurrency=_coerce_int_value(row["max_concurrency"]),
        next_due_at=_coerce_datetime_value(row["next_due_at"]),
        last_enqueued_at=_coerce_datetime_value(row["last_enqueued_at"]),
        created_at=_coerce_datetime_value(row["created_at"]) or datetime.min,
    )


class PostgresExecutionControlPlaneMixin:
    def _connect(
        self,
        *,
        row_factory: object = None,
    ) -> psycopg.Connection[object]:
        raise NotImplementedError

    def get_ingestion_definition(
        self,
        ingestion_definition_id: str,
    ) -> IngestionDefinitionRecord:
        raise NotImplementedError

    def _validate_execution_schedule_target(
        self,
        target_kind: str,
        target_ref: str,
    ) -> None:
        if target_kind == "ingestion_definition":
            definition = self.get_ingestion_definition(target_ref)
            if definition.archived:
                raise ValueError(f"Ingestion definition is archived: {target_ref}")

    def create_execution_schedule(
        self,
        schedule: ExecutionScheduleCreate,
    ) -> ExecutionScheduleRecord:
        self._validate_execution_schedule_target(
            schedule.target_kind,
            schedule.target_ref,
        )
        next_due_at = schedule.next_due_at or next_cron_occurrence(
            schedule.cron_expression,
            timezone=schedule.timezone,
            after=schedule.created_at,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO execution_schedules (
                    schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,
                    max_concurrency, next_due_at, last_enqueued_at, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    schedule.schedule_id,
                    schedule.target_kind,
                    schedule.target_ref,
                    schedule.cron_expression,
                    schedule.timezone,
                    schedule.enabled,
                    schedule.archived,
                    schedule.max_concurrency,
                    next_due_at,
                    schedule.last_enqueued_at,
                    schedule.created_at,
                ),
            )
        return self.get_execution_schedule(schedule.schedule_id)

    def update_execution_schedule(
        self,
        schedule: ExecutionScheduleCreate,
    ) -> ExecutionScheduleRecord:
        self._validate_execution_schedule_target(
            schedule.target_kind,
            schedule.target_ref,
        )
        next_due_at = schedule.next_due_at or next_cron_occurrence(
            schedule.cron_expression,
            timezone=schedule.timezone,
            after=schedule.last_enqueued_at or schedule.created_at,
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE execution_schedules
                SET target_kind = %s,
                    target_ref = %s,
                    cron_expression = %s,
                    timezone = %s,
                    enabled = %s,
                    archived = %s,
                    max_concurrency = %s,
                    next_due_at = %s,
                    last_enqueued_at = %s
                WHERE schedule_id = %s
                """,
                (
                    schedule.target_kind,
                    schedule.target_ref,
                    schedule.cron_expression,
                    schedule.timezone,
                    schedule.enabled,
                    schedule.archived,
                    schedule.max_concurrency,
                    next_due_at,
                    schedule.last_enqueued_at,
                    schedule.schedule_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown execution schedule: {schedule.schedule_id}")
        return self.get_execution_schedule(schedule.schedule_id)

    def get_execution_schedule(self, schedule_id: str) -> ExecutionScheduleRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,
                       max_concurrency, next_due_at, last_enqueued_at, created_at
                FROM execution_schedules
                WHERE schedule_id = %s
                """,
                (schedule_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown execution schedule: {schedule_id}")
        return _deserialize_execution_schedule_row(_coerce_row_mapping(row))

    def list_execution_schedules(
        self,
        *,
        enabled_only: bool = False,
        include_archived: bool = False,
    ) -> list[ExecutionScheduleRecord]:
        sql = """
            SELECT schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,
                   max_concurrency, next_due_at, last_enqueued_at, created_at
            FROM execution_schedules
        """
        clauses: list[str] = []
        if enabled_only:
            clauses.append("enabled = TRUE")
        if not include_archived:
            clauses.append("archived = FALSE")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at, schedule_id"
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(sql).fetchall()
        return [_deserialize_execution_schedule_row(_coerce_row_mapping(row)) for row in rows]

    def set_execution_schedule_archived_state(
        self,
        schedule_id: str,
        *,
        archived: bool,
    ) -> ExecutionScheduleRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE execution_schedules
                SET archived = %s,
                    enabled = CASE WHEN %s THEN FALSE ELSE enabled END
                WHERE schedule_id = %s
                """,
                (archived, archived, schedule_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown execution schedule: {schedule_id}")
        return self.get_execution_schedule(schedule_id)

    def delete_execution_schedule(self, schedule_id: str) -> None:
        schedule = self.get_execution_schedule(schedule_id)
        if not schedule.archived:
            raise ValueError("Archive execution schedule before deleting it.")
        dispatches = self.list_schedule_dispatches(schedule_id=schedule_id)
        if dispatches:
            raise ValueError(
                "Cannot delete execution schedule while dispatch history exists: "
                + ", ".join(dispatch.dispatch_id for dispatch in dispatches)
            )
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM execution_schedules WHERE schedule_id = %s",
                (schedule_id,),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown execution schedule: {schedule_id}")

    def enqueue_due_execution_schedules(
        self,
        *,
        as_of: datetime | None = None,
        limit: int | None = None,
    ) -> list[ScheduleDispatchRecord]:
        dispatches: list[ScheduleDispatchRecord] = []
        resolved_as_of = as_of or datetime.now(UTC)
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,
                       max_concurrency, next_due_at, last_enqueued_at, created_at
                FROM execution_schedules
                WHERE enabled = TRUE
                  AND archived = FALSE
                  AND next_due_at IS NOT NULL
                  AND next_due_at <= %s
                ORDER BY next_due_at, schedule_id
                """,
                (resolved_as_of,),
            ).fetchall()
            for row_data in rows:
                row = _coerce_row_mapping(row_data)
                if limit is not None and len(dispatches) >= limit:
                    break
                count_row = _coerce_row_mapping(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS active_count
                        FROM schedule_dispatches
                        WHERE schedule_id = %s
                          AND status IN ('enqueued', 'running')
                        """,
                        (row["schedule_id"],),
                    ).fetchone()
                )
                active_count = _coerce_int_value(count_row["active_count"])
                if active_count >= _coerce_int_value(row["max_concurrency"]):
                    continue
                dispatch_id = uuid.uuid4().hex[:16]
                connection.execute(
                    """
                    INSERT INTO schedule_dispatches (
                        dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                        started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                        claimed_by_worker_id, claimed_at, claim_expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        dispatch_id,
                        row["schedule_id"],
                        row["target_kind"],
                        row["target_ref"],
                        resolved_as_of,
                        "enqueued",
                        None,
                        None,
                        "[]",
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                )
                next_due_at = next_cron_occurrence(
                    str(row["cron_expression"]),
                    timezone=str(row["timezone"]),
                    after=resolved_as_of,
                )
                connection.execute(
                    """
                    UPDATE execution_schedules
                    SET last_enqueued_at = %s, next_due_at = %s
                    WHERE schedule_id = %s
                    """,
                    (resolved_as_of, next_due_at, row["schedule_id"]),
                )
                dispatches.append(
                    ScheduleDispatchRecord(
                        dispatch_id=dispatch_id,
                        schedule_id=str(row["schedule_id"]),
                        target_kind=str(row["target_kind"]),
                        target_ref=str(row["target_ref"]),
                        enqueued_at=resolved_as_of,
                        status="enqueued",
                        started_at=None,
                        completed_at=None,
                        run_ids=(),
                        failure_reason=None,
                        worker_detail=None,
                        claimed_by_worker_id=None,
                        claimed_at=None,
                        claim_expires_at=None,
                    )
                )
        return dispatches

    def list_schedule_dispatches(
        self,
        *,
        schedule_id: str | None = None,
        status: str | None = None,
    ) -> list[ScheduleDispatchRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if schedule_id is not None:
            clauses.append("schedule_id = %s")
            params.append(schedule_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"""
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                {where_sql}
                ORDER BY enqueued_at DESC, dispatch_id DESC
                """,
                params,
            ).fetchall()
        return [_deserialize_schedule_dispatch_row(_coerce_row_mapping(row)) for row in rows]

    def get_schedule_dispatch(self, dispatch_id: str) -> ScheduleDispatchRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                WHERE dispatch_id = %s
                """,
                (dispatch_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
        return _deserialize_schedule_dispatch_row(_coerce_row_mapping(row))

    def create_schedule_dispatch(
        self,
        schedule_id: str,
        *,
        enqueued_at: datetime | None = None,
    ) -> ScheduleDispatchRecord:
        resolved_enqueued_at = enqueued_at or datetime.now(UTC)
        with self._connect(row_factory=dict_row) as connection:
            schedule_row_data = connection.execute(
                """
                SELECT schedule_id, target_kind, target_ref, enabled, archived, max_concurrency
                FROM execution_schedules
                WHERE schedule_id = %s
                """,
                (schedule_id,),
            ).fetchone()
            if schedule_row_data is None:
                raise KeyError(f"Unknown execution schedule: {schedule_id}")
            schedule_row = _coerce_row_mapping(schedule_row_data)
            if bool(schedule_row["archived"]):
                raise ValueError(f"Execution schedule is archived: {schedule_id}")
            if not bool(schedule_row["enabled"]):
                raise ValueError(f"Execution schedule is disabled: {schedule_id}")
            count_row = _coerce_row_mapping(
                connection.execute(
                    """
                    SELECT COUNT(*) AS active_count
                    FROM schedule_dispatches
                    WHERE schedule_id = %s
                      AND status IN ('enqueued', 'running')
                    """,
                    (schedule_id,),
                ).fetchone()
            )
            active_count = _coerce_int_value(count_row["active_count"])
            if active_count >= _coerce_int_value(schedule_row["max_concurrency"]):
                raise ValueError(
                    f"Execution schedule already has max_concurrency active dispatches: {schedule_id}"
                )
            dispatch_id = uuid.uuid4().hex[:16]
            connection.execute(
                """
                INSERT INTO schedule_dispatches (
                    dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                    started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                    claimed_by_worker_id, claimed_at, claim_expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    dispatch_id,
                    schedule_id,
                    schedule_row["target_kind"],
                    schedule_row["target_ref"],
                    resolved_enqueued_at,
                    "enqueued",
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            connection.execute(
                """
                UPDATE execution_schedules
                SET last_enqueued_at = %s
                WHERE schedule_id = %s
                """,
                (resolved_enqueued_at, schedule_id),
            )
        return ScheduleDispatchRecord(
            dispatch_id=dispatch_id,
            schedule_id=schedule_id,
            target_kind=str(schedule_row["target_kind"]),
            target_ref=str(schedule_row["target_ref"]),
            enqueued_at=resolved_enqueued_at,
            status="enqueued",
            started_at=None,
            completed_at=None,
            run_ids=(),
            failure_reason=None,
            worker_detail=None,
            claimed_by_worker_id=None,
            claimed_at=None,
            claim_expires_at=None,
        )

    def claim_schedule_dispatch(
        self,
        dispatch_id: str,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord:
        resolved_claimed_at = claimed_at or datetime.now(UTC)
        claim_expires_at = resolved_claimed_at + timedelta(seconds=lease_seconds)
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                WHERE dispatch_id = %s
                FOR UPDATE
                """,
                (dispatch_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
            existing = _deserialize_schedule_dispatch_row(_coerce_row_mapping(row))
            if existing.status != "enqueued":
                raise ValueError(
                    f"Schedule dispatch must be enqueued before claiming: {dispatch_id}"
                )
            cursor = connection.execute(
                """
                UPDATE schedule_dispatches
                SET status = %s,
                    started_at = %s,
                    completed_at = NULL,
                    failure_reason = NULL,
                    worker_detail = %s,
                    claimed_by_worker_id = %s,
                    claimed_at = %s,
                    claim_expires_at = %s
                WHERE dispatch_id = %s
                  AND status = 'enqueued'
                """,
                (
                    "running",
                    existing.started_at or resolved_claimed_at,
                    worker_detail if worker_detail is not None else existing.worker_detail,
                    worker_id,
                    resolved_claimed_at,
                    claim_expires_at,
                    dispatch_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError(
                    f"Schedule dispatch could not be claimed: {dispatch_id}"
                )
        return self.get_schedule_dispatch(dispatch_id)

    def claim_next_schedule_dispatch(
        self,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord | None:
        resolved_claimed_at = claimed_at or datetime.now(UTC)
        claim_expires_at = resolved_claimed_at + timedelta(seconds=lease_seconds)
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                WITH next_dispatch AS (
                    SELECT dispatch_id
                    FROM schedule_dispatches
                    WHERE status = 'enqueued'
                    ORDER BY enqueued_at, dispatch_id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE schedule_dispatches AS dispatch
                SET status = %s,
                    started_at = COALESCE(dispatch.started_at, %s),
                    completed_at = NULL,
                    failure_reason = NULL,
                    worker_detail = COALESCE(%s, dispatch.worker_detail),
                    claimed_by_worker_id = %s,
                    claimed_at = %s,
                    claim_expires_at = %s
                FROM next_dispatch
                WHERE dispatch.dispatch_id = next_dispatch.dispatch_id
                RETURNING dispatch.dispatch_id, dispatch.schedule_id, dispatch.target_kind,
                          dispatch.target_ref, dispatch.enqueued_at, dispatch.status,
                          dispatch.started_at, dispatch.completed_at, dispatch.run_ids_json,
                          dispatch.failure_reason, dispatch.worker_detail,
                          dispatch.claimed_by_worker_id, dispatch.claimed_at,
                          dispatch.claim_expires_at
                """,
                (
                    "running",
                    resolved_claimed_at,
                    worker_detail,
                    worker_id,
                    resolved_claimed_at,
                    claim_expires_at,
                ),
            ).fetchone()
        if row is None:
            return None
        return _deserialize_schedule_dispatch_row(_coerce_row_mapping(row))

    def renew_schedule_dispatch_claim(
        self,
        dispatch_id: str,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord:
        resolved_claimed_at = claimed_at or datetime.now(UTC)
        claim_expires_at = resolved_claimed_at + timedelta(seconds=lease_seconds)
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                WHERE dispatch_id = %s
                FOR UPDATE
                """,
                (dispatch_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
            existing = _deserialize_schedule_dispatch_row(_coerce_row_mapping(row))
            if existing.status != "running":
                raise ValueError(
                    f"Schedule dispatch must be running before lease renewal: {dispatch_id}"
                )
            if existing.claimed_by_worker_id != worker_id:
                raise ValueError(
                    "Schedule dispatch lease can only be renewed by the claiming worker: "
                    f"{dispatch_id}"
                )
            cursor = connection.execute(
                """
                UPDATE schedule_dispatches
                SET worker_detail = %s,
                    claimed_at = %s,
                    claim_expires_at = %s
                WHERE dispatch_id = %s
                  AND status = 'running'
                  AND claimed_by_worker_id = %s
                """,
                (
                    worker_detail if worker_detail is not None else existing.worker_detail,
                    resolved_claimed_at,
                    claim_expires_at,
                    dispatch_id,
                    worker_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError(
                    f"Schedule dispatch lease could not be renewed: {dispatch_id}"
                )
        return self.get_schedule_dispatch(dispatch_id)

    def requeue_expired_schedule_dispatches(
        self,
        *,
        as_of: datetime | None = None,
        limit: int | None = None,
        recovered_by_worker_id: str | None = None,
    ) -> list[ScheduleDispatchRecoveryRecord]:
        resolved_as_of = as_of or datetime.now(UTC)
        recoveries: list[ScheduleDispatchRecoveryRecord] = []
        with self._connect(row_factory=dict_row) as connection:
            query = """
                SELECT dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                       started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                       claimed_by_worker_id, claimed_at, claim_expires_at
                FROM schedule_dispatches
                WHERE status = 'running'
                  AND claim_expires_at IS NOT NULL
                  AND claim_expires_at < %s
                ORDER BY claim_expires_at, dispatch_id
                FOR UPDATE SKIP LOCKED
            """
            parameters: list[object] = [resolved_as_of]
            if limit is not None:
                query += " LIMIT %s"
                parameters.append(limit)
            rows = connection.execute(query, tuple(parameters)).fetchall()
            for row_data in rows:
                existing = _deserialize_schedule_dispatch_row(
                    _coerce_row_mapping(row_data)
                )
                recovery_reason = _build_stale_dispatch_failure_reason(
                    existing,
                    recovered_at=resolved_as_of,
                    recovered_by_worker_id=recovered_by_worker_id,
                )
                stale_detail = _build_stale_dispatch_worker_detail(
                    existing,
                    recovered_at=resolved_as_of,
                    recovered_by_worker_id=recovered_by_worker_id,
                )
                cursor = connection.execute(
                    """
                    UPDATE schedule_dispatches
                    SET status = %s,
                        completed_at = %s,
                        failure_reason = %s,
                        worker_detail = %s,
                        claim_expires_at = NULL
                    WHERE dispatch_id = %s
                      AND status = 'running'
                      AND claim_expires_at IS NOT NULL
                      AND claim_expires_at < %s
                    """,
                    (
                        "failed",
                        resolved_as_of,
                        recovery_reason,
                        stale_detail,
                        existing.dispatch_id,
                        resolved_as_of,
                    ),
                )
                if cursor.rowcount == 0:
                    continue
                stale_dispatch = ScheduleDispatchRecord(
                    dispatch_id=existing.dispatch_id,
                    schedule_id=existing.schedule_id,
                    target_kind=existing.target_kind,
                    target_ref=existing.target_ref,
                    enqueued_at=existing.enqueued_at,
                    status="failed",
                    started_at=existing.started_at,
                    completed_at=resolved_as_of,
                    run_ids=existing.run_ids,
                    failure_reason=recovery_reason,
                    worker_detail=stale_detail,
                    claimed_by_worker_id=existing.claimed_by_worker_id,
                    claimed_at=existing.claimed_at,
                    claim_expires_at=None,
                )
                schedule_row_data = connection.execute(
                    """
                    SELECT schedule_id, target_kind, target_ref, enabled, archived, max_concurrency
                    FROM execution_schedules
                    WHERE schedule_id = %s
                    """,
                    (existing.schedule_id,),
                ).fetchone()
                replacement_dispatch: ScheduleDispatchRecord | None = None
                if schedule_row_data is not None:
                    schedule_row = _coerce_row_mapping(schedule_row_data)
                    if not bool(schedule_row["archived"]) and bool(schedule_row["enabled"]):
                        count_row = _coerce_row_mapping(
                            connection.execute(
                                """
                                SELECT COUNT(*) AS active_count
                                FROM schedule_dispatches
                                WHERE schedule_id = %s
                                  AND status IN ('enqueued', 'running')
                                """,
                                (existing.schedule_id,),
                            ).fetchone()
                        )
                        active_count = _coerce_int_value(count_row["active_count"])
                        if active_count < _coerce_int_value(schedule_row["max_concurrency"]):
                            replacement_dispatch_id = uuid.uuid4().hex[:16]
                            replacement_detail = _build_requeued_dispatch_worker_detail(
                                existing,
                                recovered_at=resolved_as_of,
                                recovered_by_worker_id=recovered_by_worker_id,
                            )
                            connection.execute(
                                """
                                INSERT INTO schedule_dispatches (
                                    dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,
                                    started_at, completed_at, run_ids_json, failure_reason, worker_detail,
                                    claimed_by_worker_id, claimed_at, claim_expires_at
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    replacement_dispatch_id,
                                    existing.schedule_id,
                                    schedule_row["target_kind"],
                                    schedule_row["target_ref"],
                                    resolved_as_of,
                                    "enqueued",
                                    None,
                                    None,
                                    "[]",
                                    None,
                                    replacement_detail,
                                    None,
                                    None,
                                    None,
                                ),
                            )
                            connection.execute(
                                """
                                UPDATE execution_schedules
                                SET last_enqueued_at = %s
                                WHERE schedule_id = %s
                                """,
                                (resolved_as_of, existing.schedule_id),
                            )
                            replacement_dispatch = ScheduleDispatchRecord(
                                dispatch_id=replacement_dispatch_id,
                                schedule_id=existing.schedule_id,
                                target_kind=str(schedule_row["target_kind"]),
                                target_ref=str(schedule_row["target_ref"]),
                                enqueued_at=resolved_as_of,
                                status="enqueued",
                                started_at=None,
                                completed_at=None,
                                run_ids=(),
                                failure_reason=None,
                                worker_detail=replacement_detail,
                                claimed_by_worker_id=None,
                                claimed_at=None,
                                claim_expires_at=None,
                            )
                recoveries.append(
                    ScheduleDispatchRecoveryRecord(
                        stale_dispatch=stale_dispatch,
                        replacement_dispatch=replacement_dispatch,
                        recovered_at=resolved_as_of,
                        recovered_by_worker_id=recovered_by_worker_id,
                    )
                )
        return recoveries

    def mark_schedule_dispatch_status(
        self,
        dispatch_id: str,
        *,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        run_ids: tuple[str, ...] | None = None,
        failure_reason: str | None = None,
        worker_detail: str | None = None,
        expected_status: str | None = None,
        expected_worker_id: str | None = None,
    ) -> ScheduleDispatchRecord:
        existing = self.get_schedule_dispatch(dispatch_id)
        if expected_status is not None and existing.status != expected_status:
            raise ValueError(
                "Schedule dispatch status changed before update: "
                f"{dispatch_id} expected {expected_status}, found {existing.status}"
            )
        if (
            expected_worker_id is not None
            and existing.claimed_by_worker_id != expected_worker_id
        ):
            raise ValueError(
                "Schedule dispatch claim changed before update: "
                f"{dispatch_id} expected worker {expected_worker_id}, "
                f"found {existing.claimed_by_worker_id}"
            )
        if status == "enqueued":
            resolved_started_at = None
            resolved_completed_at = None
            resolved_run_ids: tuple[str, ...] = ()
            resolved_failure_reason = None
            resolved_worker_detail = worker_detail
            resolved_claimed_by_worker_id = None
            resolved_claimed_at = None
            resolved_claim_expires_at = None
        elif status == "running":
            resolved_started_at = started_at or existing.started_at
            resolved_completed_at = None
            resolved_run_ids = run_ids or ()
            resolved_failure_reason = None
            resolved_worker_detail = (
                worker_detail if worker_detail is not None else existing.worker_detail
            )
            resolved_claimed_by_worker_id = existing.claimed_by_worker_id
            resolved_claimed_at = existing.claimed_at
            resolved_claim_expires_at = existing.claim_expires_at
        elif status == "failed":
            resolved_started_at = started_at or existing.started_at
            resolved_completed_at = completed_at
            resolved_run_ids = run_ids if run_ids is not None else existing.run_ids
            resolved_failure_reason = (
                failure_reason
                if failure_reason is not None
                else existing.failure_reason
            )
            resolved_worker_detail = (
                worker_detail if worker_detail is not None else existing.worker_detail
            )
            resolved_claimed_by_worker_id = existing.claimed_by_worker_id
            resolved_claimed_at = existing.claimed_at
            resolved_claim_expires_at = None
        else:
            resolved_started_at = started_at or existing.started_at
            resolved_completed_at = completed_at
            resolved_run_ids = run_ids if run_ids is not None else existing.run_ids
            resolved_failure_reason = None
            resolved_worker_detail = (
                worker_detail if worker_detail is not None else existing.worker_detail
            )
            resolved_claimed_by_worker_id = existing.claimed_by_worker_id
            resolved_claimed_at = existing.claimed_at
            resolved_claim_expires_at = None
        with self._connect() as connection:
            query = """
                UPDATE schedule_dispatches
                SET status = %s,
                    started_at = %s,
                    completed_at = %s,
                    run_ids_json = %s,
                    failure_reason = %s,
                    worker_detail = %s,
                    claimed_by_worker_id = %s,
                    claimed_at = %s,
                    claim_expires_at = %s
                WHERE dispatch_id = %s
            """
            parameters: list[object] = [
                status,
                resolved_started_at,
                resolved_completed_at,
                json.dumps(list(resolved_run_ids)),
                resolved_failure_reason,
                resolved_worker_detail,
                resolved_claimed_by_worker_id,
                resolved_claimed_at,
                resolved_claim_expires_at,
                dispatch_id,
            ]
            if expected_status is not None:
                query += " AND status = %s"
                parameters.append(expected_status)
            if expected_worker_id is not None:
                query += " AND claimed_by_worker_id = %s"
                parameters.append(expected_worker_id)
            cursor = connection.execute(
                query,
                tuple(parameters),
            )
        if cursor.rowcount == 0:
            raise ValueError(f"Schedule dispatch could not be updated: {dispatch_id}")
        return self.get_schedule_dispatch(dispatch_id)

    def record_worker_heartbeat(
        self,
        heartbeat: WorkerHeartbeatCreate,
    ) -> WorkerHeartbeatRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO worker_heartbeats (
                    worker_id, status, active_dispatch_id, detail, observed_at
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (worker_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    active_dispatch_id = EXCLUDED.active_dispatch_id,
                    detail = EXCLUDED.detail,
                    observed_at = EXCLUDED.observed_at
                """,
                (
                    heartbeat.worker_id,
                    heartbeat.status,
                    heartbeat.active_dispatch_id,
                    heartbeat.detail,
                    heartbeat.observed_at,
                ),
            )
        return WorkerHeartbeatRecord(
            worker_id=heartbeat.worker_id,
            status=heartbeat.status,
            active_dispatch_id=heartbeat.active_dispatch_id,
            detail=heartbeat.detail,
            observed_at=heartbeat.observed_at,
        )

    def list_worker_heartbeats(self) -> list[WorkerHeartbeatRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT worker_id, status, active_dispatch_id, detail, observed_at
                FROM worker_heartbeats
                ORDER BY observed_at DESC, worker_id
                """
            ).fetchall()
        return [_deserialize_worker_heartbeat_row(_coerce_row_mapping(row)) for row in rows]
