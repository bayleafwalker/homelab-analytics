"""Dialect-neutral execution control plane: schedules, dispatch queue, worker heartbeats.

``SQLiteExecutionControlPlaneMixin`` and ``PostgresExecutionControlPlaneMixin`` only
provide ``_session()``; all queries, row mapping, and dispatch state transitions live
here so both backends share one implementation.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

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
    _coerce_datetime_value,
    _deserialize_schedule_dispatch_row,
    _deserialize_worker_heartbeat_row,
)
from packages.storage.ingestion_catalog import IngestionDefinitionRecord
from packages.storage.scheduling import next_cron_occurrence
from packages.storage.sql_dialect import DialectSession, row_datetime, row_int

EXECUTION_SCHEDULE_COLUMNS = (
    "schedule_id, target_kind, target_ref, cron_expression, timezone, enabled, archived,"
    " max_concurrency, next_due_at, last_enqueued_at, created_at"
)
SCHEDULE_DISPATCH_COLUMNS = (
    "dispatch_id, schedule_id, target_kind, target_ref, enqueued_at, status,"
    " started_at, completed_at, run_ids_json, failure_reason, worker_detail,"
    " claimed_by_worker_id, claimed_at, claim_expires_at"
)
_DISPATCH_SCHEDULE_COLUMNS = (
    "schedule_id, target_kind, target_ref, enabled, archived, max_concurrency"
)
_ACTIVE_DISPATCH_COUNT_SQL = """
    SELECT COUNT(*) AS active_count
    FROM schedule_dispatches
    WHERE schedule_id = ?
      AND status IN ('enqueued', 'running')
"""
_INSERT_DISPATCH_SQL = f"""
    INSERT INTO schedule_dispatches ({SCHEDULE_DISPATCH_COLUMNS})
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
_CLAIM_DISPATCH_SQL = """
    UPDATE schedule_dispatches
    SET status = 'running',
        started_at = ?,
        completed_at = NULL,
        failure_reason = NULL,
        worker_detail = ?,
        claimed_by_worker_id = ?,
        claimed_at = ?,
        claim_expires_at = ?
    WHERE dispatch_id = ?
      AND status = 'enqueued'
"""


def deserialize_execution_schedule_row(row: Mapping[str, object]) -> ExecutionScheduleRecord:
    return ExecutionScheduleRecord(
        schedule_id=str(row["schedule_id"]),
        target_kind=str(row["target_kind"]),
        target_ref=str(row["target_ref"]),
        cron_expression=str(row["cron_expression"]),
        timezone=str(row["timezone"]),
        enabled=bool(row["enabled"]),
        archived=bool(row["archived"]),
        max_concurrency=row_int(row["max_concurrency"]),
        next_due_at=_coerce_datetime_value(row["next_due_at"]),
        last_enqueued_at=_coerce_datetime_value(row["last_enqueued_at"]),
        created_at=row_datetime(row["created_at"]),
    )


def _enqueued_dispatch_record(
    *,
    dispatch_id: str,
    schedule_id: str,
    target_kind: str,
    target_ref: str,
    enqueued_at: datetime,
    worker_detail: str | None = None,
) -> ScheduleDispatchRecord:
    return ScheduleDispatchRecord(
        dispatch_id=dispatch_id,
        schedule_id=schedule_id,
        target_kind=target_kind,
        target_ref=target_ref,
        enqueued_at=enqueued_at,
        status="enqueued",
        started_at=None,
        completed_at=None,
        run_ids=(),
        failure_reason=None,
        worker_detail=worker_detail,
        claimed_by_worker_id=None,
        claimed_at=None,
        claim_expires_at=None,
    )


