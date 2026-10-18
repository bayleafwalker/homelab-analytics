"""The named Kotiakku battery-plan decision (household outcome evidence loop).

See ``docs/plans/household-outcome-evidence-decision-plan.md`` ("Decision
definition"). Bump ``version`` whenever the question, window, thresholds or
outcome options change; decision records pin the version they were made under.
"""

from __future__ import annotations

from packages.platform.decision_definitions import (
    DecisionDefinition,
    DecisionOutcomeOption,
)

BATTERY_PLAN_DECISION_KEY = "kotiakku_battery_plan_review"
BATTERY_PLAN_OUTCOME_PUBLICATION_KEY = "mart_battery_plan_outcome"
BATTERY_PLAN_OUTCOME_VALUES_PUBLICATION_KEY = "mart_battery_plan_outcome_values"

# The evidence must cover every five-minute window of the closed month; any
# gap is insufficient evidence rather than a scaled-up estimate.
BATTERY_PLAN_MIN_COVERAGE_PCT = 100.0
BATTERY_PLAN_FRESHNESS_LIMIT_MINUTES = 15

BATTERY_PLAN_DECISION = DecisionDefinition(
    decision_key=BATTERY_PLAN_DECISION_KEY,
    version="1.0.0",
    question=(
        "Over one closed household-local calendar month, do the Kotiakku "
        "battery-versus-no-battery estimated savings cover the battery plan's "
        "effective monthly cost, so that the current battery plan, tariff and "
        "contract need no review?"
    ),
    decision_maker_role="operator",
    subject_publication_key=BATTERY_PLAN_OUTCOME_PUBLICATION_KEY,
    supporting_publication_keys=(BATTERY_PLAN_OUTCOME_VALUES_PUBLICATION_KEY,),
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
    follow_up_default_days=45,
    authorization_boundary=(
        "Review-only. A verdict or recorded decision is not authorization to "
        "change a tariff, contract or battery behaviour; HLA holds no device "
        "credentials and exposes no actuation path. Any device change runs "
        "through Home Assistant under a separate, target-specific operator approval."
    ),
)
