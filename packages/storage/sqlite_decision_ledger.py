"""SQLite control-plane storage for the append-only decision ledger.

Schema: ``migrations/sqlite/0008_decision_ledger.sql`` (mirrored in the inline
bootstrap ``sqlite_control_plane_schema.py``).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from packages.storage.decision_ledger import (
    DecisionActor,
    DecisionFollowUpCreate,
    DecisionFollowUpRecord,
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


def _actor(row: Any) -> DecisionActor:
    return DecisionActor(
        actor=row["actor"],
        actor_role=row["actor_role"],
        actor_auth_provider=row["actor_auth_provider"],
        actor_authenticated=bool(row["actor_authenticated"]),
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
            connection.commit()
        return self.get_decision_record(record.decision_id)

    def get_decision_record(self, decision_id: str) -> DecisionRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"SELECT {_RECORD_COLUMNS} FROM decision_records WHERE decision_id = ?",
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
            clauses.append("decision_key = ?")
            params.append(decision_key)
        if subject_period is not None:
            clauses.append("subject_period = ?")
            params.append(subject_period)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT {_RECORD_COLUMNS} FROM decision_records {where}"
                " ORDER BY created_at DESC, decision_id",
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
