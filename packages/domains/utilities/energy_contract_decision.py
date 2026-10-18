"""The named electricity-contract review decision: keep or switch the contract.

A second decision domain on the generic decision ledger. The subject is one
active electricity contract as published in ``mart_electricity_price_current``,
assessed against the other electricity contracts and quotes the household has
recorded (same mart), the contract review and renewal marts, and the
electricity cost/usage trend (``mart_utility_cost_trend_monthly``). All inputs
are reporting-layer rows; this module only derives the review assessment.

Evidence guard: no verdict other than ``insufficient_evidence`` unless the
contract is active, has an energy price, at least one comparable alternative
is recorded with matching currency and unit, and twelve billing months of
electricity usage exist. Estimates are never realized savings; the market
reference is only what the household recorded, not a market quote.

Bump ``version`` whenever the question, thresholds, outcomes or lifecycle
change; decision records pin the version they were made under.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
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
    evidence_fingerprint,
)

ENERGY_CONTRACT_DECISION_KEY = "electricity_contract_keep_or_switch"
ENERGY_CONTRACT_SUBJECT_PUBLICATION_KEY = "mart_electricity_price_current"
ENERGY_CONTRACT_SUPPORTING_PUBLICATION_KEYS: tuple[str, ...] = (
    "mart_contract_review_candidates",
    "mart_contract_renewal_watchlist",
    "mart_utility_cost_trend_monthly",
)
ENERGY_CONTRACT_SUBJECT_SCHEMA_NAME = "electricity_price_current"

# Twelve billing months so one season cannot stand in for a year.
ENERGY_CONTRACT_MIN_USAGE_MONTHS = 12
# An alternative must be estimated at least this much cheaper per year before
# the evidence suggests a switch review; smaller gaps are within noise.
ENERGY_CONTRACT_SWITCH_THRESHOLD_PCT = Decimal("5")
ENERGY_CONTRACT_RENEWAL_LOOKAHEAD_DAYS = 90

ENERGY_CONTRACT_VERDICTS = (
    "insufficient_evidence",
    "current_contract_competitive",
    "alternative_estimated_cheaper",
)

ENERGY_CONTRACT_BASELINE_VALUE_KEYS: tuple[str, ...] = (
    "estimated_annual_cost_current_eur",
    "estimated_annual_cost_best_alternative_eur",
    "estimated_annual_difference_eur",
)

_REMEDIATION: dict[str, str] = {
    "contract_not_found": (
        "Land a contract price file that includes this electricity contract, then refresh."
    ),
    "contract_not_active": "The contract is no longer active; review the current contract instead.",
    "energy_price_missing": (
        "Record the contract's per-kWh energy price component in the contract price file."
    ),
    "no_comparable_alternative": (
        "Record at least one alternative electricity offer (quote) in the contract price "
        "file so the contract can be compared."
    ),
    "currency_or_unit_mismatch": (
        "Record alternatives in the same currency and quantity unit as the current contract."
    ),
    "usage_history_incomplete": (
        f"Land at least {ENERGY_CONTRACT_MIN_USAGE_MONTHS} months of electricity bills or "
        "usage so annual cost can be estimated across seasons."
    ),
}

ENERGY_CONTRACT_DECISION = DecisionDefinition(
    decision_key=ENERGY_CONTRACT_DECISION_KEY,
    version="1.0.0",
    question=(
        "Given the last twelve billing months of household electricity usage, is the "
        "current electricity contract estimated to cost no more per year than the best "
        "alternative the household has recorded, so the contract can be kept?"
    ),
    purpose=(
        "Keep the household electricity contract only while recorded alternatives are not "
        "materially cheaper for the household's own usage; reopen when prices, offers or "
        "usage change."
    ),
    owner=DecisionOwner(
        role="operator",
        principal=None,
        description="Any authenticated household operator (permission control.decisions.write).",
    ),
    subject_publication_key=ENERGY_CONTRACT_SUBJECT_PUBLICATION_KEY,
    supporting_publication_keys=ENERGY_CONTRACT_SUPPORTING_PUBLICATION_KEYS,
    subject_period_label="Contract identifier (contract_id) of an active electricity contract.",
    evidence_window=(
        "The current contract terms and recorded alternatives as published now, priced "
        f"against the latest {ENERGY_CONTRACT_MIN_USAGE_MONTHS} billing months of "
        "electricity usage."
    ),
    evidence_that_could_change_decision=(
        "A price change to the current contract (energy price or base fee).",
        "A new or changed alternative offer recorded in the contract price file.",
        "Household electricity usage moving materially across the trailing year.",
        "The contract approaching its renewal date or ending.",
        "Observed bills after a switch contradicting the estimate.",
    ),
    insufficient_evidence_criteria=(
        "The contract is not published, not active, or not an electricity contract.",
        "No per-kWh energy price is recorded for the contract.",
        "No comparable alternative (same currency and unit) is recorded.",
        f"Fewer than {ENERGY_CONTRACT_MIN_USAGE_MONTHS} billing months of electricity usage.",
    ),
    outcome_options=(
        DecisionOutcomeOption("keep_current_contract", "Keep the current electricity contract"),
        DecisionOutcomeOption(
            "switch_contract",
            "Switch to an alternative contract (executed outside HLA by the household)",
        ),
        DecisionOutcomeOption(
            "request_new_quotes", "Request new quotes before deciding"
        ),
        DecisionOutcomeOption(
            "defer_pending_evidence",
            "Explicit non-decision: defer until the evidence improves",
            is_non_decision=True,
        ),
    ),
    baseline=DecisionBaseline(
        description=(
            "Estimated annual cost of the current contract and of the cheapest recorded "
            "alternative over the trailing usage year, and their difference. Estimates only."
        ),
        value_keys=ENERGY_CONTRACT_BASELINE_VALUE_KEYS,
    ),
    success_measure=DecisionSuccessMeasure(
        key="realized_annual_cost_change_eur",
        description=(
            "Realized change in annualized electricity cost versus the baseline estimate of "
            "the current contract, from bills over the observation window (negative means "
            "the household pays less). Record it on the follow-up as an observed or "
            "user-entered value; without one the outcome stays unmeasured."
        ),
        unit="EUR/year",
        comparison="at_most",
        threshold=Decimal("0"),
    ),
    observation_window=DecisionObservationWindow(
        description=(
            "Ninety days of bills after the decision; the review is due 21 days later so "
            "the last bill can land, then every 180 days while the commitment stays active."
        ),
        kind="days_after_decision",
        length=90,
        review_grace_days=21,
        review_cadence_days=180,
    ),
    evidence_components=(
        DecisionEvidenceComponent(
            "contract_terms", "Current contract price components", "contract_terms"
        ),
        DecisionEvidenceComponent(
            "alternatives", "Recorded alternative electricity offers", "market_reference"
        ),
        DecisionEvidenceComponent(
            "usage_basis", "Trailing electricity usage and cost months", "usage_basis"
        ),
    ),
    review_triggers=(
        DecisionReviewTrigger(
            "observation_window_closed",
            "The observation window has closed and the review grace period has passed.",
            "timed",
        ),
        DecisionReviewTrigger(
            "contract_terms_changed",
            "The current contract's prices were corrected or changed.",
            "evidence_change",
            ("contract_terms",),
        ),
        DecisionReviewTrigger(
            "alternatives_changed",
            "An alternative offer was recorded, corrected or removed.",
            "evidence_change",
            ("alternatives",),
        ),
        DecisionReviewTrigger(
            "usage_basis_changed",
            "Electricity usage months were re-landed or corrected.",
            "evidence_change",
            ("usage_basis",),
        ),
        DecisionReviewTrigger(
            "verdict_changed",
            "The recomputed verdict differs from the one the decision was made on.",
            "verdict_change",
        ),
    ),
    stop_conditions=(
        DecisionStopCondition(
            "contract_ended",
            "The contract is no longer active (ended or replaced).",
            reason_codes=("contract_not_active",),
        ),
        DecisionStopCondition(
            "contract_switched",
            "The household switched contract; this commitment ends once the follow-up "
            "records the realized result, and the new contract opens a new commitment.",
            outcome_keys=("switch_contract",),
        ),
        DecisionStopCondition(
            "purpose_expired",
            "The owner ends the commitment because its purpose no longer applies.",
        ),
    ),
    authorization_boundary=(
        "Review-only. A verdict or recorded decision is not authorization to switch or "
        "cancel a contract; HLA holds no supplier credentials and exposes no contract "
        "action. The household executes any switch outside HLA."
    ),
)


def assess_energy_contract_review(
    *,
    contract_id: str,
    price_rows: Sequence[Mapping[str, Any]],
    review_candidates: Sequence[Mapping[str, Any]],
    renewal_watchlist: Sequence[Mapping[str, Any]],
    cost_trend_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Assess one electricity contract from reporting rows.

    ``price_rows`` are ``mart_electricity_price_current`` rows (every
    recorded electricity contract and quote); ``cost_trend_rows`` are
    electricity rows of ``mart_utility_cost_trend_monthly``.
    """
    reasons: list[str] = []
    contract_rows = [row for row in price_rows if str(row.get("contract_id")) == contract_id]
    current = _contract_terms(contract_rows)
    if not contract_rows:
        reasons.append("contract_not_found")
    elif any(str(row.get("status")) != "active" for row in contract_rows):
        reasons.append("contract_not_active")
    if contract_rows and current["energy_unit_price"] is None:
        reasons.append("energy_price_missing")

    alternatives_by_id: dict[str, list[Mapping[str, Any]]] = {}
    for row in price_rows:
        other_id = str(row.get("contract_id"))
        if other_id != contract_id and str(row.get("status")) == "active":
            alternatives_by_id.setdefault(other_id, []).append(row)
    alternatives = [_contract_terms(rows) for _, rows in sorted(alternatives_by_id.items())]
    comparable = [
        alt
        for alt in alternatives
        if alt["energy_unit_price"] is not None
        and alt["currency"] == current["currency"]
        and alt["quantity_unit"] == current["quantity_unit"]
    ]
    if contract_rows and not alternatives:
        reasons.append("no_comparable_alternative")
    elif contract_rows and alternatives and not comparable:
        reasons.append("currency_or_unit_mismatch")

    usage_months = sorted(
        (
            row
            for row in cost_trend_rows
            if str(row.get("utility_type")) == "electricity"
        ),
        key=lambda row: str(row.get("billing_month")),
    )[-ENERGY_CONTRACT_MIN_USAGE_MONTHS:]
    usage_total = sum(
        (_decimal(row.get("usage_amount")) or Decimal(0) for row in usage_months), Decimal(0)
    )
    if len(usage_months) < ENERGY_CONTRACT_MIN_USAGE_MONTHS:
        reasons.append("usage_history_incomplete")

    annual_current = _annual_cost(current, usage_total) if not reasons else None
    best = None
    if not reasons:
        best = min(comparable, key=lambda alt: (_annual_cost(alt, usage_total), alt["contract_id"]))
    annual_best = _annual_cost(best, usage_total) if best is not None else None
    difference = (
        annual_current - annual_best
        if annual_current is not None and annual_best is not None
        else None
    )
    if reasons or annual_current is None or difference is None:
        verdict = "insufficient_evidence"
    elif annual_current > 0 and difference * 100 / annual_current > ENERGY_CONTRACT_SWITCH_THRESHOLD_PCT:
        verdict = "alternative_estimated_cheaper"
    else:
        verdict = "current_contract_competitive"

    candidate = next(
        (row for row in review_candidates if str(row.get("contract_id")) == contract_id), None
    )
    renewal = next(
        (row for row in renewal_watchlist if str(row.get("contract_id")) == contract_id), None
    )
    limitations = [
        "The comparison uses only alternatives recorded in HLA; it is not a market quote.",
        "Annual cost is estimated from the trailing usage year at today's prices; it is "
        "not a forecast and not realized cash.",
        "Transfer (network) fees are excluded: they do not change with the energy contract.",
        "No recommendation authorizes switching or cancelling a contract.",
    ]
    components = {
        "contract_terms": _terms_component(contract_rows),
        "alternatives": {
            alt_id: _terms_component(rows) for alt_id, rows in sorted(alternatives_by_id.items())
        },
        "usage_basis": [
            {
                "billing_month": str(row.get("billing_month")),
                "usage_amount": _text(row.get("usage_amount")),
                "total_cost": _text(row.get("total_cost")),
            }
            for row in usage_months
        ],
    }
    fingerprint = evidence_fingerprint(components)
    return {
        "assessment_id": "ecr_" + fingerprint.removeprefix("evf_"),
        "decision_key": ENERGY_CONTRACT_DECISION_KEY,
        "decision_version": ENERGY_CONTRACT_DECISION.version,
        "contract_id": contract_id,
        "contract_name": current["contract_name"],
        "provider": current["provider"],
        "status": contract_rows[0].get("status") if contract_rows else None,
        "currency": current["currency"],
        "quantity_unit": current["quantity_unit"],
        "energy_unit_price": _text(current["energy_unit_price"]),
        "monthly_base_fee": _text(current["monthly_base_fee"]),
        "valid_from": _text(contract_rows[0].get("valid_from")) if contract_rows else None,
        "valid_to": _text(contract_rows[0].get("valid_to")) if contract_rows else None,
        "comparable_alternative_count": len(comparable),
        "best_alternative_contract_id": best["contract_id"] if best else None,
        "best_alternative_provider": best["provider"] if best else None,
        "usage_month_count": len(usage_months),
        "usage_months_from": str(usage_months[0].get("billing_month")) if usage_months else None,
        "usage_months_to": str(usage_months[-1].get("billing_month")) if usage_months else None,
        "trailing_usage_amount": _text(usage_total) if usage_months else None,
        "estimated_annual_cost_current_eur": _text(annual_current),
        "estimated_annual_cost_best_alternative_eur": _text(annual_best),
        "estimated_annual_difference_eur": _text(difference),
        "review_candidate_reason": candidate.get("reason") if candidate else None,
        "review_candidate_score": candidate.get("score") if candidate else None,
        "renewal_date": _text(renewal.get("renewal_date")) if renewal else None,
        "days_until_renewal": renewal.get("days_until_renewal") if renewal else None,
        "verdict": verdict,
        "evidence_status": "insufficient" if verdict == "insufficient_evidence" else "qualified",
        "reason_codes": reasons,
        "remediation": " ".join(_REMEDIATION[code] for code in reasons) or None,
        "limitations": limitations,
        "recommendation_scope": "review_only",
        "actuation_authorized": False,
        "value_disclosures": _value_disclosures(),
        "evidence_components": components,
        "evidence_fingerprint": fingerprint,
    }


