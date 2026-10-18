"""Postgres control-plane storage for the append-only decision ledger.

Mirrors ``SQLiteDecisionLedgerMixin``; the schema lands via
``migrations/postgres/0015_decision_ledger.sql``.
"""

from __future__ import annotations

from psycopg.rows import dict_row

from packages.storage.decision_ledger import (
    DecisionFollowUpCreate,
    DecisionFollowUpRecord,
    DecisionRecord,
    DecisionRecordCreate,
    aware_utc,
)
from packages.storage.sqlite_decision_ledger import (
    _FOLLOW_UP_COLUMNS,
    _RECORD_COLUMNS,
    deserialize_decision_record,
    deserialize_follow_up,
)


class PostgresDecisionLedgerMixin:
    def _connect(self, *, row_factory=None):
        raise NotImplementedError

    def create_decision_record(self, record: DecisionRecordCreate) -> DecisionRecord:
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO decision_records ({_RECORD_COLUMNS})
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    record.is_non_decision,
                    record.rationale,
                    record.evidence_gaps_acknowledged,
                    record.uncertainty,
                    record.actor.actor,
                    record.actor.actor_role,
                    record.actor.actor_auth_provider,
                    record.actor.actor_authenticated,
                    record.follow_up_due_on,
                    aware_utc(record.created_at),
                ),
            )
            connection.commit()
        return self.get_decision_record(record.decision_id)

    def get_decision_record(self, decision_id: str) -> DecisionRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                f"SELECT {_RECORD_COLUMNS} FROM decision_records WHERE decision_id = %s",
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
            clauses.append("decision_key = %s")
            params.append(decision_key)
        if subject_period is not None:
            clauses.append("subject_period = %s")
            params.append(subject_period)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
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
        with self._connect(row_factory=dict_row) as connection:
            connection.execute(
                f"""
                INSERT INTO decision_follow_ups ({_FOLLOW_UP_COLUMNS})
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    follow_up.follow_up_id,
                    follow_up.decision_id,
                    aware_utc(follow_up.observed_at),
                    follow_up.observation_period,
                    follow_up.realized_result,
                    follow_up.realized_value_eur,
                    follow_up.realized_value_status,
                    follow_up.evidence_effect,
                    follow_up.notes,
                    follow_up.actor.actor,
                    follow_up.actor.actor_role,
                    follow_up.actor.actor_auth_provider,
                    follow_up.actor.actor_authenticated,
                    aware_utc(follow_up.created_at),
                ),
            )
            connection.commit()
            row = connection.execute(
                f"SELECT {_FOLLOW_UP_COLUMNS} FROM decision_follow_ups WHERE follow_up_id = %s",
                (follow_up.follow_up_id,),
            ).fetchone()
        return deserialize_follow_up(row)

    def list_decision_follow_ups(self, decision_id: str) -> list[DecisionFollowUpRecord]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"SELECT {_FOLLOW_UP_COLUMNS} FROM decision_follow_ups"
                " WHERE decision_id = %s ORDER BY observed_at, follow_up_id",
                (decision_id,),
            ).fetchall()
        return [deserialize_follow_up(row) for row in rows]
