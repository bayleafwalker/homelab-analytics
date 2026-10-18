"""HLA-K04: portable, versioned outcome references (export only, no network)."""

from __future__ import annotations

import io
import json
from argparse import Namespace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.worker.command_handlers import build_worker_command_handlers
from apps.worker.command_handlers.decision_commands import handle_export_outcome_references
from apps.worker.command_parser import build_parser
from packages.application.use_cases.decision_evidence_trace import (
    trace_evidence_corrections,
)
from packages.application.use_cases.decision_ledger import (
    DecisionRequest,
    FollowUpRequest,
    record_decision,
    record_follow_up,
    stop_commitment,
)
from packages.application.use_cases.decision_outcome_reference import (
    IDEMPOTENCY_KEY_PATTERN,
    build_outcome_references,
    latest_outcome_reference,
    outcome_reference_feed,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.household_decisions import snapshot_evidence_components
from packages.storage.run_metadata import RunMetadataRepository
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


def _decide(store: Any, table: SubjectTable) -> Any:
    return record_decision(
        store,
        definition_lookup=definition_lookup,
        subject_reader=table.read,
        request=DecisionRequest(
            decision_key=KEY, subject_period="2026-01", outcome="keep_current_plan",
            rationale="Keep.",
        ),
        actor=OPERATOR,
        now=DECIDED_AT,
    )


def _follow_up(store: Any, decision_id: str, days: int, **request: Any) -> None:
    record_follow_up(
        store,
        decision_id=decision_id,
        request=FollowUpRequest(
            observed_at=DECIDED_AT + timedelta(days=days),
            realized_result="Bills reviewed.",
            evidence_effect=request.pop("evidence_effect", "confirmed_decision"),
            **request,
        ),
        actor=OPERATOR,
        now=DECIDED_AT + timedelta(days=days),
    )


def test_envelope_carries_references_window_result_and_explicit_unknowns() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store, SubjectTable(battery_row()))
        latest, revisions = latest_outcome_reference(store, record.decision_id)
        assert len(revisions) == 1
        assert latest["schema_version"] == "hla-outcome-reference/v1"
        assert latest["repo_id"] == "homelab-analytics"
        assert latest["operation"] == "hla.outcome.export"
        assert latest["outcome_ref"] == f"hla:decision:{record.decision_id}"
        assert latest["revision"] == 1 and latest["supersedes"] is None
        assert latest["result"] == "pending"
        assert latest["commitment_ref"]["decision_version"] == "1.1.0"
        assert latest["work_ref"] is None
        assert latest["publication_ref"] == {
            "publication_key": "mart_battery_plan_outcome",
            "schema_version": "1.0.0",
            "period": "2026-01",
            "row_ref": "bpo_original",
            "evidence_fingerprint": record.commitment.evidence_fingerprint,
        }
        assert latest["observation_window"] == {"start": "2026-03-01", "end": "2026-03-31"}
        assert latest["attention"] == {
            "measured_minutes": None,
            "capture_coverage": "not_captured",
            "unknown_is_zero": False,
        }
        assert latest["cost"]["realized_value_eur"] is None
        assert latest["cost"]["capture_coverage"] == "not_captured"
        assert latest["authority"]["household_authority_transferred"] is False
        assert latest["evidence_pointer"]["href"] == f"/control/decisions/{record.decision_id}"
        assert IDEMPOTENCY_KEY_PATTERN.match(latest["idempotency_key"])
        # Household rows, snapshots and credentials stay in HLA.
        text = json.dumps(latest)
        for forbidden in ("evidence_snapshot\":", "source_entity_ids", "sensor.", "rationale"):
            assert forbidden not in text


def test_retry_is_one_logical_event_and_corrections_supersede() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(battery_row())
        record = _decide(store, table)
        first = latest_outcome_reference(store, record.decision_id)[0]
        assert latest_outcome_reference(store, record.decision_id)[0] == first  # retry

        _follow_up(
            store, record.decision_id, 60,
            realized_value_eur=Decimal("-3.50"), realized_value_status="observed",
        )
        table.rows["2026-01"] = battery_row(assessment_id="bpo_fixed", tariff_snapshot_id="t2")
        trace_evidence_corrections(
            store,
            definition_lookup=definition_lookup,
            subject_reader=table.read,
            snapshot_components=snapshot_evidence_components,
            now=DECIDED_AT + timedelta(days=61),
        )
        latest, revisions = latest_outcome_reference(store, record.decision_id)
        assert [item["revision"] for item in revisions] == [1, 2, 3]
        assert revisions[0]["event_id"] == first["event_id"]
        assert revisions[1]["supersedes"] == revisions[0]["event_id"]
        assert revisions[2]["supersedes"] == revisions[1]["event_id"]
        assert len({item["event_id"] for item in revisions}) == 3
        assert revisions[1]["result"] == "rejected"  # realized net benefit below zero
        assert revisions[1]["cost"] == {
            "realized_value_eur": "-3.50",
            "value_status": "observed",
            "capture_coverage": "captured",
            "unknown_is_zero": False,
        }
        assert latest["evidence_status"] == "superseded"
        assert latest["evidence_pointer"]["superseded_by"]["superseding_row_ref"] == "bpo_fixed"
        # Re-export after the correction reproduces the same revisions.
        assert latest_outcome_reference(store, record.decision_id)[1] == revisions


