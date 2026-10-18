"""Declared, versioned household decision questions for the decision ledger.

A decision definition names one question whose answer could change a real
household choice, the role (and optionally the principal) authorized to own
it, the evidence window, what evidence could change the answer, and what
counts as insufficient evidence. It deliberately does not preselect an
action: the outcome options are the choices a decision-maker may record,
including an explicit non-decision.

A definition also declares the *commitment lifecycle* a recorded decision
enters (HLA-K01): its purpose, authorized owner, baseline, success measure,
observation window, review triggers and stop conditions. The ledger enforces
these at record time and derives the commitment state from append-only
lifecycle events.

Definitions are platform-neutral data; domains declare concrete definitions
and the composition layer registers them.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

OBSERVATION_WINDOW_KINDS = frozenset({"calendar_months_after_decision", "days_after_decision"})
REVIEW_TRIGGER_KINDS = frozenset({"timed", "evidence_change", "verdict_change"})
SUCCESS_COMPARISONS = frozenset({"at_least", "at_most"})
CORRECTION_KINDS = frozenset(
    {
        "source_window",
        "tariff_snapshot",
        "entity_mapping",
        "cost_basis",
        "contract_terms",
        "market_reference",
        "usage_basis",
    }
)


def evidence_fingerprint(components: dict[str, Any]) -> str:
    """Stable fingerprint of the evidence inputs a decision was made on.

    Unlike a publication row reference (which may include the assessment
    timestamp), the fingerprint changes only when an input changes, so a
    plain re-assessment of unchanged evidence does not supersede a decision.
    """
    payload = json.dumps(components, sort_keys=True, separators=(",", ":"), default=str)
    return "evf_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class DecisionSubjectEvidence:
    """The exact reporting-layer row a decision is made on."""

    publication_key: str
    schema_version: str
    period: str
    row_ref: str
    verdict: str
    reason_codes: tuple[str, ...]
    lineage_reference: dict[str, Any]
    snapshot: dict[str, Any] = field(default_factory=dict)
    # Declared baseline values ({value_key: {"value", "status", "unit"}});
    # an absent value stays ``None`` rather than becoming zero.
    baseline: dict[str, Any] = field(default_factory=dict)
    # Fingerprinted evidence inputs keyed by declared component key.
    evidence_components: dict[str, Any] = field(default_factory=dict)

    @property
    def evidence_fingerprint(self) -> str:
        return evidence_fingerprint(self.evidence_components)


@dataclass(frozen=True)
class DecisionOutcomeOption:
    key: str
    label: str
    is_non_decision: bool = False


@dataclass(frozen=True)
class DecisionOwner:
    """Who may own the commitment: a role, optionally narrowed to a principal."""

    role: str
    principal: str | None = None
    description: str = ""


@dataclass(frozen=True)
class DecisionObservationWindow:
    """When the realized result of a decision is observed and reviewed."""

    description: str
    kind: str
    length: int
    review_grace_days: int
    review_cadence_days: int

    def __post_init__(self) -> None:
        if self.kind not in OBSERVATION_WINDOW_KINDS:
            raise ValueError(f"Unknown observation window kind: {self.kind}")
        if self.length < 1 or self.review_grace_days < 0 or self.review_cadence_days < 1:
            raise ValueError("Observation window lengths must be positive.")

    def window_for(self, decided_on: date) -> tuple[date, date]:
        """Inclusive observation window following a decision made on ``decided_on``."""
        if self.kind == "days_after_decision":
            return decided_on + timedelta(days=1), decided_on + timedelta(days=self.length)
        start = _add_months(decided_on.replace(day=1), 1)
        last_month = _add_months(start, self.length - 1)
        end = last_month.replace(day=calendar.monthrange(last_month.year, last_month.month)[1])
        return start, end

    def review_due_on(self, decided_on: date) -> date:
        return self.window_for(decided_on)[1] + timedelta(days=self.review_grace_days)


@dataclass(frozen=True)
class DecisionBaseline:
    description: str
    value_keys: tuple[str, ...]


@dataclass(frozen=True)
class DecisionSuccessMeasure:
    """How a follow-up's realized value is judged against the commitment."""

    key: str
    description: str
    unit: str
    comparison: str
    threshold: Decimal
    accepted_value_statuses: tuple[str, ...] = ("observed", "user_entered")

    def __post_init__(self) -> None:
        if self.comparison not in SUCCESS_COMPARISONS:
            raise ValueError(f"Unknown success comparison: {self.comparison}")

    def evaluate(self, value: Decimal | None, value_status: str | None) -> str:
        """``met`` / ``not_met`` / ``unmeasured`` — never a guess."""
        if value is None or value_status not in self.accepted_value_statuses:
            return "unmeasured"
        if self.comparison == "at_least":
            return "met" if value >= self.threshold else "not_met"
        return "met" if value <= self.threshold else "not_met"


