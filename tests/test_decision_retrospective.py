"""Retrospective decision entry: decided earlier, recorded now (HLA-K03 live gate)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from packages.application.use_cases.decision_ledger import (
    DecisionRequest,
    DecisionValidationError,
    FollowUpRequest,
    derive_commitment_state,
    load_serialized_decision,
    record_decision,
    record_follow_up,
)
from packages.application.use_cases.decision_outcome_reference import (
    latest_outcome_reference,
)
from tests.decision_lifecycle_support import (
    OPERATOR,
    SubjectTable,
    battery_row,
    definition_lookup,
    ledger,
)
from tests.test_decision_ledger import _client, _decision_body

ROOT = Path(__file__).resolve().parents[1]
KEY = "kotiakku_battery_plan_review"
RECORDED_AT = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
DECIDED_AT = datetime(2026, 7, 3, 8, 0, tzinfo=UTC)


def _decide(store: Any, **request: Any) -> Any:
    return record_decision(
        store,
        definition_lookup=definition_lookup,
        subject_reader=SubjectTable(battery_row(decision_month="2026-06")).read,
        request=DecisionRequest(
            decision_key=KEY,
            subject_period="2026-06",
            outcome="keep_current_plan",
            rationale="Kept the plan after June's bills.",
            **request,
        ),
        actor=OPERATOR,
        now=RECORDED_AT,
    )


def _follow_up(store: Any, decision_id: str, period: str, value: str, minute: int = 0) -> Any:
    observed = RECORDED_AT + timedelta(minutes=minute)
    return record_follow_up(
        store,
        decision_id=decision_id,
        request=FollowUpRequest(
            observed_at=observed,
            observation_period=period,
            realized_result=f"{period} bills reviewed.",
            evidence_effect="confirmed_decision",
            realized_value_eur=Decimal(value),
            realized_value_status="observed",
        ),
        actor=OPERATOR,
        now=observed,
    )


def test_retrospective_decision_windows_from_decided_at() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(
            store,
            decided_at=DECIDED_AT,
            retrospective_basis="Household note of 2026-07-03 after the June bill.",
        )
        assert record.is_retrospective
        assert record.created_at == RECORDED_AT
        assert record.commitment.observation_window_start.isoformat() == "2026-08-01"
        assert record.commitment.observation_window_end.isoformat() == "2026-08-31"
        decision = load_serialized_decision(store, record, today=RECORDED_AT.date())
        assert decision["entry_mode"] == "retrospective"
        assert decision["decided_at"] == DECIDED_AT.isoformat()
        assert decision["created_at"] == RECORDED_AT.isoformat()
        assert decision["retrospective_basis"].startswith("Household note")
        assert decision["lifecycle"]["state"] == "review_due"
        reference, _ = latest_outcome_reference(store, record.decision_id)
        assert reference["commitment_ref"]["decided_at"] == DECIDED_AT.isoformat()


def test_two_closed_periods_reviewed_without_waiting() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store, decided_at=DECIDED_AT, retrospective_basis="Contract note.")
        _follow_up(store, record.decision_id, "2026-08", "4.10")
        _follow_up(store, record.decision_id, "2026-09", "2.75", minute=5)
        decision = load_serialized_decision(store, record, today=RECORDED_AT.date())
        assert [item["observation_period"] for item in decision["follow_ups"]] == [
            "2026-08",
            "2026-09",
        ]
        assert [item["success"] for item in decision["follow_ups"]] == ["met", "met"]
        assert decision["lifecycle"]["state"] == "active"


def test_follow_up_cannot_precede_the_retrospective_decision() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store, decided_at=DECIDED_AT, retrospective_basis="Contract note.")
        with pytest.raises(DecisionValidationError, match="before the decision"):
            record_follow_up(
                store,
                decision_id=record.decision_id,
                request=FollowUpRequest(
                    observed_at=DECIDED_AT - timedelta(days=1),
                    realized_result="x",
                    evidence_effect="confirmed_decision",
                ),
                actor=OPERATOR,
                now=RECORDED_AT,
            )


@pytest.mark.parametrize(
    ("request_fields", "message"),
    [
        ({"decided_at": DECIDED_AT}, "needs retrospective_basis"),
        ({"retrospective_basis": "note"}, "requires decided_at"),
        ({"decided_at": RECORDED_AT + timedelta(hours=1), "retrospective_basis": "x"}, "future"),
        ({"decided_at": DECIDED_AT.replace(tzinfo=None), "retrospective_basis": "x"}, "offset"),
    ],
)
def test_invalid_retrospective_entries_are_refused(
    request_fields: dict[str, Any], message: str
) -> None:
    with TemporaryDirectory() as temp_dir:
        with pytest.raises(DecisionValidationError, match=message):
            _decide(ledger(temp_dir), **request_fields)


def test_contemporaneous_records_are_unchanged() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store)
        assert record.decided_at is None and not record.is_retrospective
        decision = load_serialized_decision(store, record, today=RECORDED_AT.date())
        assert decision["entry_mode"] == "contemporaneous"
        assert decision["decided_at"] == RECORDED_AT.isoformat()
        state = derive_commitment_state(record, [], [], today=RECORDED_AT.date())
        assert state["state"] == "active"


def test_migration_0015_and_postgres_0024_add_the_same_columns() -> None:
    sqlite_sql = (ROOT / "migrations/sqlite/0015_decision_record_decided_at.sql").read_text()
    postgres_sql = (ROOT / "migrations/postgres/0024_decision_record_decided_at.sql").read_text()

    def columns(sql: str) -> list[str]:
        return [
            line.split("ADD COLUMN")[1].replace("IF NOT EXISTS", "").split()[0]
            for line in sql.splitlines()
            if "ADD COLUMN" in line
        ]

    assert columns(sqlite_sql) == columns(postgres_sql) == ["decided_at", "retrospective_basis"]
    with TemporaryDirectory() as temp_dir:
        ledger(temp_dir)
        conn = sqlite3.connect(Path(temp_dir) / "config.db")
        names = {row[1] for row in conn.execute("PRAGMA table_info(decision_records)")}
        conn.close()
        assert {"decided_at", "retrospective_basis"} <= names


def test_api_records_a_retrospective_decision() -> None:
    with TemporaryDirectory() as temp_dir:
        client, row = _client(temp_dir)
        decided = (datetime.now(UTC) - timedelta(days=20)).replace(microsecond=0)
        response = client.post(
            "/control/decisions",
            json=_decision_body(
                row,
                decided_at=decided.isoformat(),
                retrospective_basis="Signed note from the household meeting.",
            ),
        )
        assert response.status_code == 201, response.text
        decision = response.json()["decision"]
        assert decision["entry_mode"] == "retrospective"
        assert decision["decided_at"] == decided.isoformat()
        refused = client.post(
            "/control/decisions",
            json=_decision_body(row, decided_at=decided.isoformat()),
        )
        assert refused.status_code == 422
