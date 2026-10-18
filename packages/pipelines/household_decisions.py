"""Composition-layer registry of declared household decision definitions.

Each definition has a subject reader that resolves the exact reporting-layer
publication row a decision is made on (never landing or transformation data),
so a decision record can pin its row reference, schema version and lineage.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from packages.domains.utilities.battery_plan_decision import BATTERY_PLAN_DECISION
from packages.domains.utilities.battery_plan_publications import (
    BATTERY_PLAN_OUTCOME_PUBLICATION,
)
from packages.pipelines.reporting_service import ReportingService
from packages.platform.decision_definitions import (
    DecisionDefinition,
    DecisionSubjectEvidence,
)

DECISION_DEFINITIONS: dict[str, DecisionDefinition] = {
    definition.decision_key: definition for definition in (BATTERY_PLAN_DECISION,)
}


SubjectReader = Callable[[ReportingService, str], DecisionSubjectEvidence | None]


def _read_battery_plan_subject(
    reporting: ReportingService, period: str
) -> DecisionSubjectEvidence | None:
    rows = reporting.get_battery_plan_outcome(decision_month=period)
    if not rows:
        return None
    row = rows[0]
    values = [
        value
        for value in reporting.get_battery_plan_outcome_values(decision_month=period)
        if value.get("assessment_id") == row["assessment_id"]
    ]
    return DecisionSubjectEvidence(
        publication_key=BATTERY_PLAN_DECISION.subject_publication_key,
        schema_version=BATTERY_PLAN_OUTCOME_PUBLICATION.schema_version,
        period=period,
        row_ref=str(row["assessment_id"]),
        verdict=str(row["verdict"]),
        reason_codes=tuple(json.loads(str(row.get("reason_codes_json") or "[]"))),
        lineage_reference={
            "publication_keys": [
                BATTERY_PLAN_DECISION.subject_publication_key,
                *BATTERY_PLAN_DECISION.supporting_publication_keys,
            ],
            "assessment_id": row["assessment_id"],
            "assessed_at": row.get("assessed_at"),
            "source_layer": "transformation.fact_ha_state_change",
            "source_system": "home_assistant",
            "source_run_ids": json.loads(str(row.get("source_run_ids_json") or "[]")),
            "source_entity_ids": json.loads(str(row.get("source_entity_ids_json") or "{}")),
            "source_report_ingested_at": row.get("source_report_ingested_at"),
            "tariff_snapshot_id": row.get("tariff_snapshot_id"),
        },
        snapshot={"outcome": row, "values": values},
    )


SUBJECT_READERS: dict[str, SubjectReader] = {
    BATTERY_PLAN_DECISION.decision_key: _read_battery_plan_subject,
}


def get_decision_definition(decision_key: str) -> DecisionDefinition | None:
    return DECISION_DEFINITIONS.get(decision_key)


def read_decision_subject(
    decision_key: str, reporting: ReportingService, period: str
) -> DecisionSubjectEvidence | None:
    reader = SUBJECT_READERS.get(decision_key)
    return reader(reporting, period) if reader is not None else None
