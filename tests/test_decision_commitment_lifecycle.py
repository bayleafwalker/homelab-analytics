"""HLA-K01: commitment lifecycle on the decision ledger.

Fixtures demonstrate that success, timed review, source-triggered review,
operator stop and missing evidence produce distinguishable states; stopped
commitments drop out of the proactive review queue while their history stays
readable; owner, window and stop conditions are enforced at record time.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from packages.application.use_cases.decision_evidence_trace import (
    trace_evidence_corrections,
)
from packages.application.use_cases.decision_ledger import (
    DecisionAuthorizationError,
    DecisionRequest,
    DecisionStateConflictError,
    DecisionValidationError,
    FollowUpRequest,
    actor_from_principal,
    list_commitment_reviews,
    load_serialized_decision,
    record_decision,
    record_follow_up,
    reopen_commitment,
    stop_commitment,
)
from packages.domains.utilities.battery_plan_decision import BATTERY_PLAN_DECISION
from packages.pipelines.household_decisions import snapshot_evidence_components
from packages.platform.decision_definitions import (
    DecisionObservationWindow,
    DecisionOwner,
    DecisionReviewTrigger,
)
from packages.storage.migration_runner import apply_pending_sqlite_migrations
from tests.decision_lifecycle_support import (
    DECIDED_AT,
    OPERATOR,
    READER,
    SubjectTable,
    battery_row,
    definition_lookup,
    ledger,
)

ROOT = Path(__file__).resolve().parents[1]
KEY = BATTERY_PLAN_DECISION.decision_key


def _record(store, table, *, outcome="keep_current_plan", actor=OPERATOR, **request):
    return record_decision(
        store,
        definition_lookup=definition_lookup,
        subject_reader=table.read,
        request=DecisionRequest(
            decision_key=KEY,
            subject_period="2026-01",
            outcome=outcome,
            rationale="Estimate below cost; keep for one more month.",
            **request,
        ),
        actor=actor,
        now=DECIDED_AT,
    )


def _state(store, record, today: date) -> dict:
    return load_serialized_decision(store, record, today=today)["lifecycle"]


def test_migration_0010_adds_commitment_tables_and_mirrors_postgres() -> None:
    conn = sqlite3.connect(":memory:")
    applied = apply_pending_sqlite_migrations(conn, ROOT / "migrations" / "sqlite")
    assert "0010_decision_commitment_lifecycle" in applied
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"decision_commitments", "decision_lifecycle_events"} <= tables
    record_columns = [row[1] for row in conn.execute("PRAGMA table_info(decision_records)")]
    assert "purpose" not in record_columns  # decision_records is unchanged

    def columns(sql: str) -> list[str]:
        return [
            line.strip().split()[0]
            for line in sql.splitlines()
            if line.strip() and not line.strip().startswith(("--", "CREATE", "ON ", ")"))
        ]

    sqlite_sql = (ROOT / "migrations/sqlite/0010_decision_commitment_lifecycle.sql").read_text()
    postgres_sql = (
        ROOT / "migrations/postgres/0017_decision_commitment_lifecycle.sql"
    ).read_text()
    assert columns(sqlite_sql) == columns(postgres_sql)


def test_battery_definition_declares_commitment_terms_at_version_1_1_0() -> None:
    definition = BATTERY_PLAN_DECISION
    assert definition.version == "1.1.0"
    assert definition.purpose
    assert definition.owner.role == definition.decision_maker_role == "operator"
    assert set(definition.baseline.value_keys) == {
        "estimated_savings_eur",
        "effective_monthly_cost_eur",
        "estimated_net_benefit_eur",
    }
    kinds = {trigger.kind for trigger in definition.review_triggers}
    assert kinds == {"timed", "evidence_change", "verdict_change"}
    assert {component.correction_kind for component in definition.evidence_components} >= {
        "source_window",
        "tariff_snapshot",
        "entity_mapping",
    }
    assert definition.observation_window.window_for(date(2026, 2, 10)) == (
        date(2026, 3, 1),
        date(2026, 3, 31),
    )
    assert definition.observation_window.review_due_on(date(2026, 12, 5)) == date(2027, 2, 14)
    payload = definition.to_dict()
    assert payload["stop_conditions"] and payload["success_measure"]["threshold"] == "0"


def test_definition_rejects_incomplete_lifecycle_terms() -> None:
    with pytest.raises(ValueError, match="timed review trigger"):
        replace(
            BATTERY_PLAN_DECISION,
            review_triggers=tuple(
                trigger
                for trigger in BATTERY_PLAN_DECISION.review_triggers
                if trigger.kind != "timed"
            ),
        )
    with pytest.raises(ValueError, match="undeclared evidence components"):
        replace(
            BATTERY_PLAN_DECISION,
            review_triggers=(
                *BATTERY_PLAN_DECISION.review_triggers,
                DecisionReviewTrigger("x", "x", "evidence_change", ("nope",)),
            ),
        )
    with pytest.raises(ValueError, match="stop condition"):
        replace(BATTERY_PLAN_DECISION, stop_conditions=())
    with pytest.raises(ValueError, match="purpose"):
        replace(BATTERY_PLAN_DECISION, purpose=" ")
    with pytest.raises(ValueError):
        DecisionObservationWindow("x", "weekly", 1, 0, 1)


def test_record_pins_commitment_terms_and_derives_follow_up_from_window() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _record(store, SubjectTable(battery_row()))
        commitment = record.commitment
        assert commitment is not None
        assert commitment.owner_verified is True
        assert commitment.observation_window_start == date(2026, 3, 1)
        assert commitment.observation_window_end == date(2026, 3, 31)
        assert record.follow_up_due_on == commitment.next_review_due_on == date(2026, 4, 14)
        payload = load_serialized_decision(store, record, today=date(2026, 2, 11))
        assert payload["commitment"]["purpose"] == BATTERY_PLAN_DECISION.purpose
        baseline = payload["commitment"]["baseline"]["values"]
        assert baseline["estimated_savings_eur"] == {
            "value": "30",
            "status": "estimated",
            "unit": "EUR/month",
            "is_missing": False,
        }
        assert payload["lifecycle"]["state"] == "active"
        assert payload["lifecycle"]["evidence_status"] == "as_recorded"
        assert payload["lineage_reference"]["evidence_fingerprint"].startswith("evf_")
        assert payload["history"] == []


def test_owner_and_window_are_enforced_at_record_time() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(battery_row())
        with pytest.raises(DecisionAuthorizationError):
            _record(store, table, actor=READER)
        with pytest.raises(DecisionValidationError, match="observation window closes"):
            _record(store, table, follow_up_due_on=date(2026, 3, 15))
        later = _record(store, table, follow_up_due_on=date(2026, 5, 1))
        assert later.follow_up_due_on == date(2026, 5, 1)

        unverified = _record(store, table, actor=actor_from_principal(None))
        assert unverified.commitment is not None
        assert unverified.commitment.owner_verified is False

    named = replace(
        BATTERY_PLAN_DECISION, owner=DecisionOwner(role="operator", principal="alice")
    )
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        with pytest.raises(DecisionAuthorizationError, match="owned by alice"):
            record_decision(
                store,
                definition_lookup=lambda key: named,
                subject_reader=SubjectTable(battery_row()).read,
                request=DecisionRequest(
                    decision_key=KEY, subject_period="2026-01", outcome="keep_current_plan",
                    rationale="r",
                ),
                actor=OPERATOR,
                now=DECIDED_AT,
            )


def test_success_follow_up_meets_measure_and_schedules_next_review() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _record(store, SubjectTable(battery_row()))
        record_follow_up(
            store,
            decision_id=record.decision_id,
            request=FollowUpRequest(
                observed_at=datetime(2026, 4, 10, 8, tzinfo=DECIDED_AT.tzinfo),
                realized_result="March bills show the battery paid for itself.",
                evidence_effect="confirmed_decision",
                realized_value_eur=Decimal("4.10"),
                realized_value_status="observed",
            ),
            actor=OPERATOR,
            now=datetime(2026, 4, 10, 9, tzinfo=DECIDED_AT.tzinfo),
        )
        payload = load_serialized_decision(store, record, today=date(2026, 4, 20))
        assert payload["follow_ups"][0]["success"] == "met"
        assert payload["lifecycle"]["state"] == "active"
        assert payload["lifecycle"]["next_review_due_on"] == "2026-05-10"
        assert list_commitment_reviews(store, today=date(2026, 4, 20)) == []


def test_timed_review_becomes_due_and_enters_the_queue() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _record(store, SubjectTable(battery_row()))
        assert _state(store, record, date(2026, 4, 13))["state"] == "active"
        due = _state(store, record, date(2026, 4, 14))
        assert due["state"] == "review_due"
        assert due["proactive_review"] is True
        [queued] = list_commitment_reviews(store, today=date(2026, 4, 14))
        assert queued["decision_id"] == record.decision_id
        assert queued["state"] == "review_due"


def test_source_change_requires_review_until_a_follow_up_reviews_it() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(battery_row())
        record = _record(store, table)
        table.rows["2026-01"] = battery_row(
            assessment_id="bpo_corrected", tariff_snapshot_id="tariff-b"
        )
        trace_evidence_corrections(
            store,
            definition_lookup=definition_lookup,
            subject_reader=table.read,
            snapshot_components=snapshot_evidence_components,
            now=DECIDED_AT + timedelta(days=5),
        )
        required = _state(store, record, date(2026, 2, 20))
        assert required["state"] == "review_required"
        assert required["evidence_status"] == "superseded"
        assert required["superseded_by"]["superseding_row_ref"] == "bpo_corrected"
        assert list_commitment_reviews(store, today=date(2026, 2, 20))[0]["state"] == (
            "review_required"
        )
        record_follow_up(
            store,
            decision_id=record.decision_id,
            request=FollowUpRequest(
                observed_at=DECIDED_AT + timedelta(days=6),
                realized_result="Reviewed the revised tariff; decision stands.",
                evidence_effect="confirmed_decision",
            ),
            actor=OPERATOR,
            now=DECIDED_AT + timedelta(days=6),
        )
        reviewed = load_serialized_decision(store, record, today=date(2026, 2, 20))
        assert reviewed["lifecycle"]["state"] == "active"
        # The pointer to the newer assessment stays; the original snapshot too.
        assert reviewed["lifecycle"]["evidence_status"] == "superseded"
        assert reviewed["follow_ups"][0]["success"] == "unmeasured"


def test_operator_stop_removes_commitment_from_queue_and_keeps_history() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _record(store, SubjectTable(battery_row()))
        with pytest.raises(DecisionValidationError, match="Unknown stop condition"):
            stop_commitment(
                store, decision_id=record.decision_id, stop_condition_key="bored",
                reason="x", actor=OPERATOR, definition_lookup=definition_lookup,
            )
        with pytest.raises(DecisionAuthorizationError):
            stop_commitment(
                store, decision_id=record.decision_id, stop_condition_key="purpose_expired",
                reason="x", actor=READER, definition_lookup=definition_lookup,
            )
        stop_commitment(
            store,
            decision_id=record.decision_id,
            stop_condition_key="purpose_expired",
            reason="Battery sold with the house.",
            actor=OPERATOR,
            definition_lookup=definition_lookup,
            now=DECIDED_AT + timedelta(days=1),
        )
        with pytest.raises(DecisionStateConflictError):
            stop_commitment(
                store, decision_id=record.decision_id, stop_condition_key="purpose_expired",
                reason="again", actor=OPERATOR, definition_lookup=definition_lookup,
            )
        long_past_due = date(2026, 9, 1)
        payload = load_serialized_decision(store, record, today=long_past_due)
        assert payload["lifecycle"]["state"] == "stopped"
        assert payload["lifecycle"]["next_review_due_on"] is None
        assert payload["lifecycle"]["proactive_review"] is False
        assert [event["event_kind"] for event in payload["history"]] == ["stopped"]
        assert payload["rationale"]  # historical decision remains readable
        assert list_commitment_reviews(store, today=long_past_due) == []

        reopen_commitment(
            store,
            decision_id=record.decision_id,
            reason="Battery kept after all.",
            actor=OPERATOR,
            definition_lookup=definition_lookup,
            now=DECIDED_AT + timedelta(days=2),
        )
        reopened = load_serialized_decision(store, record, today=date(2026, 2, 13))
        assert reopened["lifecycle"]["state"] == "active"
        assert [event["event_kind"] for event in reopened["history"]] == ["stopped", "reopened"]
        with pytest.raises(DecisionStateConflictError):
            reopen_commitment(
                store, decision_id=record.decision_id, reason="x", actor=OPERATOR,
                definition_lookup=definition_lookup,
            )


def test_missing_evidence_is_distinct_and_flags_stop_conditions() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(
            battery_row(
                verdict="insufficient_evidence",
                reason_codes_json='["battery_cost_basis_missing"]',
                effective_monthly_cost_eur=None,
                estimated_net_benefit_eur=None,
            )
        )
        with pytest.raises(DecisionValidationError, match="acknowledge"):
            _record(store, table, outcome="defer_pending_evidence")
        record = _record(
            store,
            table,
            outcome="defer_pending_evidence",
            evidence_gaps_acknowledged=("battery_cost_basis_missing",),
        )
        payload = load_serialized_decision(store, record, today=date(2026, 2, 11))
        lifecycle = payload["lifecycle"]
        assert lifecycle["state"] == "active"
        assert lifecycle["evidence_status"] == "insufficient"
        assert lifecycle["stop_conditions_met"] == ["battery_plan_ended"]
        assert lifecycle["stop_recommended"] is True
        cost = payload["commitment"]["baseline"]["values"]["effective_monthly_cost_eur"]
        assert cost["value"] is None and cost["is_missing"] is True


def test_outcome_based_stop_condition_is_flagged_not_applied() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _record(store, SubjectTable(battery_row()), outcome="change_tariff_or_contract")
        lifecycle = _state(store, record, date(2026, 2, 11))
        assert lifecycle["state"] == "active"
        assert lifecycle["stop_conditions_met"] == ["tariff_or_contract_changed"]
