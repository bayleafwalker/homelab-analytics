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
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"


class VerdictMapping(BaseModel):
    ok: str | None = None
    warning: str | None = None
    breach: str | None = None
    unavailable: str | None = None

    model_config = {"extra": "forbid"}


class PublicationValueComparisonRule(BaseModel):
    rule_kind: Literal["publication_value_comparison"]
    publication_key: str
    field_name: str
    operator: ComparisonOperator
    threshold: float | int | str
    unit: str | None = None
    verdict_mapping: VerdictMapping = Field(default_factory=VerdictMapping)

    model_config = {"extra": "forbid"}


class PublicationFreshnessComparisonRule(BaseModel):
    rule_kind: Literal["publication_freshness_comparison"]
    publication_key: str
    operator: ComparisonOperator
    threshold_hours: float
    allowed_freshness_states: list[str] | None = None
    verdict_mapping: VerdictMapping = Field(default_factory=VerdictMapping)

    model_config = {"extra": "forbid"}


class HaHelperStateComparisonRule(BaseModel):
    rule_kind: Literal["ha_helper_state_comparison"]
    entity_id: str
    operator: ComparisonOperator
    expected_value: str | float | int | bool
    verdict_mapping: VerdictMapping = Field(default_factory=VerdictMapping)

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
    """
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