@dataclass(frozen=True)
class DecisionEvidenceComponent:
    """One fingerprinted evidence input and the kind of correction it signals."""

    key: str
    label: str
    correction_kind: str

    def __post_init__(self) -> None:
        if self.correction_kind not in CORRECTION_KINDS:
            raise ValueError(f"Unknown correction kind: {self.correction_kind}")


@dataclass(frozen=True)
class DecisionReviewTrigger:
    key: str
    description: str
    kind: str
    evidence_components: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in REVIEW_TRIGGER_KINDS:
            raise ValueError(f"Unknown review trigger kind: {self.kind}")


@dataclass(frozen=True)
class DecisionStopCondition:
    """When the commitment ends.

    ``outcome_keys`` / ``reason_codes`` let the ledger flag a met condition at
    record time (or when later evidence carries the reason code). Flagging
    recommends a stop; only the owner stops a commitment. A condition with
    neither is an operator stop.
    """

    key: str
    description: str
    outcome_keys: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def met_by(self, *, outcome: str, reason_codes: tuple[str, ...]) -> bool:
        return outcome in self.outcome_keys or any(
            code in self.reason_codes for code in reason_codes
        )


@dataclass(frozen=True)
class DecisionDefinition:
    decision_key: str
    version: str
    question: str
    subject_publication_key: str
    evidence_window: str
    evidence_that_could_change_decision: tuple[str, ...]
    insufficient_evidence_criteria: tuple[str, ...]
    outcome_options: tuple[DecisionOutcomeOption, ...]
    authorization_boundary: str
    supporting_publication_keys: tuple[str, ...] = field(default_factory=tuple)
    subject_period_label: str = "Period of the subject publication row (YYYY-MM)."
    # Commitment lifecycle (HLA-K01).
    purpose: str = field(kw_only=True)
    owner: DecisionOwner = field(kw_only=True)
    baseline: DecisionBaseline = field(kw_only=True)
    success_measure: DecisionSuccessMeasure = field(kw_only=True)
    observation_window: DecisionObservationWindow = field(kw_only=True)
    evidence_components: tuple[DecisionEvidenceComponent, ...] = field(kw_only=True)
    review_triggers: tuple[DecisionReviewTrigger, ...] = field(kw_only=True)
    stop_conditions: tuple[DecisionStopCondition, ...] = field(kw_only=True)

    def __post_init__(self) -> None:
        keys = [option.key for option in self.outcome_options]
        if len(set(keys)) != len(keys):
            raise ValueError(f"Duplicate outcome option keys for {self.decision_key}")
        if not any(option.is_non_decision for option in self.outcome_options):
            raise ValueError(
                f"Decision {self.decision_key} must offer an explicit non-decision outcome"
            )
        if not self.purpose.strip():
            raise ValueError(f"Decision {self.decision_key} must state its purpose")
        component_keys = {component.key for component in self.evidence_components}
        for trigger in self.review_triggers:
            unknown = set(trigger.evidence_components) - component_keys
            if unknown:
                raise ValueError(
                    f"Trigger {trigger.key} names undeclared evidence components {sorted(unknown)}"
                )
        if not any(trigger.kind == "timed" for trigger in self.review_triggers):
            raise ValueError(f"Decision {self.decision_key} needs a timed review trigger")
        if not self.stop_conditions:
            raise ValueError(f"Decision {self.decision_key} needs at least one stop condition")
        for condition in self.stop_conditions:
            unknown = set(condition.outcome_keys) - set(keys)
            if unknown:
                raise ValueError(
                    f"Stop condition {condition.key} names unknown outcomes {sorted(unknown)}"
                )

    @property
    def decision_maker_role(self) -> str:
        return self.owner.role

    def outcome_option(self, key: str) -> DecisionOutcomeOption | None:
        for option in self.outcome_options:
            if option.key == key:
                return option
        return None

    def evidence_component(self, key: str) -> DecisionEvidenceComponent | None:
        for component in self.evidence_components:
            if component.key == key:
                return component
        return None

    def stop_condition(self, key: str) -> DecisionStopCondition | None:
        for condition in self.stop_conditions:
            if condition.key == key:
                return condition
        return None

    def triggers_for_components(self, component_keys: tuple[str, ...]) -> tuple[str, ...]:
        changed = set(component_keys)
        return tuple(
            trigger.key
            for trigger in self.review_triggers
            if trigger.kind == "evidence_change" and changed & set(trigger.evidence_components)
        )

    def to_dict(self) -> dict[str, Any]:
        window = self.observation_window
        measure = self.success_measure
        return {
            "decision_key": self.decision_key,
            "version": self.version,
            "question": self.question,
            "purpose": self.purpose,
            "decision_maker_role": self.owner.role,
            "owner": {
                "role": self.owner.role,
                "principal": self.owner.principal,
                "description": self.owner.description,
            },
            "subject_publication_key": self.subject_publication_key,
            "subject_period_label": self.subject_period_label,
            "supporting_publication_keys": list(self.supporting_publication_keys),
            "evidence_window": self.evidence_window,
            "evidence_that_could_change_decision": list(
                self.evidence_that_could_change_decision
            ),
            "insufficient_evidence_criteria": list(self.insufficient_evidence_criteria),
            "outcome_options": [
                {
                    "key": option.key,
                    "label": option.label,
                    "is_non_decision": option.is_non_decision,
                }
                for option in self.outcome_options
            ],
            "baseline": {
                "description": self.baseline.description,
                "value_keys": list(self.baseline.value_keys),
            },
            "success_measure": {
                "key": measure.key,
                "description": measure.description,
                "unit": measure.unit,
                "comparison": measure.comparison,
                "threshold": str(measure.threshold),
                "accepted_value_statuses": list(measure.accepted_value_statuses),
            },
            "observation_window": {
                "description": window.description,
                "kind": window.kind,
                "length": window.length,
                "review_grace_days": window.review_grace_days,
                "review_cadence_days": window.review_cadence_days,
            },
            "evidence_components": [
                {
                    "key": component.key,
                    "label": component.label,
                    "correction_kind": component.correction_kind,
                }
                for component in self.evidence_components
            ],
            "review_triggers": [
                {
                    "key": trigger.key,
                    "description": trigger.description,
                    "kind": trigger.kind,
                    "evidence_components": list(trigger.evidence_components),
                }
                for trigger in self.review_triggers
            ],
            "stop_conditions": [
                {
                    "key": condition.key,
                    "description": condition.description,
                    "outcome_keys": list(condition.outcome_keys),
                    "reason_codes": list(condition.reason_codes),
                }
                for condition in self.stop_conditions
            ],
            "authorization_boundary": self.authorization_boundary,
        }


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
