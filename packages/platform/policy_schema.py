"""Declarative rule schema for operator-authored policy definitions.

Supports three initial rule kinds:
  - publication_value_comparison
  - publication_freshness_comparison
  - ha_helper_state_comparison

Arbitrary code execution is rejected by design: rules are declarative
comparisons only, with an explicit allowlist of operators.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

RULE_SCHEMA_VERSION = "1.0"

ALLOWED_RULE_KINDS = frozenset({
    "publication_value_comparison",
    "publication_freshness_comparison",
    "ha_helper_state_comparison",
})


class ComparisonOperator(StrEnum):
    """Operators the evaluator actually implements.

    ``in`` and ``not_in`` were previously accepted here but were never
    implemented: the evaluator's comparison falls through to ``False`` for an
    unknown operator, so such a rule validated, saved and then quietly never
    fired. They are retired rather than implemented — the schema has a single
    scalar ``threshold`` with nowhere to put a set — and are rejected with an
    explicit message by :func:`parse_rule_document`.
    """

    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"


# Fields that were declared on the rule models, persisted, and never read by
# the evaluator. A control that does nothing is worse than an absent one, so
# they are rejected with a message naming the retirement rather than silently
# accepted. Retiring them keeps the authoring form from offering them.
_RETIRED_RULE_FIELDS = {
    "verdict_mapping": (
        "verdict_mapping was accepted and stored but never read by the "
        "evaluator, so it changed nothing. It has been retired; remove it "
        "from the rule document."
    ),
    "allowed_freshness_states": (
        "allowed_freshness_states was accepted and stored but never consulted "
        "by the freshness evaluator, which compares only against "
        "threshold_hours. It has been retired; remove it from the rule "
        "document."
    ),
}

_RETIRED_OPERATORS = {
    "in": (
        "operator 'in' was accepted but never implemented; a rule using it "
        "silently never fired. Use an explicit comparison instead."
    ),
    "not_in": (
        "operator 'not_in' was accepted but never implemented; a rule using "
        "it silently never fired. Use an explicit comparison instead."
    ),
}


class PublicationValueComparisonRule(BaseModel):
    rule_kind: Literal["publication_value_comparison"]
    publication_key: str
    field_name: str
    operator: ComparisonOperator
    threshold: float | int | str
    unit: str | None = None

    model_config = {"extra": "forbid"}


class PublicationFreshnessComparisonRule(BaseModel):
    rule_kind: Literal["publication_freshness_comparison"]
    publication_key: str
    operator: ComparisonOperator
    threshold_hours: float

    model_config = {"extra": "forbid"}


class HaHelperStateComparisonRule(BaseModel):
    rule_kind: Literal["ha_helper_state_comparison"]
    entity_id: str
    operator: ComparisonOperator
    expected_value: str | float | int | bool

    model_config = {"extra": "forbid"}


RuleDocument = Annotated[
    Union[
        PublicationValueComparisonRule,
        PublicationFreshnessComparisonRule,
        HaHelperStateComparisonRule,
    ],
    Field(discriminator="rule_kind"),
]


def parse_rule_document(data: dict) -> PublicationValueComparisonRule | PublicationFreshnessComparisonRule | HaHelperStateComparisonRule:
    """Parse and validate a rule document dict.

    Raises ``ValueError`` for unknown rule_kind or invalid structure.
    Raises ``pydantic.ValidationError`` for schema violations.

    Retired fields and operators are reported by name so an operator holding
    an older rule document is told what changed, rather than getting a bare
    "extra inputs are not permitted".
    """
    for field_name, message in _RETIRED_RULE_FIELDS.items():
        if field_name in data:
            raise ValueError(message)
    operator = data.get("operator")
    if isinstance(operator, str) and operator in _RETIRED_OPERATORS:
        raise ValueError(_RETIRED_OPERATORS[operator])

    rule_kind = data.get("rule_kind")
    if rule_kind == "publication_value_comparison":
        return PublicationValueComparisonRule.model_validate(data)
    if rule_kind == "publication_freshness_comparison":
        return PublicationFreshnessComparisonRule.model_validate(data)
    if rule_kind == "ha_helper_state_comparison":
        return HaHelperStateComparisonRule.model_validate(data)
    raise ValueError(
        f"Unknown rule_kind {rule_kind!r}. "
        f"Must be one of: {', '.join(sorted(ALLOWED_RULE_KINDS))}"
    )
