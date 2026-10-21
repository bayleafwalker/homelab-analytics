"""Postgres control-plane storage for the append-only decision ledger.

Mirrors ``SQLiteDecisionLedgerMixin``; the schema lands via
``migrations/postgres/0015_decision_ledger.sql`` and
``0017_decision_commitment_lifecycle.sql``.
"""

from __future__ import annotations

from psycopg.rows import dict_row

from packages.storage.decision_ledger import (
    DecisionFollowUpCreate,
    DecisionFollowUpRecord,
    DecisionLifecycleEvent,
    DecisionLifecycleEventCreate,
    DecisionRecord,
    DecisionRecordCreate,
    aware_utc,
)
from packages.storage.sqlite_decision_ledger import (
    _COMMITMENT_COLUMN_NAMES,
    _COMMITMENT_COLUMNS,
    _FOLLOW_UP_COLUMNS,
    _LIFECYCLE_EVENT_COLUMNS,
    _RECORD_COLUMNS,
    commitment_params,
    deserialize_decision_record,
    deserialize_follow_up,
    deserialize_lifecycle_event,
    follow_up_attribution_params,
    lifecycle_event_params,
    record_select_sql,
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
            if record.commitment is not None:
                connection.execute(
                    f"INSERT INTO decision_commitments ({_COMMITMENT_COLUMNS})"
                    f" VALUES ({', '.join('%s' for _ in _COMMITMENT_COLUMN_NAMES)})",
                    commitment_params(record.commitment, native_types=True),
                )
            connection.commit()
        return self.get_decision_record(record.decision_id)

    def get_decision_record(self, decision_id: str) -> DecisionRecord:
        with self._connect(row_factory=dict_row) as connection:
            row = connection.execute(
                record_select_sql("WHERE r.decision_id = %s"),
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
            clauses.append("r.decision_key = %s")
            params.append(decision_key)
        if subject_period is not None:
            clauses.append("r.subject_period = %s")
            params.append(subject_period)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                record_select_sql(where, "ORDER BY r.created_at DESC, r.decision_id"),
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s)
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
                    *follow_up_attribution_params(follow_up, decimal_as_text=False),
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

    def append_decision_lifecycle_event(
        self, event: DecisionLifecycleEventCreate
    ) -> tuple[DecisionLifecycleEvent, bool]:
        self.get_decision_record(event.decision_id)
        with self._connect(row_factory=dict_row) as connection:
            cursor = connection.execute(
                f"INSERT INTO decision_lifecycle_events ({_LIFECYCLE_EVENT_COLUMNS})"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (dedupe_key) DO NOTHING",
                lifecycle_event_params(event, native_types=True),
            )
            created = cursor.rowcount == 1
            connection.commit()
            row = connection.execute(
                f"SELECT {_LIFECYCLE_EVENT_COLUMNS} FROM decision_lifecycle_events"
                " WHERE dedupe_key = %s",
                (event.dedupe_key,),
            ).fetchone()
        return deserialize_lifecycle_event(row), created

    def list_decision_lifecycle_events(self, decision_id: str) -> list[DecisionLifecycleEvent]:
        with self._connect(row_factory=dict_row) as connection:
            rows = connection.execute(
                f"SELECT {_LIFECYCLE_EVENT_COLUMNS} FROM decision_lifecycle_events"
                " WHERE decision_id = %s ORDER BY occurred_at, created_at, event_id",
                (decision_id,),
            ).fetchall()
        return [deserialize_lifecycle_event(row) for row in rows]
