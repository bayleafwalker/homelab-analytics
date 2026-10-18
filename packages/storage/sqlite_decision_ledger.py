"""SQLite control-plane storage for the append-only decision ledger.

Schema: ``migrations/sqlite/0008_decision_ledger.sql`` and
``0010_decision_commitment_lifecycle.sql`` (mirrored in the inline bootstrap
``sqlite_control_plane_schema.py``).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from packages.storage.decision_ledger import (
    DecisionActor,
    DecisionCommitment,
    DecisionFollowUpCreate,
    DecisionFollowUpRecord,
    DecisionLifecycleEvent,
    DecisionLifecycleEventCreate,
    DecisionRecord,
    DecisionRecordCreate,
    aware_utc,
    coerce_date,
    coerce_datetime,
    coerce_decimal,
)

_RECORD_COLUMNS = """
    decision_id, decision_key, decision_version, subject_publication_key,
    subject_schema_version, subject_period, subject_row_ref, subject_verdict,
    lineage_reference, evidence_snapshot, outcome, is_non_decision, rationale,
    evidence_gaps_acknowledged, uncertainty, actor, actor_role,
    actor_auth_provider, actor_authenticated, follow_up_due_on, created_at
"""
_FOLLOW_UP_COLUMNS = """
    follow_up_id, decision_id, observed_at, observation_period, realized_result,
    realized_value_eur, realized_value_status, evidence_effect, notes, actor,
    actor_role, actor_auth_provider, actor_authenticated, created_at
"""

_COMMITMENT_COLUMN_NAMES: tuple[str, ...] = (
    "decision_id",
    "purpose",
    "owner_role",
    "owner_principal",
    "owner_verified",
    "baseline",
    "success_measure",
    "observation_window_start",
    "observation_window_end",
    "next_review_due_on",
    "review_cadence_days",
    "review_triggers",
    "stop_conditions",
    "stop_conditions_met",
    "evidence_fingerprint",
    "evidence_components",
    "created_at",
)
_COMMITMENT_COLUMNS = ", ".join(_COMMITMENT_COLUMN_NAMES)
_LIFECYCLE_EVENT_COLUMNS = """
    event_id, decision_id, event_kind, dedupe_key, reason_code, reason, details,
    actor, actor_role, actor_auth_provider, actor_authenticated, occurred_at,
    created_at
