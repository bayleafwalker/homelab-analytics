"""Application use-cases for category rule and override management.

Surfaces call these functions; they do not call TransformationService directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from packages.pipelines.transformation_service import TransformationService


def list_rules(svc: "TransformationService") -> list[dict[str, Any]]:
    return svc.list_category_rules()


def add_rule(
    svc: "TransformationService",
    *,
    rule_id: str,
    pattern: str,
    category: str,
    priority: int = 0,
) -> None:
    svc.add_category_rule(
        rule_id=rule_id,
        pattern=pattern,
        category=category,
        priority=priority,
    )


def remove_rule(svc: "TransformationService", *, rule_id: str) -> None:
    svc.remove_category_rule(rule_id=rule_id)


def list_overrides(svc: "TransformationService") -> list[dict[str, Any]]:
    return svc.list_category_overrides()


def set_override(
    svc: "TransformationService",
    *,
    counterparty_name: str,
    category: str,
) -> None:
    svc.set_category_override(counterparty_name=counterparty_name, category=category)


def remove_override(svc: "TransformationService", *, counterparty_name: str) -> None:
    svc.remove_category_override(counterparty_name=counterparty_name)
