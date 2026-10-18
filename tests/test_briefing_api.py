"""API tests for GET /api/briefing (Kotona B1 morning brief)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.response_models import MorningBriefResponseModel
from packages.pipelines.transformation_service import TransformationService
from packages.storage.control_plane import (
    PublicationAuditCreate,
    PublicationConfidenceSnapshotCreate,
    SourceLineageCreate,
)
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


class _FakeReportingService:
    """Stands in for ReportingService: only the brief's reporting accessors."""

    def get_monthly_cashflow(self, from_month=None, to_month=None) -> list[dict[str, Any]]:
        return [
            {"booking_month": "2026-09", "income": 4000, "expense": 3000, "net": 1000},
            {"booking_month": "2026-10", "income": 4200, "expense": 3700, "net": 500},
        ]

    def get_open_attention_items(self) -> list[dict[str, Any]]:
        return []

    def get_recent_significant_changes(self) -> list[dict[str, Any]]:
        return []

    def get_upcoming_fixed_costs_30d(self) -> list[dict[str, Any]]:
        return []


class _BreachEvaluator:
    def evaluate(self):
        from packages.domains.homelab.pipelines.ha_policy import PolicyResult

        return [
            PolicyResult(
                id="budget_status",
                name="Budget status",
                description="Test policy",
                verdict="breach",
                value="104%",
                reason="Highest budget utilisation 104% is over 100%.",
                evaluated_at="2026-10-18T05:00:00+00:00",
            )
        ]


def _client(tmp: str, *, fake_reporting: bool = False, evaluator: Any = None) -> TestClient:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    kwargs: dict[str, Any] = {"transformation_service": TransformationService(DuckDBStore.memory())}
    if fake_reporting:
        kwargs["reporting_service"] = _FakeReportingService()
    if evaluator is not None:
        kwargs["ha_policy_evaluator"] = evaluator
    return TestClient(create_app(service, **kwargs))


def _seed_trustworthy_cashflow(store: Any) -> None:
    store.record_publication_confidence_snapshot(
        (
            PublicationConfidenceSnapshotCreate(
                snapshot_id="snap-1",
                publication_key="mart_monthly_cashflow",
                assessed_at=datetime.now(UTC),
                freshness_state="current",
                completeness_pct=100,
                confidence_verdict="trustworthy",
                quality_flags={"validation_errors": 0, "rejected_runs": 0},
                contributing_run_ids=("run-100",),
                source_freshness_states={
                    "bank_csv": {"source_asset_id": "bank_csv", "freshness_state": "current"}
                },
            ),
        )
    )
    store.record_publication_audit(
        (
            PublicationAuditCreate(
                publication_audit_id="a1",
                run_id="run-100",
                publication_key="mart_monthly_cashflow",
                relation_name="mart_monthly_cashflow",
                status="published",
                published_at=datetime(2026, 10, 5, tzinfo=UTC),
            ),
        )
    )
    store.record_source_lineage(
        (
            SourceLineageCreate(
                lineage_id="L1",
                input_run_id="run-100",
                target_layer="reporting",
                target_name="mart_monthly_cashflow",
                target_kind="mart",
                row_count=12,
                source_system="bank_csv",
                source_run_id="src-7",
            ),
        )
    )


def _section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return next(section for section in payload["sections"] if section["key"] == key)


def test_brief_without_confidence_withholds_publication_claims() -> None:
    with TemporaryDirectory() as tmp:
        client = _client(tmp)
        response = client.get("/api/briefing")
        assert response.status_code == 200
        payload = response.json()
        MorningBriefResponseModel.model_validate(payload)
        assert [s["key"] for s in payload["sections"]] == [
            "money", "attention", "changes", "upcoming", "policies", "sources",
        ]
        money = _section(payload, "money")["items"][0]
        assert money["claim_status"] == "withheld"
        assert "transformation refresh" in money["remediation"]
        assert money["lineage_publication_key"] == "mart_monthly_cashflow"
        assert _section(payload, "policies")["status"] == "unavailable"
        assert payload["counts"]["withheld"] >= 5


def test_trustworthy_publication_yields_confirmed_claim_and_lineage_drill() -> None:
    with TemporaryDirectory() as tmp:
        client = _client(tmp, fake_reporting=True)
        _seed_trustworthy_cashflow(client.app.state.control_plane_store)
        payload = client.get("/api/briefing").json()
        money = _section(payload, "money")["items"][0]
        assert money["claim_status"] == "confirmed"
        assert money["confidence"]["verdict"] == "trustworthy"
        assert money["confidence"]["validation_state"] == "known"
        refs = {(ref["kind"], ref["ref"]) for ref in money["evidence"]}
        assert ("run", "run-100") in refs
        assert ("source", "bank_csv") in refs

        # The drill target resolves to the source run through the lineage API.
        lineage = client.get(
            f"/api/lineage/publication/{money['lineage_publication_key']}"
        ).json()
        node_ids = {node["id"] for node in lineage["nodes"]}
        assert {"run:run-100", "source:bank_csv"} <= node_ids


def test_policy_verdict_and_reason_appear_in_brief() -> None:
    with TemporaryDirectory() as tmp:
        client = _client(tmp, evaluator=_BreachEvaluator())
        payload = client.get("/api/briefing").json()
        policies = _section(payload, "policies")
        item = policies["items"][0]
        assert item["severity"] == "critical"
        assert item["detail"] == "Highest budget utilisation 104% is over 100%."
        assert payload["overall_severity"] == "critical"


def test_repeat_requests_have_identical_content_hash() -> None:
    with TemporaryDirectory() as tmp:
        client = _client(tmp, fake_reporting=True)
        _seed_trustworthy_cashflow(client.app.state.control_plane_store)
        first = client.get("/api/briefing").json()
        second = client.get("/api/briefing").json()
        assert first["content_hash"] == second["content_hash"]
        assert first["sections"] == second["sections"]
