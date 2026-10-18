"""HLA-K02: corrected source windows, tariffs and mappings supersede decision evidence."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.use_cases.decision_evidence_trace import (
    trace_evidence_corrections,
)
from packages.application.use_cases.decision_ledger import (
    DecisionRequest,
    load_serialized_decision,
    record_decision,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.domains.homelab.pipelines.ha_models import FACT_HA_STATE_CHANGE_TABLE
from packages.domains.utilities.pipelines.publication_refresh import (
    refresh_battery_plan_publication,
)
from packages.pipelines.household_decisions import snapshot_evidence_components
from packages.storage.decision_ledger import DecisionRecordCreate
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.decision_lifecycle_support import (
    DECIDED_AT,
    OPERATOR,
    SubjectTable,
    battery_row,
    definition_lookup,
    ledger,
)
from tests.test_battery_plan_outcome import _profile, _service, _store_with_history

KEY = "kotiakku_battery_plan_review"


def _decide(store: Any, table: SubjectTable, period: str = "2026-01") -> Any:
    return record_decision(
        store,
        definition_lookup=definition_lookup,
        subject_reader=table.read,
        request=DecisionRequest(
            decision_key=KEY,
            subject_period=period,
            outcome="keep_current_plan",
            rationale="Keep.",
        ),
        actor=OPERATOR,
        now=DECIDED_AT,
    )


def _trace(store: Any, table: SubjectTable, days: int = 3) -> dict[str, Any]:
    return trace_evidence_corrections(
        store,
        definition_lookup=definition_lookup,
        subject_reader=table.read,
        snapshot_components=snapshot_evidence_components,
        now=DECIDED_AT + timedelta(days=days),
    ).as_dict()


@pytest.mark.parametrize(
    "overrides,component,kind",
    [
        ({"tariff_snapshot_id": "tariff-b"}, "tariff_snapshot", "tariff_snapshot"),
        (
            {"source_entity_ids_json": json.dumps({"battery_savings": "sensor.renamed"})},
            "entity_mapping",
            "entity_mapping",
        ),
        (
            {"source_run_ids_json": json.dumps(["run-economics", "run-measurement-relanded"])},
            "source_windows",
            "source_window",
        ),
        ({"complete_window_count": 8900, "missing_window_count": 28}, "source_windows", "source_window"),
        ({"effective_monthly_cost_eur": "39.0000"}, "cost_basis", "cost_basis"),
    ],
)
def test_correction_marks_decision_superseded_with_pointer(
    overrides: dict[str, Any], component: str, kind: str
) -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(battery_row())
        record = _decide(store, table)
        table.rows["2026-01"] = battery_row(assessment_id="bpo_corrected", **overrides)

        report = _trace(store, table)
        [result] = report["results"]
        assert result["status"] == "superseded"
        assert result["changed_components"] == [component]
        assert result["correction_kinds"] == [kind]
        assert result["superseding_row_ref"] == "bpo_corrected"
        assert report["affected_publication_keys"] == [
            "mart_battery_plan_outcome",
            "mart_battery_plan_outcome_values",
        ]

        [event] = store.list_decision_lifecycle_events(record.decision_id)
        details = json.loads(event.details)
        assert event.event_kind == "evidence_superseded"
        assert details["superseded_row_ref"] == "bpo_original"
        assert details["superseding_row_ref"] == "bpo_corrected"
        assert details["superseded_fingerprint"] != details["superseding_fingerprint"]
        assert details["source_version"]["assessment_id"] == "bpo_corrected"
        assert details["traced_at"]
        assert details["triggered_reviews"]
        # The original evidence stays reconstructible next to the pointer.
        stored = store.get_decision_record(record.decision_id)
        assert json.loads(stored.evidence_snapshot)["outcome"]["assessment_id"] == "bpo_original"
        assert stored.subject_row_ref == "bpo_original"


def test_repeated_delivery_records_one_review_and_new_revision_records_another() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(battery_row())
        record = _decide(store, table)
        table.rows["2026-01"] = battery_row(assessment_id="bpo_b", tariff_snapshot_id="tariff-b")
        assert _trace(store, table)["counts"] == {"superseded": 1}
        # Same revision delivered again (even re-assessed under a new id).
        table.rows["2026-01"] = battery_row(assessment_id="bpo_b2", tariff_snapshot_id="tariff-b")
        assert _trace(store, table, days=4)["counts"] == {"already_recorded": 1}
        assert len(store.list_decision_lifecycle_events(record.decision_id)) == 1
        # A further revision supersedes again, pointing at the newest assessment.
        table.rows["2026-01"] = battery_row(assessment_id="bpo_c", tariff_snapshot_id="tariff-c")
        assert _trace(store, table, days=5)["counts"] == {"superseded": 1}
        payload = load_serialized_decision(store, record, today=DECIDED_AT.date())
        assert payload["lifecycle"]["superseded_by"]["superseding_row_ref"] == "bpo_c"
        assert len(payload["history"]) == 2


def test_reassessment_without_input_change_and_unrelated_periods_stay_valid() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(battery_row(), battery_row(decision_month="2025-12", assessment_id="bpo_dec"))
        january = _decide(store, table, "2026-01")
        december = _decide(store, table, "2025-12")
        # Re-assessment later: new id and timestamp, verdict drift from age, same inputs.
        table.rows["2026-01"] = battery_row(
            assessment_id="bpo_reassessed", assessed_at="2026-03-01T00:00:00+00:00",
            verdict="insufficient_evidence",
        )
        # A correction to December only.
        table.rows["2025-12"] = battery_row(
            decision_month="2025-12", assessment_id="bpo_dec_fixed", tariff_snapshot_id="t2"
        )
        report = _trace(store, table)
        by_id = {result["decision_id"]: result["status"] for result in report["results"]}
        assert by_id == {january.decision_id: "unchanged", december.decision_id: "superseded"}
        assert store.list_decision_lifecycle_events(january.decision_id) == []

        del table.rows["2026-01"]
        report = _trace(store, table, days=6)
        statuses = {result["decision_id"]: result["status"] for result in report["results"]}
        assert statuses[january.decision_id] == "subject_unpublished"


def test_verdict_change_alongside_correction_fires_verdict_trigger() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(battery_row())
        record = _decide(store, table)
        table.rows["2026-01"] = battery_row(
            assessment_id="bpo_more", estimated_savings_eur="55.0000", verdict="benefit_estimated"
        )
        _trace(store, table)
        [event] = store.list_decision_lifecycle_events(record.decision_id)
        details = json.loads(event.details)
        assert details["triggered_reviews"] == ["source_window_corrected", "verdict_changed"]
        assert (details["verdict_before"], details["verdict_after"]) == (
            "no_benefit_estimated",
            "benefit_estimated",
        )


def test_legacy_record_without_commitment_is_traced_from_its_snapshot() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        row = battery_row()
        store.create_decision_record(
            DecisionRecordCreate(
                decision_id="dec_legacy",
                decision_key=KEY,
                decision_version="1.0.0",
                subject_publication_key="mart_battery_plan_outcome",
                subject_schema_version="1.0.0",
                subject_period="2026-01",
                subject_row_ref="bpo_original",
                subject_verdict="no_benefit_estimated",
                lineage_reference=json.dumps({"publication_keys": ["mart_battery_plan_outcome"]}),
                evidence_snapshot=json.dumps({"outcome": row, "values": []}),
                outcome="keep_current_plan",
                is_non_decision=False,
                rationale="Legacy.",
                evidence_gaps_acknowledged="[]",
                uncertainty=None,
                actor=OPERATOR,
                follow_up_due_on=DECIDED_AT.date() + timedelta(days=45),
                created_at=DECIDED_AT,
            )
        )
        table = SubjectTable(battery_row(assessment_id="bpo_x", tariff_snapshot_id="t9"))
        [result] = _trace(store, table)["results"]
        assert result["status"] == "superseded"
        assert result["changed_components"] == ["tariff_snapshot"]


def test_relanded_ha_history_supersedes_decision_through_the_api() -> None:
    """End to end: re-landed HA runs → refresh → trace → battery decision superseded."""
    with TemporaryDirectory() as temp_dir:
        store, assessed_at = _store_with_history()
        transformation = _service(store, assessed_at=assessed_at, resolution=_profile())
        refresh_battery_plan_publication(transformation)
        [row] = transformation.get_battery_plan_outcome()
        app = create_app(
            AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            ),
            config_repository=IngestionConfigRepository(Path(temp_dir) / "config.db"),
            transformation_service=transformation,
        )
        client = TestClient(app)
        created = client.post(
            "/control/decisions",
            json={
                "decision_key": KEY,
                "subject_period": "2026-01",
                "subject_row_ref": row["assessment_id"],
                "outcome": "review_battery_plan",
                "rationale": "Estimated savings stay below the monthly battery cost.",
            },
        )
        assert created.status_code == 201, created.text
        decision_id = created.json()["decision"]["decision_id"]

        unchanged = client.post("/control/decisions/evidence-trace", json={}).json()["trace"]
        assert unchanged["counts"] == {"unchanged": 1}

        # Re-land the measurement history under a corrected run, then recompute.
        store.execute(
            f"UPDATE {FACT_HA_STATE_CHANGE_TABLE} SET run_id = 'corrected-measurement-run'"
            " WHERE run_id = 'synthetic-measurement-run'"
        )
        refresh_battery_plan_publication(transformation)
        traced = client.post("/control/decisions/evidence-trace", json={"decision_key": KEY})
        assert traced.status_code == 200, traced.text
        [result] = traced.json()["trace"]["results"]
        assert result["status"] == "superseded"
        assert result["correction_kinds"] == ["source_window"]

        decision = client.get(f"/control/decisions/{decision_id}").json()["decision"]
        assert decision["lifecycle"]["state"] == "review_required"
        assert decision["lifecycle"]["evidence_status"] == "superseded"
        pointer = decision["lifecycle"]["superseded_by"]
        assert pointer["superseding_row_ref"] != row["assessment_id"]
        assert "corrected-measurement-run" in pointer["source_version"]["source_run_ids"]
        assert decision["evidence_snapshot"]["outcome"]["assessment_id"] == row["assessment_id"]

        reviews = client.get("/control/decisions/reviews").json()["reviews"]
        assert [item["decision_id"] for item in reviews] == [decision_id]

        again = client.post("/control/decisions/evidence-trace", json={}).json()["trace"]
        assert again["counts"] == {"already_recorded": 1}
