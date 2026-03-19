"""Overview domain capability pack manifest — cross-domain composition publications.

The overview pack owns no sources or workflows of its own. It composes outputs
from the finance and utilities packs into a household operating picture.
"""
from __future__ import annotations

from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    UiDescriptor,
)

OVERVIEW_PACK = CapabilityPack(
    name="overview",
    version="1.0.0",
    sources=(),
    workflows=(),
    publications=(
        PublicationDefinition(
            key="household_overview",
            schema_name="household_overview",
            display_name="Household Overview",
            description="Top-line summary of current cashflow, utility spend, subscriptions, and account balance direction.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="open_attention_items",
            schema_name="open_attention_items",
            display_name="Open Attention Items",
            description="Aggregated attention items across domains — anomalies, contract reviews, upcoming renewals, and imminent payments.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="recent_significant_changes",
            schema_name="recent_significant_changes",
            display_name="Recent Significant Changes",
            description="Biggest month-over-month changes in cashflow, category spend, and utility costs.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="current_operating_baseline",
            schema_name="current_operating_baseline",
            display_name="Current Operating Baseline",
            description="Household financial baseline — average monthly spend, recurring costs, utility baseline, and current account balance.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
    ),
    ui_descriptors=(
        UiDescriptor(
            key="overview",
            nav_label="Overview",
            nav_path="/",
            kind="dashboard",
            publication_keys=(
                "household_overview",
                "open_attention_items",
                "recent_significant_changes",
                "current_operating_baseline",
            ),
            icon="home",
        ),
    ),
)