"""


def record_select_sql(where: str = "", order: str = "") -> str:
    """Decision records LEFT JOINed to their (optional) commitment terms."""
    record_columns = ", ".join(
        f"r.{name.strip()}" for name in _RECORD_COLUMNS.split(",") if name.strip()
    )
    commitment_columns = ", ".join(
        f"c.{name} AS commitment_{name}" for name in _COMMITMENT_COLUMN_NAMES
    )
    return (
        f"SELECT {record_columns}, {commitment_columns} FROM decision_records r"
        " LEFT JOIN decision_commitments c ON c.decision_id = r.decision_id"
        f" {where} {order}"
    )


def commitment_params(commitment: DecisionCommitment, *, native_types: bool) -> tuple[Any, ...]:
    """Insert parameters; ``native_types`` keeps dates/bools for Postgres."""

    def _date(value: Any) -> Any:
        return value if native_types else value.isoformat()

    created_at = aware_utc(commitment.created_at)
    return (
        commitment.decision_id,
        commitment.purpose,
        commitment.owner_role,
        commitment.owner_principal,
        commitment.owner_verified if native_types else int(commitment.owner_verified),
        commitment.baseline,
        commitment.success_measure,
        _date(commitment.observation_window_start),
        _date(commitment.observation_window_end),
        _date(commitment.next_review_due_on),
        commitment.review_cadence_days,
        commitment.review_triggers,
        commitment.stop_conditions,
        commitment.stop_conditions_met,
        commitment.evidence_fingerprint,
        commitment.evidence_components,
        created_at if native_types else created_at.isoformat(),
    )


def lifecycle_event_params(
    event: DecisionLifecycleEventCreate, *, native_types: bool
) -> tuple[Any, ...]:
    def _ts(value: Any) -> Any:
        return aware_utc(value) if native_types else aware_utc(value).isoformat()

    authenticated = event.actor.actor_authenticated
    return (
        event.event_id,
        event.decision_id,
        event.event_kind,
        event.dedupe_key,
        event.reason_code,
        event.reason,
        event.details,
        event.actor.actor,
        event.actor.actor_role,
        event.actor.actor_auth_provider,
        authenticated if native_types else int(authenticated),
        _ts(event.occurred_at),
        _ts(event.created_at),
    )


def _actor(row: Any) -> DecisionActor:
    return DecisionActor(
        actor=row["actor"],
        actor_role=row["actor_role"],
        actor_auth_provider=row["actor_auth_provider"],
        actor_authenticated=bool(row["actor_authenticated"]),
    )


def deserialize_commitment(row: Any) -> DecisionCommitment | None:
    """Commitment from a ``record_select_sql`` row; ``None`` for legacy records."""
    decision_id = row["commitment_decision_id"]
    if decision_id is None:
        return None
    return DecisionCommitment(
        decision_id=str(decision_id),
        purpose=str(row["commitment_purpose"]),
        owner_role=str(row["commitment_owner_role"]),
        owner_principal=row["commitment_owner_principal"],
        owner_verified=bool(row["commitment_owner_verified"]),
        baseline=str(row["commitment_baseline"]),
        success_measure=str(row["commitment_success_measure"]),
        observation_window_start=coerce_date(row["commitment_observation_window_start"]),
        observation_window_end=coerce_date(row["commitment_observation_window_end"]),
        next_review_due_on=coerce_date(row["commitment_next_review_due_on"]),
        review_cadence_days=int(row["commitment_review_cadence_days"]),
        review_triggers=str(row["commitment_review_triggers"]),
        stop_conditions=str(row["commitment_stop_conditions"]),
        stop_conditions_met=str(row["commitment_stop_conditions_met"]),
        evidence_fingerprint=str(row["commitment_evidence_fingerprint"]),
        evidence_components=str(row["commitment_evidence_components"]),
        created_at=coerce_datetime(row["commitment_created_at"]),
    )


def deserialize_lifecycle_event(row: Any) -> DecisionLifecycleEvent:
    return DecisionLifecycleEvent(
        event_id=str(row["event_id"]),
        decision_id=str(row["decision_id"]),
        event_kind=str(row["event_kind"]),
        dedupe_key=str(row["dedupe_key"]),
        reason_code=str(row["reason_code"]),
        reason=str(row["reason"]),
        details=str(row["details"]),
        actor=_actor(row),
        occurred_at=coerce_datetime(row["occurred_at"]),
        created_at=coerce_datetime(row["created_at"]),
    )


def deserialize_decision_record(row: Any) -> DecisionRecord:
    return DecisionRecord(
        decision_id=str(row["decision_id"]),
        decision_key=str(row["decision_key"]),
        decision_version=str(row["decision_version"]),
        subject_publication_key=str(row["subject_publication_key"]),
        subject_schema_version=str(row["subject_schema_version"]),
        subject_period=str(row["subject_period"]),
        subject_row_ref=str(row["subject_row_ref"]),
        subject_verdict=str(row["subject_verdict"]),
        lineage_reference=str(row["lineage_reference"]),
        evidence_snapshot=str(row["evidence_snapshot"]),
        outcome=str(row["outcome"]),
        is_non_decision=bool(row["is_non_decision"]),
        rationale=str(row["rationale"]),
        evidence_gaps_acknowledged=str(row["evidence_gaps_acknowledged"]),
        uncertainty=row["uncertainty"],
        actor=_actor(row),
        follow_up_due_on=coerce_date(row["follow_up_due_on"]),
        created_at=coerce_datetime(row["created_at"]),
        commitment=deserialize_commitment(row),
    )


def deserialize_follow_up(row: Any) -> DecisionFollowUpRecord:
    return DecisionFollowUpRecord(
        follow_up_id=str(row["follow_up_id"]),
        decision_id=str(row["decision_id"]),
        observed_at=coerce_datetime(row["observed_at"]),
        observation_period=row["observation_period"],
        realized_result=str(row["realized_result"]),
        realized_value_eur=coerce_decimal(row["realized_value_eur"]),
        realized_value_status=row["realized_value_status"],
        evidence_effect=str(row["evidence_effect"]),
        notes=row["notes"],
        actor=_actor(row),
        created_at=coerce_datetime(row["created_at"]),
    )


class SQLiteDecisionLedgerMixin:
    def _connect(self) -> sqlite3.Connection:
        raise NotImplementedError

    def create_decision_record(self, record: DecisionRecordCreate) -> DecisionRecord:
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO decision_records ({_RECORD_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.decision_id,
                    record.decision_key,
                    record.decision_version,
                    record.subject_publication_key,
                    record.subject_schema_version,
                    record.subject_period,
                    record.subject_row_ref,
                    record.subject_verdict,
                    record.lineage_reference,
                    record.evidence_snapshot,
                    record.outcome,
                    int(record.is_non_decision),
                    record.rationale,
                    record.evidence_gaps_acknowledged,
                    record.uncertainty,
                    record.actor.actor,
                    record.actor.actor_role,
                    record.actor.actor_auth_provider,
                    int(record.actor.actor_authenticated),
                    record.follow_up_due_on.isoformat(),
                    aware_utc(record.created_at).isoformat(),
                ),
            )
            if record.commitment is not None:
                connection.execute(
                    f"INSERT INTO decision_commitments ({_COMMITMENT_COLUMNS})"
                    f" VALUES ({', '.join('?' for _ in _COMMITMENT_COLUMN_NAMES)})",
                    commitment_params(record.commitment, native_types=False),
                )
            connection.commit()
        return self.get_decision_record(record.decision_id)

    def get_decision_record(self, decision_id: str) -> DecisionRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                record_select_sql("WHERE r.decision_id = ?"),
                (decision_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown decision record: {decision_id}")
        return deserialize_decision_record(row)

    def list_decision_records(
        self,
        *,
        decision_key: str | None = None,
        subject_period: str | None = None,
    ) -> list[DecisionRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if decision_key is not None:
            clauses.append("r.decision_key = ?")
            params.append(decision_key)
        if subject_period is not None:
            clauses.append("r.subject_period = ?")
            params.append(subject_period)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                record_select_sql(where, "ORDER BY r.created_at DESC, r.decision_id"),
                params,
            ).fetchall()
        return [deserialize_decision_record(row) for row in rows]

    def add_decision_follow_up(
        self, follow_up: DecisionFollowUpCreate
    ) -> DecisionFollowUpRecord:
        self.get_decision_record(follow_up.decision_id)
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO decision_follow_ups ({_FOLLOW_UP_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    follow_up.follow_up_id,
                    follow_up.decision_id,
                    aware_utc(follow_up.observed_at).isoformat(),
                    follow_up.observation_period,
                    follow_up.realized_result,
                    (
                        str(follow_up.realized_value_eur)
                        if follow_up.realized_value_eur is not None
                        else None
                    ),
                    follow_up.realized_value_status,
                    follow_up.evidence_effect,
                    follow_up.notes,
                    follow_up.actor.actor,
                    follow_up.actor.actor_role,
                    follow_up.actor.actor_auth_provider,
                    int(follow_up.actor.actor_authenticated),
                    aware_utc(follow_up.created_at).isoformat(),
                ),
            )
            connection.commit()
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"SELECT {_FOLLOW_UP_COLUMNS} FROM decision_follow_ups WHERE follow_up_id = ?",
                (follow_up.follow_up_id,),
            ).fetchone()
        return deserialize_follow_up(row)

    def list_decision_follow_ups(self, decision_id: str) -> list[DecisionFollowUpRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT {_FOLLOW_UP_COLUMNS} FROM decision_follow_ups"
                " WHERE decision_id = ? ORDER BY observed_at, follow_up_id",
                (decision_id,),
            ).fetchall()
        return [deserialize_follow_up(row) for row in rows]

    def append_decision_lifecycle_event(
        self, event: DecisionLifecycleEventCreate
    ) -> tuple[DecisionLifecycleEvent, bool]:
        self.get_decision_record(event.decision_id)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                f"INSERT INTO decision_lifecycle_events ({_LIFECYCLE_EVENT_COLUMNS})"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (dedupe_key) DO NOTHING",
                lifecycle_event_params(event, native_types=False),
            )
            created = cursor.rowcount == 1
            connection.commit()
            row = connection.execute(
                f"SELECT {_LIFECYCLE_EVENT_COLUMNS} FROM decision_lifecycle_events"
                " WHERE dedupe_key = ?",
                (event.dedupe_key,),
            ).fetchone()
        return deserialize_lifecycle_event(row), created

    def list_decision_lifecycle_events(self, decision_id: str) -> list[DecisionLifecycleEvent]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT {_LIFECYCLE_EVENT_COLUMNS} FROM decision_lifecycle_events"
                " WHERE decision_id = ? ORDER BY occurred_at, created_at, event_id",
                (decision_id,),
            ).fetchall()
        return [deserialize_lifecycle_event(row) for row in rows]
