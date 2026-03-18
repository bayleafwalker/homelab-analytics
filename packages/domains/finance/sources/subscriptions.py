"""Subscriptions source definition for the finance capability pack."""
from __future__ import annotations

from packages.platform.capability_types import SourceDefinition

SUBSCRIPTIONS_SOURCE = SourceDefinition(
    dataset_name="subscriptions",
    display_name="Subscriptions",
    description="Recurring subscription records (SaaS services, memberships, utilities).",
    retry_kind="subscriptions",
)
