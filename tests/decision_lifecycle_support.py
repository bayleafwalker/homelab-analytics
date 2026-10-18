"""Shared fixtures for decision commitment lifecycle, trace and export tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.domains.utilities.battery_plan_decision import (
    BATTERY_PLAN_DECISION,
    battery_plan_baseline,
    battery_plan_evidence_components,
)
from packages.pipelines.household_decisions import get_decision_definition
from packages.platform.decision_definitions import DecisionSubjectEvidence
from packages.storage.decision_ledger import DecisionActor
from packages.storage.ingestion_config import IngestionConfigRepository

OPERATOR = DecisionActor(
    actor="household-operator",
    actor_role="operator",
    actor_auth_provider="oidc",
    actor_authenticated=True,
)
READER = DecisionActor(
    actor="household-reader",
    actor_role="reader",
    actor_auth_provider="oidc",
    actor_authenticated=True,
)
DECIDED_AT = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)


def battery_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "assessment_id": "bpo_original",
        "decision_month": "2026-01",
        "assessed_at": "2026-02-01T00:10:00+00:00",
        "verdict": "no_benefit_estimated",
        "reason_codes_json": "[]",
        "estimated_savings_eur": "30.0000",
        "effective_monthly_cost_eur": "49.0000",
        "estimated_net_benefit_eur": "-19.0000",
        "cost_basis_method": "monthly_cost",
        "expected_window_count": 8928,
        "complete_window_count": 8928,
        "missing_window_count": 0,
        "duplicate_snapshot_count": 0,
        "conflicting_window_count": 0,
        "invalid_record_count": 0,
        "source_last_period_end": "2026-02-01T00:00:00+02:00",
        "source_report_ingested_at": "2026-02-01T00:05:00+00:00",
        "source_evidence_contract_version": "1.0",
        "source_calculation_method": "battery_vs_no_battery_site_cost_v1",
        "tariff_snapshot_id": "tariff-a",
        "tariff_snapshot_json": json.dumps({"tariff_mode": "spot_only"}),
        "source_entity_ids_json": json.dumps({"battery_savings": "sensor.savings"}),
        "source_run_ids_json": json.dumps(["run-economics", "run-measurement"]),
    }
    row.update(overrides)
    return row


def battery_subject(row: dict[str, Any]) -> DecisionSubjectEvidence:
    return DecisionSubjectEvidence(
        publication_key=BATTERY_PLAN_DECISION.subject_publication_key,
        schema_version="1.0.0",
        period=str(row["decision_month"]),
        row_ref=str(row["assessment_id"]),
        verdict=str(row["verdict"]),
        reason_codes=tuple(json.loads(row["reason_codes_json"])),
        lineage_reference={
            "publication_keys": [
                BATTERY_PLAN_DECISION.subject_publication_key,
                *BATTERY_PLAN_DECISION.supporting_publication_keys,
            ],
            "assessment_id": row["assessment_id"],
            "assessed_at": row["assessed_at"],
            "source_run_ids": json.loads(row["source_run_ids_json"]),
            "tariff_snapshot_id": row["tariff_snapshot_id"],
        },
        snapshot={"outcome": row, "values": []},
        baseline=battery_plan_baseline(row),
        evidence_components=battery_plan_evidence_components(row),
    )


class SubjectTable:
    """Mutable stand-in for the reporting layer: period → current row."""

    def __init__(self, *rows: dict[str, Any]) -> None:
        self.rows = {str(row["decision_month"]): row for row in rows}

    def read(self, decision_key: str, period: str) -> DecisionSubjectEvidence | None:
        if decision_key != BATTERY_PLAN_DECISION.decision_key or period not in self.rows:
            return None
        return battery_subject(self.rows[period])


def ledger(temp_dir: str) -> IngestionConfigRepository:
    return IngestionConfigRepository(Path(temp_dir) / "config.db")


definition_lookup = get_decision_definition
