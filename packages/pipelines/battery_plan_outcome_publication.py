"""Refresh, publish and record lineage for the battery-plan outcome marts.

The battery-plan outcome is assessed from Home Assistant history rather than a
file promotion, so this use case drives the standard refresh registry
(which also records publication confidence), publishes both marts to the
reporting store, and records reporting lineage from every source ingest run
the evidence was read from to both marts. Lineage carries
``source_system="home_assistant"`` so publication confidence can resolve the
contributing source runs; confidence is recomputed once lineage exists.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from packages.domains.utilities.pipelines.battery_plan_models import (
    MART_BATTERY_PLAN_OUTCOME_TABLE,
    MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE,
)
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.control_plane import SourceLineageCreate, SourceLineageStore

BATTERY_PLAN_SOURCE_SYSTEM = "home_assistant"

BATTERY_PLAN_PUBLICATION_KEYS: tuple[str, ...] = (
    MART_BATTERY_PLAN_OUTCOME_TABLE,
    MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE,
)


@dataclass(frozen=True)
class BatteryPlanPublicationResult:
    refreshed: list[str]
    published: list[str]
    lineage_run_ids: list[str]
    outcomes: list[dict[str, object]] = field(default_factory=list)


def publish_battery_plan_outcome(
    transformation_service: TransformationService,
    reporting_service: ReportingService | None,
    *,
    control_plane: SourceLineageStore | None = None,
) -> BatteryPlanPublicationResult:
    # The refresh handler rebuilds both marts together, so one refresh key
    # keeps a summary row and its value rows from the same assessment.
    refreshed = transformation_service.refresh_publications(
        [MART_BATTERY_PLAN_OUTCOME_TABLE]
    )
    rows = transformation_service.get_battery_plan_outcome()
    run_ids = sorted(
        {
            str(run_id)
            for row in rows
            for run_id in json.loads(str(row.get("source_run_ids_json") or "[]"))
        }
    )
    published: list[str] = []
    if reporting_service is not None:
        published = reporting_service.publish_publications(list(BATTERY_PLAN_PUBLICATION_KEYS))
    if control_plane is not None and run_ids:
        control_plane.record_source_lineage(
            tuple(
                SourceLineageCreate(
                    lineage_id=uuid.uuid4().hex[:16],
                    input_run_id=run_id,
                    source_run_id=run_id,
                    source_system=BATTERY_PLAN_SOURCE_SYSTEM,
                    target_layer="reporting",
                    target_name=publication_key,
                    target_kind="mart",
                    row_count=len(rows),
                )
                for run_id in run_ids
                for publication_key in BATTERY_PLAN_PUBLICATION_KEYS
            )
        )
        transformation_service.record_publication_confidence(BATTERY_PLAN_PUBLICATION_KEYS)
    return BatteryPlanPublicationResult(
        refreshed=refreshed,
        published=published,
        lineage_run_ids=run_ids,
        outcomes=[
            {
                "assessment_id": row["assessment_id"],
                "decision_month": row["decision_month"],
                "verdict": row["verdict"],
                "evidence_status": row["evidence_status"],
                "reason_codes": json.loads(str(row["reason_codes_json"])),
                "remediation": row["remediation"],
            }
            for row in rows
        ],
    )