def test_result_mapping_and_terminal_feed_events() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        table = SubjectTable(battery_row())
        accepted = _decide(store, table)
        _follow_up(
            store, accepted.decision_id, 60,
            realized_value_eur=Decimal("2"), realized_value_status="user_entered",
        )
        unmeasured = _decide(store, table)
        _follow_up(store, unmeasured.decision_id, 60)
        defect = _decide(store, table)
        _follow_up(store, defect.decision_id, 60, evidence_effect="exposed_source_defect")
        stop_commitment(
            store, decision_id=defect.decision_id, stop_condition_key="purpose_expired",
            reason="Done.", actor=OPERATOR, definition_lookup=definition_lookup,
            now=DECIDED_AT + timedelta(days=61),
        )
        feed = outcome_reference_feed(store, decision_key=KEY, include_history=False)
        assert feed["schema_version"] == "resource-changes/v1"
        assert feed["next_cursor"] is None
        by_decision = {
            event["data"]["commitment_ref"]["decision_id"]: event for event in feed["events"]
        }
        assert by_decision[accepted.decision_id]["data"]["result"] == "accepted"
        assert by_decision[unmeasured.decision_id]["data"]["result"] == "insufficient_evidence"
        assert by_decision[defect.decision_id]["data"]["result"] == "insufficient_evidence"
        assert by_decision[defect.decision_id]["terminal"] is True
        assert by_decision[accepted.decision_id]["terminal"] is False
        full = outcome_reference_feed(store, decision_key=KEY)
        assert len(full["events"]) == 7  # 3 records + 3 follow-ups + 1 stop
        record = store.get_decision_record(accepted.decision_id)
        assert build_outcome_references(
            record, store.list_decision_follow_ups(record.decision_id), []
        )[-1]["result"] == "accepted"


def test_api_and_worker_export_without_network() -> None:
    with TemporaryDirectory() as temp_dir:
        store = ledger(temp_dir)
        record = _decide(store, SubjectTable(battery_row()))
        app = create_app(
            AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            ),
            config_repository=store,
        )
        client = TestClient(app)
        single = client.get(f"/control/decisions/{record.decision_id}/outcome-reference")
        assert single.status_code == 200, single.text
        assert single.json()["reference"]["revision"] == 1
        assert client.get("/control/decisions/dec_missing/outcome-reference").status_code == 404
        feed = client.get("/control/decisions/outcome-references", params={"latest_only": True})
        assert [event["event_id"] for event in feed.json()["events"]] == [
            single.json()["reference"]["event_id"]
        ]

        assert "export-outcome-references" in build_worker_command_handlers()
        args = build_parser().parse_args(
            ["export-outcome-references", "--output-file", str(Path(temp_dir) / "out.json")]
        )
        output = io.StringIO()
        runtime = SimpleNamespace(config_repository=store, output=output)
        assert handle_export_outcome_references(args, runtime) == 0  # type: ignore[arg-type]
        written = json.loads((Path(temp_dir) / "out.json").read_text())
        assert written["events"][0]["event_id"] == single.json()["reference"]["event_id"]
        assert handle_export_outcome_references(
            Namespace(decision_key="", latest_only=True, output_file=""),
            SimpleNamespace(config_repository=object(), output=io.StringIO()),  # type: ignore[arg-type]
        ) == 1


def test_export_modules_make_no_outbound_calls() -> None:
    for path in (
        "packages/application/use_cases/decision_outcome_reference.py",
        "apps/worker/command_handlers/decision_commands.py",
    ):
        source = (ROOT / path).read_text()
        for token in ("httpx", "requests", "urllib", "socket", "aiohttp", "http.client"):
            assert f"import {token}" not in source and f"from {token}" not in source
