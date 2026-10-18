"""The named Kotiakku battery-plan decision (household outcome evidence loop).

See ``docs/plans/household-outcome-evidence-decision-plan.md`` ("Decision
definition"). Bump ``version`` whenever the question, window, thresholds,
outcome options or commitment lifecycle change; decision records pin the
version they were made under.

Version history:

- ``1.0.0`` — question, evidence window, insufficiency criteria, outcomes and a
  fixed 45-day follow-up.
- ``1.1.0`` — commitment lifecycle (HLA-K01): purpose, authorized owner,
  baseline, success measure, observation window (follow-up due derived from
  it), review triggers, stop conditions and fingerprinted evidence components
  for correction tracing (HLA-K02).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from packages.platform.decision_definitions import (
    DecisionBaseline,
    DecisionDefinition,
    DecisionEvidenceComponent,
    DecisionObservationWindow,
    DecisionOutcomeOption,
    DecisionOwner,
    DecisionReviewTrigger,
    DecisionStopCondition,
    DecisionSuccessMeasure,
)

BATTERY_PLAN_DECISION_KEY = "kotiakku_battery_plan_review"
BATTERY_PLAN_OUTCOME_PUBLICATION_KEY = "mart_battery_plan_outcome"
BATTERY_PLAN_OUTCOME_VALUES_PUBLICATION_KEY = "mart_battery_plan_outcome_values"

# The evidence must cover every five-minute window of the closed month; any
# gap is insufficient evidence rather than a scaled-up estimate.
BATTERY_PLAN_MIN_COVERAGE_PCT = 100.0
BATTERY_PLAN_FRESHNESS_LIMIT_MINUTES = 15

BATTERY_PLAN_BASELINE_VALUE_KEYS: tuple[str, ...] = (
    "estimated_savings_eur",
    "effective_monthly_cost_eur",
    "estimated_net_benefit_eur",
)

BATTERY_PLAN_DECISION = DecisionDefinition(
    decision_key=BATTERY_PLAN_DECISION_KEY,
    version="1.1.0",
    question=(
        "Over one closed household-local calendar month, do the Kotiakku "
        "battery-versus-no-battery estimated savings cover the battery plan's "
        "effective monthly cost, so that the current battery plan, tariff and "
        "contract need no review?"
    ),
    purpose=(
        "Keep the household's battery plan, tariff and contract only while observed "
        "economics justify them; reopen the question when the evidence or the plan changes."
    ),
    owner=DecisionOwner(
        role="operator",
        principal=None,
        description="Any authenticated household operator (permission control.decisions.write).",
    ),
    subject_publication_key=BATTERY_PLAN_OUTCOME_PUBLICATION_KEY,
    supporting_publication_keys=(BATTERY_PLAN_OUTCOME_VALUES_PUBLICATION_KEY,),
    subject_period_label="Closed decision month of the battery-plan outcome (YYYY-MM).",
    evidence_window=(
        "One closed calendar month in the household timezone, evaluated as "
        "complete five-minute source windows read from Home Assistant history "
        "and bounded by the assessment timestamp."
    ),
    evidence_that_could_change_decision=(
        "Estimated monthly savings moving above or below the effective monthly battery cost.",
        "A change to the battery cost basis (monthly cost, total cost, or akkureservihyvitys compensation).",
        "A tariff snapshot change for the month (tariff mode, transfer fees, margins).",
        "Further closed months showing a seasonal pattern that a single month does not.",
        "Observed bills contradicting the source estimate.",
    ),
    insufficient_evidence_criteria=(
        f"Measurement coverage below {BATTERY_PLAN_MIN_COVERAGE_PCT:g}% of expected five-minute windows.",
        f"Source measurements older than {BATTERY_PLAN_FRESHNESS_LIMIT_MINUTES} minutes at assessment time.",
        "Missing, invalid, conflicting or ambiguously scoped source records.",
        "Missing or mixed tariff snapshot for the month, or tariff signature mismatch.",
        "Missing savings estimate or battery cost basis, or source counters that disagree.",
        "Unsupported source evidence contract, calculation method, or period.",
        "Decision month not yet closed in the household timezone, or no source profile configured.",
    ),
    outcome_options=(
        DecisionOutcomeOption("keep_current_plan", "Keep the current battery plan, tariff and contract"),
        DecisionOutcomeOption("review_battery_plan", "Open a review of the battery plan, tariff or contract"),
        DecisionOutcomeOption(
            "change_tariff_or_contract",
            "Change tariff or contract (executed outside HLA by the household)",
        ),
        DecisionOutcomeOption(
            "defer_pending_evidence",
            "Explicit non-decision: defer until the evidence improves",
            is_non_decision=True,
        ),
    ),
    baseline=DecisionBaseline(
        description=(
            "The subject month's source estimate: estimated savings, the user-entered "
            "effective monthly battery cost and their difference. These are estimates and "
            "assumptions, never realized cash."
        ),
        value_keys=BATTERY_PLAN_BASELINE_VALUE_KEYS,
    ),
    success_measure=DecisionSuccessMeasure(
        key="realized_monthly_net_benefit_eur",
        description=(
            "Realized monthly net benefit over the observation window: observed bill "
            "savings attributable to the battery minus the effective monthly battery cost. "
            "Record it on the follow-up as an observed or user-entered value; without one "
            "the outcome stays unmeasured."
        ),
        unit="EUR/month",
        comparison="at_least",
        threshold=Decimal("0"),
    ),
    observation_window=DecisionObservationWindow(
        description=(
            "The first full household-local calendar month after the decision; the "
            "review is due 14 days after it closes so bills and the refresh can land, "
            "then every 30 days while the commitment stays active."
        ),
        kind="calendar_months_after_decision",
        length=1,
        review_grace_days=14,
        review_cadence_days=30,
    ),
    evidence_components=(
        DecisionEvidenceComponent(
            "source_windows",
            "Source windows, counters, savings estimate and contributing HA runs",
            "source_window",
        ),
        DecisionEvidenceComponent("tariff_snapshot", "Month tariff snapshot", "tariff_snapshot"),
        DecisionEvidenceComponent("entity_mapping", "Kotiakku HA entity mapping", "entity_mapping"),
        DecisionEvidenceComponent("cost_basis", "Battery cost basis", "cost_basis"),
    ),
    review_triggers=(
        DecisionReviewTrigger(
            "observation_window_closed",
            "The observation window has closed and the review grace period has passed.",
            "timed",
        ),
        DecisionReviewTrigger(
            "source_window_corrected",
            "HA history for the month was re-landed or corrected (new runs, windows or savings).",
            "evidence_change",
            ("source_windows",),
        ),
        DecisionReviewTrigger(
            "tariff_revised",
            "The month's tariff snapshot was revised.",
            "evidence_change",
            ("tariff_snapshot",),
        ),
        DecisionReviewTrigger(
            "entity_mapping_revised",
            "The Kotiakku entity mapping changed.",
            "evidence_change",
            ("entity_mapping",),
        ),
        DecisionReviewTrigger(
            "cost_basis_changed",
            "The battery cost basis changed.",
            "evidence_change",
            ("cost_basis",),
        ),
        DecisionReviewTrigger(
            "verdict_changed",
            "The recomputed verdict differs from the one the decision was made on.",
            "verdict_change",
        ),
    ),
    stop_conditions=(
        DecisionStopCondition(
            "battery_plan_ended",
            "The battery plan or its cost basis no longer exists (plan cancelled or battery removed).",
            reason_codes=("battery_cost_basis_missing",),
        ),
        DecisionStopCondition(
            "tariff_or_contract_changed",
            "The household changed tariff or contract; this commitment ends once the follow-up "
            "records the realized result, and a new decision opens a new commitment.",
            outcome_keys=("change_tariff_or_contract",),
        ),
        DecisionStopCondition(
            "purpose_expired",
            "The owner ends the commitment because its purpose no longer applies.",
        ),
    ),
    authorization_boundary=(
        "Review-only. A verdict or recorded decision is not authorization to "
        "change a tariff, contract or battery behaviour; HLA holds no device "
        "credentials and exposes no actuation path. Any device change runs "
        "through Home Assistant under a separate, target-specific operator approval."
    ),
)


def battery_plan_evidence_components(outcome_row: Mapping[str, Any]) -> dict[str, Any]:
    """Fingerprinted inputs of one ``mart_battery_plan_outcome`` row.

    Excludes the assessment timestamp and freshness age, so re-assessing
    unchanged evidence keeps the same fingerprint; any re-landed source run,
    window counter, savings, tariff, mapping or cost-basis change alters it.
    Works on live rows and on decision evidence snapshots alike.
    """
    return {
        "source_windows": {
            "source_run_ids": sorted(_json_value(outcome_row.get("source_run_ids_json"), [])),
            "source_report_ingested_at": outcome_row.get("source_report_ingested_at"),
            "source_last_period_end": outcome_row.get("source_last_period_end"),
            "expected_window_count": _number(outcome_row.get("expected_window_count")),
            "complete_window_count": _number(outcome_row.get("complete_window_count")),
            "missing_window_count": _number(outcome_row.get("missing_window_count")),
            "duplicate_snapshot_count": _number(outcome_row.get("duplicate_snapshot_count")),
            "conflicting_window_count": _number(outcome_row.get("conflicting_window_count")),
            "invalid_record_count": _number(outcome_row.get("invalid_record_count")),
            "estimated_savings_eur": _number(outcome_row.get("estimated_savings_eur")),
            "source_evidence_contract_version": outcome_row.get(
                "source_evidence_contract_version"
            ),
            "source_calculation_method": outcome_row.get("source_calculation_method"),
        },
        "tariff_snapshot": {
            "tariff_snapshot_id": outcome_row.get("tariff_snapshot_id"),
            "tariff_snapshot": _json_value(outcome_row.get("tariff_snapshot_json"), None),
        },
        "entity_mapping": _json_value(outcome_row.get("source_entity_ids_json"), {}),
        "cost_basis": {
            "effective_monthly_cost_eur": _number(outcome_row.get("effective_monthly_cost_eur")),
            "cost_basis_method": outcome_row.get("cost_basis_method"),
        },
    }


def battery_plan_baseline(outcome_row: Mapping[str, Any]) -> dict[str, Any]:
    statuses = {
        "estimated_savings_eur": "estimated",
        "effective_monthly_cost_eur": "user_entered",
        "estimated_net_benefit_eur": "estimated",
    }
    return {
        key: {
            "value": _number(outcome_row.get(key)),
            "status": statuses[key],
            "unit": "EUR/month",
            "is_missing": outcome_row.get(key) is None,
        }
        for key in BATTERY_PLAN_BASELINE_VALUE_KEYS
    }


def _json_value(value: object, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except ValueError:
        return default


def _number(value: object) -> str | None:
    """Canonical text for a numeric value so live rows and snapshots compare equal."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    if not number.is_finite():
        return str(value)
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")
