"""Composition-layer registry of declared household decision definitions.

Each definition has a subject reader that resolves the exact reporting-layer
publication row a decision is made on (never landing or transformation data),
so a decision record can pin its row reference, schema version, lineage,
baseline and evidence fingerprint. A subject lister enumerates the periods a
decision can currently be made on, and a snapshot reader recovers the
fingerprinted evidence components from a stored decision snapshot so
correction tracing also covers records made before fingerprints were pinned.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from packages.domains.utilities.battery_plan_decision import (
    BATTERY_PLAN_DECISION,
    battery_plan_baseline,
    battery_plan_evidence_components,
)
from packages.domains.utilities.battery_plan_publications import (
    BATTERY_PLAN_OUTCOME_PUBLICATION,
)
from packages.domains.utilities.energy_contract_decision import (
    ENERGY_CONTRACT_DECISION,
    ENERGY_CONTRACT_SUBJECT_SCHEMA_NAME,
    assess_energy_contract_review,
    energy_contract_baseline,
    energy_contract_ids,
)
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.reporting_service import ReportingService
from packages.platform.decision_definitions import (
    DecisionDefinition,
    DecisionSubjectEvidence,
)

DECISION_DEFINITIONS: dict[str, DecisionDefinition] = {
    definition.decision_key: definition
    for definition in (BATTERY_PLAN_DECISION, ENERGY_CONTRACT_DECISION)
}


SubjectReader = Callable[[ReportingService, str], DecisionSubjectEvidence | None]
SubjectLister = Callable[[ReportingService], list[str]]
SnapshotComponentsReader = Callable[[Mapping[str, Any]], dict[str, Any] | None]


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
        baseline=battery_plan_baseline(row),
        evidence_components=battery_plan_evidence_components(row),
    )


def _list_battery_plan_subjects(reporting: ReportingService) -> list[str]:
    return [str(row["decision_month"]) for row in reporting.get_battery_plan_outcome()]


def _battery_snapshot_components(snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
    outcome = snapshot.get("outcome")
    if not isinstance(outcome, Mapping):
        return None
    return battery_plan_evidence_components(outcome)


def _energy_contract_schema_version() -> str:
    for publication in UTILITIES_PACK.publications:
        if publication.schema_name == ENERGY_CONTRACT_SUBJECT_SCHEMA_NAME:
            return publication.schema_version
    raise LookupError(ENERGY_CONTRACT_SUBJECT_SCHEMA_NAME)


def _read_energy_contract_subject(
    reporting: ReportingService, period: str
) -> DecisionSubjectEvidence | None:
    price_rows = reporting.get_electricity_price_current()
    if period not in energy_contract_ids(price_rows):
        return None
    assessment = assess_energy_contract_review(
        contract_id=period,
        price_rows=price_rows,
        review_candidates=reporting.get_contract_review_candidates(),
        renewal_watchlist=reporting.get_contract_renewal_watchlist(),
        cost_trend_rows=reporting.get_utility_cost_trend_monthly(utility_type="electricity"),
    )
    components = assessment.pop("evidence_components")
    return DecisionSubjectEvidence(
        publication_key=ENERGY_CONTRACT_DECISION.subject_publication_key,
        schema_version=_energy_contract_schema_version(),
        period=period,
        row_ref=str(assessment["assessment_id"]),
        verdict=str(assessment["verdict"]),
        reason_codes=tuple(assessment["reason_codes"]),
        lineage_reference={
            "publication_keys": [
                ENERGY_CONTRACT_DECISION.subject_publication_key,
                *ENERGY_CONTRACT_DECISION.supporting_publication_keys,
            ],
            "assessment_id": assessment["assessment_id"],
            "contract_id": period,
            "source_layer": "transformation.fact_contract_price",
            "best_alternative_contract_id": assessment["best_alternative_contract_id"],
            "usage_months": [assessment["usage_months_from"], assessment["usage_months_to"]],
        },
        snapshot={"assessment": assessment, "evidence_components": components},
        baseline=energy_contract_baseline(assessment),
        evidence_components=components,
    )


def _list_energy_contract_subjects(reporting: ReportingService) -> list[str]:
    return energy_contract_ids(reporting.get_electricity_price_current())


def _energy_snapshot_components(snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
    components = snapshot.get("evidence_components")
    return dict(components) if isinstance(components, Mapping) else None


SUBJECT_READERS: dict[str, SubjectReader] = {
    BATTERY_PLAN_DECISION.decision_key: _read_battery_plan_subject,
    ENERGY_CONTRACT_DECISION.decision_key: _read_energy_contract_subject,
}
SUBJECT_LISTERS: dict[str, SubjectLister] = {
    BATTERY_PLAN_DECISION.decision_key: _list_battery_plan_subjects,
    ENERGY_CONTRACT_DECISION.decision_key: _list_energy_contract_subjects,
}
SNAPSHOT_COMPONENT_READERS: dict[str, SnapshotComponentsReader] = {
    BATTERY_PLAN_DECISION.decision_key: _battery_snapshot_components,
    ENERGY_CONTRACT_DECISION.decision_key: _energy_snapshot_components,
}


def get_decision_definition(decision_key: str) -> DecisionDefinition | None:
    return DECISION_DEFINITIONS.get(decision_key)


def read_decision_subject(
    decision_key: str, reporting: ReportingService, period: str
) -> DecisionSubjectEvidence | None:
    reader = SUBJECT_READERS.get(decision_key)
    return reader(reporting, period) if reader is not None else None


def list_decision_subjects(
    decision_key: str, reporting: ReportingService
) -> list[DecisionSubjectEvidence]:
    lister = SUBJECT_LISTERS.get(decision_key)
    if lister is None:
        return []
    subjects = (read_decision_subject(decision_key, reporting, period) for period in lister(reporting))
    return [subject for subject in subjects if subject is not None]


def snapshot_evidence_components(
    decision_key: str, snapshot: Mapping[str, Any]
) -> dict[str, Any] | None:
    reader = SNAPSHOT_COMPONENT_READERS.get(decision_key)
    return reader(snapshot) if reader is not None else None
