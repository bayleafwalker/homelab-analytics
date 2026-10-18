"""Declared, versioned household decision questions for the decision ledger.

A decision definition names one question whose answer could change a real
household choice, the role authorized to decide it, the evidence window, what
evidence could change the answer, and what counts as insufficient evidence. It
deliberately does not preselect an action: the outcome options are the choices
a decision-maker may record, including an explicit non-decision.

Definitions are platform-neutral data; domains declare concrete definitions
and the composition layer registers them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DecisionOutcomeOption:
    key: str
    label: str
    is_non_decision: bool = False


@dataclass(frozen=True)
class DecisionDefinition:
    decision_key: str
    version: str
    question: str
    decision_maker_role: str
    subject_publication_key: str
    evidence_window: str
    evidence_that_could_change_decision: tuple[str, ...]
    insufficient_evidence_criteria: tuple[str, ...]
    outcome_options: tuple[DecisionOutcomeOption, ...]
    follow_up_default_days: int
    authorization_boundary: str
    supporting_publication_keys: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        keys = [option.key for option in self.outcome_options]
        if len(set(keys)) != len(keys):
            raise ValueError(f"Duplicate outcome option keys for {self.decision_key}")
        if not any(option.is_non_decision for option in self.outcome_options):
            raise ValueError(
                f"Decision {self.decision_key} must offer an explicit non-decision outcome"
            )

    def outcome_option(self, key: str) -> DecisionOutcomeOption | None:
        for option in self.outcome_options:
            if option.key == key:
                return option
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_key": self.decision_key,
            "version": self.version,
            "question": self.question,
            "decision_maker_role": self.decision_maker_role,
            "subject_publication_key": self.subject_publication_key,
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
            "follow_up_default_days": self.follow_up_default_days,
            "authorization_boundary": self.authorization_boundary,
        }
