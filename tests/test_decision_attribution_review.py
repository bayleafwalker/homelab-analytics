"""HLA-K03 attribution review on follow-ups and HLA-K04 attention capture."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.use_cases.decision_ledger import (
    DecisionRequest,
    DecisionValidationError,
    FollowUpRequest,
    load_serialized_decision,
    record_decision,
    record_follow_up,
)
from packages.application.use_cases.decision_outcome_reference import (
    latest_outcome_reference,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.storage.migration_runner import apply_pending_sqlite_migrations
from packages.storage.run_metadata import RunMetadataRepository
from packages.storage.sqlite_decision_ledger import deserialize_follow_up
from tests.decision_lifecycle_support import (
    DECIDED_AT,
    OPERATOR,
    SubjectTable,
    battery_row,
    definition_lookup,
    ledger,
)

ROOT = Path(__file__).resolve().parents[1]
KEY = "kotiakku_battery_plan_review"
ATTRIBUTION_COLUMNS = [
    "estimated_baseline_eur",
    "estimated_baseline_basis",
    "attribution_hypothesis",
    "confounders",
    "attribution_uncertainty",
    "missing_evidence",
    "attention_minutes",
]


def _decide(store: Any) -> Any:
    return record_decision(
        store,
        definition_lookup=definition_lookup,
        subject_reader=SubjectTable(battery_row()).read,
        request=DecisionRequest(
            decision_key=KEY, subject_period="2026-01", outcome="keep_current_plan",
            rationale="Keep.",
        ),
        actor=OPERATOR,
        now=DECIDED_AT,
    )


def _follow_up(store: Any, decision_id: str, days: int = 40, **request: Any) -> Any:
    return record_follow_up(
        store,
        decision_id=decision_id,
        request=FollowUpRequest(
            observed_at=DECIDED_AT + timedelta(days=days),
            realized_result="Bills reviewed.",
            evidence_effect="confirmed_decision",
            **request,
        ),
        actor=OPERATOR,
        now=DECIDED_AT + timedelta(days=days),
    )


def _columns(sql: str) -> list[str]:
    return [
        line.split("ADD COLUMN")[1].replace("IF NOT EXISTS", "").split()[0]
        for line in sql.splitlines()
        if "ADD COLUMN" in line
    ]


def test_migration_0014_adds_attribution_columns_and_mirrors_postgres() -> None:
    sqlite_sql = (ROOT / "migrations/sqlite/0014_decision_follow_up_attribution.sql").read_text()
    postgres_sql = (
        ROOT / "migrations/postgres/0023_decision_follow_up_attribution.sql"
    ).read_text()
    assert _columns(sqlite_sql) == _columns(postgres_sql) == ATTRIBUTION_COLUMNS

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations = ROOT / "migrations" / "sqlite"
    with TemporaryDirectory() as staged:
        for path in sorted(migrations.glob("*.sql")):
            if path.name < "0014":
                (Path(staged) / path.name).write_text(path.read_text())
        apply_pending_sqlite_migrations(conn, Path(staged))
    conn.execute(
        "INSERT INTO decision_records (decision_id, decision_key, decision_version,"
        " subject_publication_key, subject_schema_version, subject_period, subject_row_ref,"
        " subject_verdict, lineage_reference, evidence_snapshot, outcome, is_non_decision,"
        " rationale, evidence_gaps_acknowledged, actor, actor_auth_provider,"
        " actor_authenticated, follow_up_due_on, created_at)"
        " VALUES ('dec_old', 'k', '1.0.0', 'p', '1.0.0', '2026-01', 'r', 'v', '{}', '{}',"
        " 'keep', 0, 'x', '[]', 'op', 'local', 1, '2026-03-01', '2026-02-01T00:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO decision_follow_ups (follow_up_id, decision_id, observed_at,"
        " realized_result, evidence_effect, actor, actor_auth_provider, actor_authenticated,"
        " created_at) VALUES ('fup_old', 'dec_old', '2026-03-02T00:00:00+00:00', 'ok',"
        " 'confirmed_decision', 'op', 'local', 1, '2026-03-02T00:00:00+00:00')"
    )
    applied = apply_pending_sqlite_migrations(conn, migrations)
    assert "0014_decision_follow_up_attribution" in applied
    row = conn.execute("SELECT * FROM decision_follow_ups").fetchone()
    old = deserialize_follow_up(row)
    assert old.estimated_baseline_eur is None
    assert old.attention_minutes is None
    assert old.confounders == "[]" and old.missing_evidence == "[]"


def test_bootstrap_adds_attribution_columns_to_existing_database() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        database = Path(temp_dir) / "config.db"
        conn = sqlite3.connect(database)
        columns = [row[1] for row in conn.execute("PRAGMA table_info(decision_follow_ups)")]
        conn.close()
        assert set(ATTRIBUTION_COLUMNS) <= set(columns)
        assert store is not None


def test_measured_result_stays_apart_from_pinned_estimate() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store)
        _follow_up(
            store,
            record.decision_id,
            realized_value_eur=Decimal("-12.50"),
            realized_value_status="observed",
            baseline_value_key="estimated_net_benefit_eur",
            attribution_hypothesis="Battery shifted evening peak load to cheaper hours.",
            confounders=("Mild February", "  ", "Mild February", "New heat pump schedule"),
            attribution_uncertainty="One month; bills include a fixed fee change.",
            missing_evidence=("Spot price export for 3 days",),
            attention_minutes=25,
        )
        decision = load_serialized_decision(store, record)
        review = decision["follow_ups"][0]["attribution_review"]
        assert review["measured"] == {"value_eur": "-12.50", "value_status": "observed"}
        assert review["estimated_baseline"]["value_eur"] == "-19"
        assert review["estimated_baseline"]["value_status"] == "estimated"
        assert "estimated_net_benefit_eur" in review["estimated_baseline"]["basis"]
        assert review["measured_minus_estimate_eur"] == "6.50"
        assert review["confounders"] == ["Mild February", "New heat pump schedule"]
        assert review["missing_evidence"] == ["Spot price export for 3 days"]
        assert review["not_recorded"] == []
        assert review["causal_claim"] is False
        assert decision["follow_ups"][0]["success"] == "not_met"
        assert decision["follow_ups"][0]["attention"] == {
            "minutes": 25,
            "value_status": "user_entered",
            "capture_coverage": "captured",
        }


def test_unrecorded_parts_are_listed_never_assumed() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store)
        _follow_up(store, record.decision_id)
        follow_up = load_serialized_decision(store, record)["follow_ups"][0]
        review = follow_up["attribution_review"]
        assert review["estimated_baseline"] is None
        assert review["measured_minus_estimate_eur"] is None
        assert review["not_recorded"] == [
            "measured_result",
            "estimated_baseline",
            "attribution_hypothesis",
            "confounders",
            "uncertainty",
        ]
        assert follow_up["attention"]["minutes"] is None
        assert follow_up["attention"]["capture_coverage"] == "not_captured"


def test_explicit_estimate_needs_a_basis() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store)
        follow_up = _follow_up(
            store,
            record.decision_id,
            realized_value_eur=Decimal("5"),
            realized_value_status="user_entered",
            estimated_baseline_eur=Decimal("2"),
            estimated_baseline_basis="Last winter's bills without the battery.",
        )
        assert follow_up.estimated_baseline_eur == Decimal("2")
        assert follow_up.estimated_baseline_basis == "Last winter's bills without the battery."


@pytest.mark.parametrize(
    ("request_fields", "message"),
    [
        ({"estimated_baseline_eur": Decimal("1")}, "needs estimated_baseline_basis"),
        ({"estimated_baseline_basis": "guess"}, "requires estimated_baseline_eur"),
        (
            {"baseline_value_key": "estimated_net_benefit_eur", "estimated_baseline_eur": Decimal("1")},
            "not both",
        ),
        ({"baseline_value_key": "realized_savings"}, "Unknown baseline_value_key"),
        ({"attention_minutes": -1}, "cannot be negative"),
    ],
)
def test_invalid_attribution_inputs_are_refused(
    request_fields: dict[str, Any], message: str
) -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store)
        with pytest.raises(DecisionValidationError, match=message):
            _follow_up(store, record.decision_id, **request_fields)


def test_missing_pinned_estimate_is_refused() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = record_decision(
            store,
            definition_lookup=definition_lookup,
            subject_reader=SubjectTable(battery_row(estimated_net_benefit_eur=None)).read,
            request=DecisionRequest(
                decision_key=KEY, subject_period="2026-01", outcome="defer_pending_evidence",
                rationale="Defer.", evidence_gaps_acknowledged=("missing_estimate",),
            ),
            actor=OPERATOR,
            now=DECIDED_AT,
        )
        with pytest.raises(DecisionValidationError, match="pinned baseline value is missing"):
            _follow_up(store, record.decision_id, baseline_value_key="estimated_net_benefit_eur")


def test_outcome_reference_attention_coverage() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store)
        before, _ = latest_outcome_reference(store, record.decision_id)
        assert before["attention"] == {
            "measured_minutes": None,
            "capture_coverage": "not_captured",
            "unknown_is_zero": False,
        }
        _follow_up(store, record.decision_id, days=40, attention_minutes=20)
        captured, _ = latest_outcome_reference(store, record.decision_id)
        assert captured["attention"]["measured_minutes"] == 20
        assert captured["attention"]["capture_coverage"] == "captured"
        _follow_up(store, record.decision_id, days=75)
        partial, revisions = latest_outcome_reference(store, record.decision_id)
        assert partial["attention"]["measured_minutes"] == 20
        assert partial["attention"]["capture_coverage"] == "partial"
        assert partial["supersedes"] == revisions[-2]["event_id"]


def test_follow_up_api_accepts_attribution_review() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store)
        app = create_app(
            AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            ),
            config_repository=store,
        )
        client = TestClient(app)
        observed = (DECIDED_AT + timedelta(days=40)).isoformat()
        response = client.post(
            f"/control/decisions/{record.decision_id}/follow-ups",
            json={
                "observed_at": observed,
                "realized_result": "Bills reviewed.",
                "evidence_effect": "confirmed_decision",
                "realized_value_eur": "3.10",
                "realized_value_status": "observed",
                "baseline_value_key": "estimated_net_benefit_eur",
                "attribution_hypothesis": "Peak shifting.",
                "confounders": ["Holiday week"],
                "missing_evidence": [],
                "attention_minutes": 15,
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()["follow_up"]
        assert payload["attribution_review"]["measured_minus_estimate_eur"] == "22.10"
        assert payload["attention"]["minutes"] == 15
        refused = client.post(
            f"/control/decisions/{record.decision_id}/follow-ups",
            json={
                "observed_at": observed,
                "realized_result": "x",
                "evidence_effect": "confirmed_decision",
                "estimated_baseline_eur": "1",
            },
        )
        assert refused.status_code == 422