def energy_contract_baseline(assessment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: {
            "value": assessment.get(key),
            "status": "estimated",
            "unit": "EUR/year",
            "is_missing": assessment.get(key) is None,
        }
        for key in ENERGY_CONTRACT_BASELINE_VALUE_KEYS
    }


def energy_contract_ids(price_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted({str(row.get("contract_id")) for row in price_rows if row.get("contract_id")})


def _value_disclosures() -> dict[str, str]:
    return {
        "energy_unit_price": "observed (contract price file)",
        "monthly_base_fee": "observed (contract price file)",
        "trailing_usage_amount": "observed (bills / usage)",
        "estimated_annual_cost_current_eur": "estimated",
        "estimated_annual_cost_best_alternative_eur": "estimated",
        "estimated_annual_difference_eur": "estimated",
    }


def _contract_terms(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    energy = next((row for row in rows if str(row.get("price_component")) == "energy"), None)
    base_fee = next(
        (
            row
            for row in rows
            if str(row.get("price_component")) == "base_fee"
            and str(row.get("billing_cycle")) == "monthly"
        ),
        None,
    )
    first = rows[0] if rows else {}
    return {
        "contract_id": str(first.get("contract_id")) if rows else None,
        "contract_name": first.get("contract_name"),
        "provider": first.get("provider"),
        "currency": (energy or first).get("currency") if rows else None,
        "quantity_unit": energy.get("quantity_unit") if energy else None,
        "energy_unit_price": _decimal(energy.get("unit_price")) if energy else None,
        "monthly_base_fee": _decimal(base_fee.get("unit_price")) if base_fee else Decimal(0),
    }


def _annual_cost(terms: Mapping[str, Any] | None, usage_total: Decimal) -> Decimal:
    if terms is None or terms.get("energy_unit_price") is None:
        return Decimal(0)
    cost = usage_total * terms["energy_unit_price"] + 12 * terms["monthly_base_fee"]
    return cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _terms_component(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "price_component": str(row.get("price_component")),
                "billing_cycle": str(row.get("billing_cycle")),
                "unit_price": _text(row.get("unit_price")),
                "currency": row.get("currency"),
                "quantity_unit": row.get("quantity_unit"),
                "valid_from": _text(row.get("valid_from")),
                "valid_to": _text(row.get("valid_to")),
                "status": row.get("status"),
            }
            for row in rows
        ),
        key=lambda item: (item["price_component"], item["billing_cycle"], str(item["valid_from"])),
    )


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    number = _decimal(value)
    if number is None:
        return str(value)
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")
