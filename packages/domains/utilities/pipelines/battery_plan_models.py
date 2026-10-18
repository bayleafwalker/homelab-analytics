"""Reporting mart schemas for the battery-plan outcome publication.

Timestamps are stored as ISO-8601 strings carrying an explicit UTC offset so
naive and aware datetimes are never mixed in comparisons.
"""

from __future__ import annotations

MART_BATTERY_PLAN_OUTCOME_TABLE = "mart_battery_plan_outcome"

MART_BATTERY_PLAN_OUTCOME_COLUMNS: list[tuple[str, str]] = [
    ("assessment_id", "VARCHAR NOT NULL"),
    ("decision_key", "VARCHAR NOT NULL"),
    ("decision_version", "VARCHAR NOT NULL"),
    ("decision_month", "VARCHAR NOT NULL"),
    ("household_timezone", "VARCHAR"),
    ("assessed_at", "VARCHAR NOT NULL"),
    ("profile_status", "VARCHAR NOT NULL"),  # configured | unconfigured | invalid
    ("evidence_status", "VARCHAR NOT NULL"),  # qualified | insufficient
    # insufficient_evidence | no_benefit_estimated | benefit_estimated
    ("verdict", "VARCHAR NOT NULL"),
    ("claim_basis", "VARCHAR NOT NULL"),  # none | source_estimate
    ("source_recommendation", "VARCHAR NOT NULL"),
    ("recommendation_scope", "VARCHAR NOT NULL"),
    ("actuation_authorized", "BOOLEAN NOT NULL"),
    ("estimated_savings_eur", "DECIMAL(18,4)"),
    ("effective_monthly_cost_eur", "DECIMAL(18,4)"),
    ("estimated_net_benefit_eur", "DECIMAL(18,4)"),
    ("cost_basis_method", "VARCHAR"),
    ("expected_window_count", "INTEGER NOT NULL"),
    ("complete_window_count", "INTEGER NOT NULL"),
    ("missing_window_count", "INTEGER NOT NULL"),
    ("coverage_pct", "DECIMAL(9,4) NOT NULL"),
    ("duplicate_snapshot_count", "INTEGER NOT NULL"),
    ("conflicting_window_count", "INTEGER NOT NULL"),
    ("invalid_record_count", "INTEGER NOT NULL"),
    ("unknown_scope_timestamp_count", "INTEGER NOT NULL"),
    ("backfill_status", "VARCHAR NOT NULL"),
    ("source_last_period_end", "VARCHAR"),
    ("freshness_status", "VARCHAR NOT NULL"),  # fresh | stale | unknown
    ("freshness_age_minutes", "DECIMAL(18,2)"),
    ("freshness_limit_minutes", "INTEGER NOT NULL"),
    ("tariff_snapshot_id", "VARCHAR"),
    ("tariff_snapshot_json", "VARCHAR"),
    ("source_calculation_method", "VARCHAR"),
    ("source_evidence_contract_version", "VARCHAR"),
    ("reason_codes_json", "VARCHAR NOT NULL"),
    ("missing_fields_json", "VARCHAR NOT NULL"),
    ("remediation", "VARCHAR"),
    ("limitations_json", "VARCHAR NOT NULL"),
    ("source_entity_ids_json", "VARCHAR NOT NULL"),
    ("source_run_ids_json", "VARCHAR NOT NULL"),
    ("source_report_ingested_at", "VARCHAR"),
]

MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE = "mart_battery_plan_outcome_values"

MART_BATTERY_PLAN_OUTCOME_VALUES_COLUMNS: list[tuple[str, str]] = [
    ("assessment_id", "VARCHAR NOT NULL"),
    ("decision_month", "VARCHAR NOT NULL"),
    ("display_order", "INTEGER NOT NULL"),
    ("value_key", "VARCHAR NOT NULL"),
    ("value_label", "VARCHAR NOT NULL"),
    ("value_numeric", "DECIMAL(18,4)"),
    ("value_text", "VARCHAR"),
    ("unit", "VARCHAR"),
    # observed | derived | estimated | heuristic | user_entered
    ("value_status", "VARCHAR NOT NULL"),
    ("value_role", "VARCHAR NOT NULL"),  # actual | estimate | assumption | quality
    ("is_missing", "BOOLEAN NOT NULL"),
    ("source_reference", "VARCHAR"),
    ("note", "VARCHAR"),
]

VALUE_STATUSES = frozenset({"observed", "derived", "estimated", "heuristic", "user_entered"})
VALUE_ROLES = frozenset({"actual", "estimate", "assumption", "quality"})
VERDICTS = frozenset({"insufficient_evidence", "no_benefit_estimated", "benefit_estimated"})
