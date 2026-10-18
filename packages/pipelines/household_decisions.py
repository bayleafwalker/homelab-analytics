"""Composition-layer registry of declared household decision definitions."""

from __future__ import annotations

from packages.domains.utilities.battery_plan_decision import BATTERY_PLAN_DECISION
from packages.platform.decision_definitions import DecisionDefinition

DECISION_DEFINITIONS: dict[str, DecisionDefinition] = {
    definition.decision_key: definition for definition in (BATTERY_PLAN_DECISION,)
}


def get_decision_definition(decision_key: str) -> DecisionDefinition | None:
    return DECISION_DEFINITIONS.get(decision_key)
