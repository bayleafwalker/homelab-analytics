"""Publication contracts for the battery-plan outcome marts."""

from __future__ import annotations

from packages.platform.capability_types import (
    PublicationDefinition,
    PublicationFieldDefinition,
    dimension_field,
    identifier_field,
    measure_field,
    status_field,
    time_field,
)


def _count(description: str) -> PublicationFieldDefinition:
    return measure_field(description, aggregation="latest", unit="count")


def _eur(description: str) -> PublicationFieldDefinition:
    return measure_field(description, aggregation="latest", unit="currency")


BATTERY_PLAN_OUTCOME_PUBLICATION = PublicationDefinition(
    key="battery_plan_outcome",
    schema_name="battery_plan_outcome",
    schema_version="1.0.0",
    display_name="Battery Plan Outcome",
    description=(
        "Review-only verdict for the named Kotiakku battery-plan decision with "
        "coverage, freshness, tariff assumptions, lineage and remediation. "
        "Estimates are never realized savings and never authorize actuation."
    ),
    visibility="public",
    lineage_required=True,
    retention_policy="rolling_12_months",
    field_semantics={
        "assessment_id": identifier_field(
            "Deterministic fingerprint of the assessment inputs; decision records pin it."
        ),
        "decision_key": identifier_field("Declared decision question this row answers."),
        "decision_version": dimension_field("Version of the decision definition applied."),
        "decision_month": time_field(
            "Closed household-local month the evidence window covers.", grain="month"
        ),
        "household_timezone": dimension_field("IANA timezone defining the month window."),
        "assessed_at": time_field("Assessment timestamp (ISO-8601, UTC).", grain="timestamp"),
        "profile_status": status_field(
            "Source profile state: configured, unconfigured, or invalid."
        ),
        "evidence_status": status_field("qualified or insufficient."),
        "verdict": status_field(
            "insufficient_evidence, no_benefit_estimated, or benefit_estimated. "
            "Stale or incomplete evidence is always insufficient_evidence."
        ),
        "claim_basis": status_field(
            "none when insufficient; source_estimate otherwise. Never realized savings."
        ),
        "source_recommendation": status_field(
            "Review-only recommendation from the evidence qualifier."
        ),
        "recommendation_scope": status_field("Always review_only."),
        "actuation_authorized": status_field("Always false: no actuation is authorized."),
        "estimated_savings_eur": _eur("Source-calculated estimated monthly battery savings."),
        "effective_monthly_cost_eur": _eur("Effective monthly battery cost from user-entered inputs."),
        "estimated_net_benefit_eur": _eur("Estimated savings minus effective monthly cost."),
        "cost_basis_method": dimension_field("How the effective monthly cost was obtained."),
        "expected_window_count": _count("Five-minute windows expected in the month."),
        "complete_window_count": _count("Windows with every mapped measurement present."),
        "missing_window_count": _count("Expected windows without complete measurements."),
        "coverage_pct": measure_field(
            "Complete windows as a percentage of expected windows.",
            aggregation="latest",
            unit="percent",
        ),
        "duplicate_snapshot_count": _count("Duplicate measurement records seen."),
        "conflicting_window_count": _count("Windows with conflicting duplicate values."),
        "invalid_record_count": _count("Records with invalid periods, values, or units."),
        "unknown_scope_timestamp_count": _count("Records whose month could not be established."),
        "backfill_status": status_field("Backfill state; not established from HA state history."),
        "source_last_period_end": time_field(
            "End of the latest source period reported (ISO-8601, UTC).", grain="timestamp"
        ),
        "freshness_status": status_field("fresh, stale, or unknown at assessment time."),
        "freshness_age_minutes": measure_field(
            "Minutes between the latest source period and the assessment.",
            aggregation="latest",
            unit="minutes",
        ),
        "freshness_limit_minutes": measure_field(
            "Maximum source age accepted as fresh.", aggregation="latest", unit="minutes"
        ),
        "tariff_snapshot_id": identifier_field("Signature of the month's tariff snapshot."),
        "tariff_snapshot_json": dimension_field("Month-specific tariff assumptions (JSON)."),
        "source_calculation_method": dimension_field("Source economics calculation method."),
        "source_evidence_contract_version": dimension_field("Source evidence contract version."),
        "reason_codes_json": dimension_field("Insufficiency reason codes (JSON list)."),
        "missing_fields_json": dimension_field("Material values that are missing (JSON list)."),
        "remediation": dimension_field("Actionable remediation for insufficient evidence."),
        "limitations_json": dimension_field("Material estimate limitations (JSON list)."),
        "source_entity_ids_json": dimension_field("Explicit HA entity mapping used (JSON)."),
        "source_run_ids_json": dimension_field("Ingest run IDs the evidence was read from (JSON)."),
        "source_report_ingested_at": time_field(
            "Ingest time of the economics snapshot used.", grain="timestamp"
        ),
    },
)

BATTERY_PLAN_OUTCOME_VALUES_PUBLICATION = PublicationDefinition(
    key="battery_plan_outcome_values",
    schema_name="battery_plan_outcome_values",
    schema_version="1.0.0",
    display_name="Battery Plan Outcome Values",
    description=(
        "Per-value disclosure for the battery-plan outcome: each material value "
        "with its status (observed, derived, estimated, heuristic, user_entered), "
        "role (actual, estimate, assumption, quality) and explicit missing flag."
    ),
    visibility="public",
    lineage_required=True,
    retention_policy="rolling_12_months",
    field_semantics={
        "assessment_id": identifier_field("Assessment the value belongs to."),
        "decision_month": time_field("Decision month of the assessment.", grain="month"),
        "display_order": measure_field(
            "Stable display order within the assessment.", aggregation="none", unit="rank"
        ),
        "value_key": identifier_field("Stable key of the material value."),
        "value_label": dimension_field("Human-readable label."),
        "value_numeric": measure_field(
            "Numeric value; null when missing or textual (never zero-filled).",
            aggregation="none",
            unit="value_unit",
        ),
        "value_text": dimension_field("Textual value, when not numeric."),
        "unit": dimension_field("Unit of the value."),
        "value_status": status_field(
            "observed, derived, estimated, heuristic, or user_entered."
        ),
        "value_role": status_field("actual, estimate, assumption, or quality."),
        "is_missing": status_field("True when the source did not supply the value."),
        "source_reference": dimension_field("Source entity/attribute the value came from."),
        "note": dimension_field("Derivation or limitation note."),
    },
)