class ExecutionControlPlaneMixin:
    if TYPE_CHECKING:
        # Supplied by the dialect binding (SQLiteSessionMixin / PostgresSessionMixin);
        # declared for type checking only so it never shadows the binding in the MRO.
        def _session(
            self, *, write_lock: bool = False
        ) -> AbstractContextManager[DialectSession]: ...

        # Supplied by the asset-definition catalog mixin.
        def get_ingestion_definition(
            self,
            ingestion_definition_id: str,
        ) -> IngestionDefinitionRecord: ...

    # -- internal helpers -------------------------------------------------

    @staticmethod
    def _active_dispatch_count(session: DialectSession, schedule_id: str) -> int:
        row = session.fetchone(_ACTIVE_DISPATCH_COUNT_SQL, (schedule_id,))
        assert row is not None
        return row_int(row["active_count"])

    @staticmethod
    def _insert_enqueued_dispatch(
        session: DialectSession,
        *,
        schedule_id: str,
        target_kind: str,
        target_ref: str,
        enqueued_at: datetime,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord:
        dispatch_id = uuid.uuid4().hex[:16]
        session.execute(
            _INSERT_DISPATCH_SQL,
            (
                dispatch_id,
                schedule_id,
                target_kind,
                target_ref,
                session.dialect.encode_datetime(enqueued_at),
                "enqueued",
                None,
                None,
                json.dumps([]),
                None,
                worker_detail,
                None,
                None,
                None,
            ),
        )
        return _enqueued_dispatch_record(
            dispatch_id=dispatch_id,
            schedule_id=schedule_id,
            target_kind=target_kind,
            target_ref=target_ref,
            enqueued_at=enqueued_at,
            worker_detail=worker_detail,
        )

    @staticmethod
    def _claim_enqueued_dispatch(
        session: DialectSession,
        existing: ScheduleDispatchRecord,
        *,
        worker_id: str,
        claimed_at: datetime,
        claim_expires_at: datetime,
        worker_detail: str | None,
    ) -> int:
        encode = session.dialect.encode_datetime
        return session.execute(
            _CLAIM_DISPATCH_SQL,
            (
                encode(existing.started_at or claimed_at),
                worker_detail if worker_detail is not None else existing.worker_detail,
                worker_id,
                encode(claimed_at),
                encode(claim_expires_at),
                existing.dispatch_id,
            ),
        )

    def _validate_execution_schedule_target(
        self,
        target_kind: str,
        target_ref: str,
    ) -> None:
        if target_kind == "ingestion_definition":
            definition = self.get_ingestion_definition(target_ref)
            if definition.archived:
                raise ValueError(f"Ingestion definition is archived: {target_ref}")

    # -- execution schedules ----------------------------------------------

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
        with self._session() as session:
            dialect = session.dialect
            session.execute(
                f"""
                INSERT INTO execution_schedules ({EXECUTION_SCHEDULE_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule.schedule_id,
                    schedule.target_kind,
                    schedule.target_ref,
                    schedule.cron_expression,
                    schedule.timezone,
                    dialect.encode_bool(schedule.enabled),
                    dialect.encode_bool(schedule.archived),
                    schedule.max_concurrency,
                    dialect.encode_datetime(next_due_at),
                    dialect.encode_datetime(schedule.last_enqueued_at),
                    dialect.encode_datetime(schedule.created_at),
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
        with self._session() as session:
            dialect = session.dialect
            rowcount = session.execute(
                """
                UPDATE execution_schedules
                SET target_kind = ?,
                    target_ref = ?,
                    cron_expression = ?,
                    timezone = ?,
                    enabled = ?,
                    archived = ?,
                    max_concurrency = ?,
                    next_due_at = ?,
                    last_enqueued_at = ?
                WHERE schedule_id = ?
                """,
                (
                    schedule.target_kind,
                    schedule.target_ref,
                    schedule.cron_expression,
                    schedule.timezone,
                    dialect.encode_bool(schedule.enabled),
                    dialect.encode_bool(schedule.archived),
                    schedule.max_concurrency,
                    dialect.encode_datetime(next_due_at),
                    dialect.encode_datetime(schedule.last_enqueued_at),
                    schedule.schedule_id,
                ),
            )
        if rowcount == 0:
            raise KeyError(f"Unknown execution schedule: {schedule.schedule_id}")
        return self.get_execution_schedule(schedule.schedule_id)

    def get_execution_schedule(self, schedule_id: str) -> ExecutionScheduleRecord:
        with self._session() as session:
            row = session.fetchone(
                f"""
                SELECT {EXECUTION_SCHEDULE_COLUMNS}
                FROM execution_schedules
                WHERE schedule_id = ?
                """,
                (schedule_id,),
            )
        if row is None:
            raise KeyError(f"Unknown execution schedule: {schedule_id}")
        return deserialize_execution_schedule_row(row)

    def list_execution_schedules(
        self,
        *,
        enabled_only: bool = False,
        include_archived: bool = False,
    ) -> list[ExecutionScheduleRecord]:
        query = f"SELECT {EXECUTION_SCHEDULE_COLUMNS} FROM execution_schedules"
        clauses: list[str] = []
        if enabled_only:
            clauses.append("enabled = TRUE")
        if not include_archived:
            clauses.append("archived = FALSE")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, schedule_id"
        with self._session() as session:
            rows = session.fetchall(query)
        return [deserialize_execution_schedule_row(row) for row in rows]

    def set_execution_schedule_archived_state(
        self,
        schedule_id: str,
        *,
        archived: bool,
    ) -> ExecutionScheduleRecord:
        with self._session() as session:
            encoded = session.dialect.encode_bool(archived)
            rowcount = session.execute(
                """
                UPDATE execution_schedules
                SET archived = ?,
                    enabled = CASE WHEN ? THEN FALSE ELSE enabled END
                WHERE schedule_id = ?
                """,
                (encoded, encoded, schedule_id),
            )
        if rowcount == 0:
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
        with self._session() as session:
            rowcount = session.execute(
                "DELETE FROM execution_schedules WHERE schedule_id = ?",
                (schedule_id,),
            )
        if rowcount == 0:
            raise KeyError(f"Unknown execution schedule: {schedule_id}")

    def enqueue_due_execution_schedules(
        self,
        *,
        as_of: datetime | None = None,
        limit: int | None = None,
    ) -> list[ScheduleDispatchRecord]:
        dispatches: list[ScheduleDispatchRecord] = []
        resolved_as_of = as_of or datetime.now(UTC)
        with self._session() as session:
            encode = session.dialect.encode_datetime
            schedule_rows = session.fetchall(
                f"""
                SELECT {EXECUTION_SCHEDULE_COLUMNS}
                FROM execution_schedules
                WHERE enabled = TRUE
                  AND archived = FALSE
                  AND next_due_at IS NOT NULL
                  AND next_due_at <= ?
                ORDER BY next_due_at, schedule_id
                """,
                (encode(resolved_as_of),),
            )
            for row in schedule_rows:
                if limit is not None and len(dispatches) >= limit:
                    break
                schedule_id = str(row["schedule_id"])
                if self._active_dispatch_count(session, schedule_id) >= row_int(
                    row["max_concurrency"]
                ):
                    continue
                dispatches.append(
                    self._insert_enqueued_dispatch(
                        session,
                        schedule_id=schedule_id,
                        target_kind=str(row["target_kind"]),
                        target_ref=str(row["target_ref"]),
                        enqueued_at=resolved_as_of,
                    )
                )
                next_due_at = next_cron_occurrence(
                    str(row["cron_expression"]),
                    timezone=str(row["timezone"]),
                    after=resolved_as_of,
                )
                session.execute(
                    """
                    UPDATE execution_schedules
                    SET last_enqueued_at = ?, next_due_at = ?
                    WHERE schedule_id = ?
                    """,
                    (encode(resolved_as_of), encode(next_due_at), schedule_id),
                )
        return dispatches

    # -- schedule dispatches ----------------------------------------------

    def list_schedule_dispatches(
        self,
        *,
        schedule_id: str | None = None,
        status: str | None = None,
    ) -> list[ScheduleDispatchRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if schedule_id is not None:
            clauses.append("schedule_id = ?")
            params.append(schedule_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._session() as session:
            rows = session.fetchall(
                f"""
                SELECT {SCHEDULE_DISPATCH_COLUMNS}
                FROM schedule_dispatches
                {where_sql}
                ORDER BY enqueued_at DESC, dispatch_id DESC
                """,
                params,
            )
        return [_deserialize_schedule_dispatch_row(row) for row in rows]

    def get_schedule_dispatch(self, dispatch_id: str) -> ScheduleDispatchRecord:
        with self._session() as session:
            row = session.fetchone(
                f"""
                SELECT {SCHEDULE_DISPATCH_COLUMNS}
                FROM schedule_dispatches
                WHERE dispatch_id = ?
                """,
                (dispatch_id,),
            )
        if row is None:
            raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
        return _deserialize_schedule_dispatch_row(row)

    def create_schedule_dispatch(
        self,
        schedule_id: str,
        *,
        enqueued_at: datetime | None = None,
    ) -> ScheduleDispatchRecord:
        resolved_enqueued_at = enqueued_at or datetime.now(UTC)
        with self._session() as session:
            schedule_row = session.fetchone(
                f"""
                SELECT {_DISPATCH_SCHEDULE_COLUMNS}
                FROM execution_schedules
                WHERE schedule_id = ?
                """,
                (schedule_id,),
            )
            if schedule_row is None:
                raise KeyError(f"Unknown execution schedule: {schedule_id}")
            if bool(schedule_row["archived"]):
                raise ValueError(f"Execution schedule is archived: {schedule_id}")
            if not bool(schedule_row["enabled"]):
                raise ValueError(f"Execution schedule is disabled: {schedule_id}")
            if self._active_dispatch_count(session, schedule_id) >= row_int(
                schedule_row["max_concurrency"]
            ):
                raise ValueError(
                    f"Execution schedule already has max_concurrency active dispatches: {schedule_id}"
                )
            dispatch = self._insert_enqueued_dispatch(
                session,
                schedule_id=schedule_id,
                target_kind=str(schedule_row["target_kind"]),
                target_ref=str(schedule_row["target_ref"]),
                enqueued_at=resolved_enqueued_at,
            )
            session.execute(
                """
                UPDATE execution_schedules
                SET last_enqueued_at = ?
                WHERE schedule_id = ?
                """,
                (session.dialect.encode_datetime(resolved_enqueued_at), schedule_id),
            )
        return dispatch

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
        with self._session(write_lock=True) as session:
            row = session.fetchone(
                f"""
                SELECT {SCHEDULE_DISPATCH_COLUMNS}
                FROM schedule_dispatches
                WHERE dispatch_id = ?
                {session.dialect.row_lock_clause}
                """,
                (dispatch_id,),
            )
            if row is None:
                raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
            existing = _deserialize_schedule_dispatch_row(row)
            if existing.status != "enqueued":
                raise ValueError(
                    f"Schedule dispatch must be enqueued before claiming: {dispatch_id}"
                )
            rowcount = self._claim_enqueued_dispatch(
                session,
                existing,
                worker_id=worker_id,
                claimed_at=resolved_claimed_at,
                claim_expires_at=claim_expires_at,
                worker_detail=worker_detail,
            )
            if rowcount == 0:
                raise ValueError(f"Schedule dispatch could not be claimed: {dispatch_id}")
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
        with self._session(write_lock=True) as session:
            row = session.fetchone(
                f"""
                SELECT {SCHEDULE_DISPATCH_COLUMNS}
                FROM schedule_dispatches
                WHERE status = 'enqueued'
                ORDER BY enqueued_at, dispatch_id
                LIMIT 1
                {session.dialect.skip_locked_clause}
                """
            )
            if row is None:
                return None
            existing = _deserialize_schedule_dispatch_row(row)
            rowcount = self._claim_enqueued_dispatch(
                session,
                existing,
                worker_id=worker_id,
                claimed_at=resolved_claimed_at,
                claim_expires_at=claim_expires_at,
                worker_detail=worker_detail,
            )
            if rowcount == 0:
                return None
        return self.get_schedule_dispatch(existing.dispatch_id)

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
        with self._session(write_lock=True) as session:
            encode = session.dialect.encode_datetime
            row = session.fetchone(
                f"""
                SELECT {SCHEDULE_DISPATCH_COLUMNS}
                FROM schedule_dispatches
                WHERE dispatch_id = ?
                {session.dialect.row_lock_clause}
                """,
                (dispatch_id,),
            )
            if row is None:
                raise KeyError(f"Unknown schedule dispatch: {dispatch_id}")
            existing = _deserialize_schedule_dispatch_row(row)
            if existing.status != "running":
                raise ValueError(
                    f"Schedule dispatch must be running before lease renewal: {dispatch_id}"
                )
            if existing.claimed_by_worker_id != worker_id:
                raise ValueError(
                    "Schedule dispatch lease can only be renewed by the claiming worker: "
                    f"{dispatch_id}"
                )
            rowcount = session.execute(
                """
                UPDATE schedule_dispatches
                SET worker_detail = ?,
                    claimed_at = ?,
                    claim_expires_at = ?
                WHERE dispatch_id = ?
                  AND status = 'running'
                  AND claimed_by_worker_id = ?
                """,
                (
                    worker_detail if worker_detail is not None else existing.worker_detail,
                    encode(resolved_claimed_at),
                    encode(claim_expires_at),
                    dispatch_id,
                    worker_id,
                ),
            )
            if rowcount == 0:
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
        with self._session(write_lock=True) as session:
            encode = session.dialect.encode_datetime
            query = f"""
                SELECT {SCHEDULE_DISPATCH_COLUMNS}
                FROM schedule_dispatches
                WHERE status = 'running'
                  AND claim_expires_at IS NOT NULL
                  AND claim_expires_at < ?
                ORDER BY claim_expires_at, dispatch_id
            """
            parameters: list[object] = [encode(resolved_as_of)]
            if limit is not None:
                query += " LIMIT ?"
                parameters.append(limit)
            query += f" {session.dialect.skip_locked_clause}"
            for row in session.fetchall(query, parameters):
                existing = _deserialize_schedule_dispatch_row(row)
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
                rowcount = session.execute(
                    """
                    UPDATE schedule_dispatches
                    SET status = 'failed',
                        completed_at = ?,
                        failure_reason = ?,
                        worker_detail = ?,
                        claim_expires_at = NULL
                    WHERE dispatch_id = ?
                      AND status = 'running'
                      AND claim_expires_at IS NOT NULL
                      AND claim_expires_at < ?
                    """,
                    (
                        encode(resolved_as_of),
                        recovery_reason,
                        stale_detail,
                        existing.dispatch_id,
                        encode(resolved_as_of),
                    ),
                )
                if rowcount == 0:
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
                schedule_row = session.fetchone(
                    f"""
                    SELECT {_DISPATCH_SCHEDULE_COLUMNS}
                    FROM execution_schedules
                    WHERE schedule_id = ?
                    """,
                    (existing.schedule_id,),
                )
                replacement_dispatch: ScheduleDispatchRecord | None = None
                if (
                    schedule_row is not None
                    and not bool(schedule_row["archived"])
                    and bool(schedule_row["enabled"])
                    and self._active_dispatch_count(session, existing.schedule_id)
                    < row_int(schedule_row["max_concurrency"])
                ):
                    replacement_dispatch = self._insert_enqueued_dispatch(
                        session,
                        schedule_id=existing.schedule_id,
                        target_kind=str(schedule_row["target_kind"]),
                        target_ref=str(schedule_row["target_ref"]),
                        enqueued_at=resolved_as_of,
                        worker_detail=_build_requeued_dispatch_worker_detail(
                            existing,
                            recovered_at=resolved_as_of,
                            recovered_by_worker_id=recovered_by_worker_id,
                        ),
                    )
                    session.execute(
                        """
                        UPDATE execution_schedules
                        SET last_enqueued_at = ?
                        WHERE schedule_id = ?
                        """,
                        (encode(resolved_as_of), existing.schedule_id),
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
        resolved_worker_detail = (
            worker_detail if worker_detail is not None else existing.worker_detail
        )
        resolved_claimed_by_worker_id = existing.claimed_by_worker_id
        resolved_claimed_at = existing.claimed_at
        resolved_claim_expires_at: datetime | None = None
        resolved_started_at = started_at or existing.started_at
        resolved_completed_at = completed_at
        resolved_run_ids = run_ids if run_ids is not None else existing.run_ids
        resolved_failure_reason: str | None = None
        if status == "enqueued":
            resolved_started_at = None
            resolved_completed_at = None
            resolved_run_ids = ()
            resolved_worker_detail = worker_detail
            resolved_claimed_by_worker_id = None
            resolved_claimed_at = None
        elif status == "running":
            resolved_completed_at = None
            resolved_run_ids = run_ids or ()
            resolved_claim_expires_at = existing.claim_expires_at
        elif status == "failed":
            resolved_failure_reason = (
                failure_reason if failure_reason is not None else existing.failure_reason
            )
        query = """
            UPDATE schedule_dispatches
            SET status = ?,
                started_at = ?,
                completed_at = ?,
                run_ids_json = ?,
                failure_reason = ?,
                worker_detail = ?,
                claimed_by_worker_id = ?,
                claimed_at = ?,
                claim_expires_at = ?
            WHERE dispatch_id = ?
        """
        with self._session() as session:
            encode = session.dialect.encode_datetime
            parameters: list[object] = [
                status,
                encode(resolved_started_at),
                encode(resolved_completed_at),
                json.dumps(list(resolved_run_ids)),
                resolved_failure_reason,
                resolved_worker_detail,
                resolved_claimed_by_worker_id,
                encode(resolved_claimed_at),
                encode(resolved_claim_expires_at),
                dispatch_id,
            ]
            if expected_status is not None:
                query += " AND status = ?"
                parameters.append(expected_status)
            if expected_worker_id is not None:
                query += " AND claimed_by_worker_id = ?"
                parameters.append(expected_worker_id)
            rowcount = session.execute(query, parameters)
        if rowcount == 0:
            raise ValueError(f"Schedule dispatch could not be updated: {dispatch_id}")
        return self.get_schedule_dispatch(dispatch_id)

    # -- worker heartbeats ------------------------------------------------

    def record_worker_heartbeat(
        self,
        heartbeat: WorkerHeartbeatCreate,
    ) -> WorkerHeartbeatRecord:
        with self._session() as session:
            session.execute(
                """
                INSERT INTO worker_heartbeats (
                    worker_id, status, active_dispatch_id, detail, observed_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (worker_id) DO UPDATE SET
                    status = excluded.status,
                    active_dispatch_id = excluded.active_dispatch_id,
                    detail = excluded.detail,
                    observed_at = excluded.observed_at
                """,
                (
                    heartbeat.worker_id,
                    heartbeat.status,
                    heartbeat.active_dispatch_id,
                    heartbeat.detail,
                    session.dialect.encode_datetime(heartbeat.observed_at),
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
        with self._session() as session:
            rows = session.fetchall(
                """
                SELECT worker_id, status, active_dispatch_id, detail, observed_at
                FROM worker_heartbeats
                ORDER BY observed_at DESC, worker_id
                """
            )
        return [_deserialize_worker_heartbeat_row(row) for row in rows]
