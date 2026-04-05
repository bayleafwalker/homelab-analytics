"""Overview domain capability pack manifest — cross-domain composition publications.

The overview pack owns no sources or workflows of its own. It composes outputs
from the finance and utilities packs into a household operating picture.
"""
from __future__ import annotations

from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    UiDescriptor,
    dimension_field,
    identifier_field,
    measure_field,
    status_field,
    time_field,
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
            schema_version="1.0.0",
            display_name="Household Overview",
            description="Top-line summary of current cashflow, utility spend, subscriptions, and account balance direction.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "current_month": time_field(
                    "Calendar month represented by the overview snapshot.",
                    grain="month",
                ),
                "cashflow_income": measure_field(
                    "Current-month income total included in the overview.",
                    aggregation="sum",
                    unit="currency",
                ),
                "cashflow_expense": measure_field(
                    "Current-month expense total included in the overview.",
                    aggregation="sum",
                    unit="currency",
                ),
                "cashflow_net": measure_field(
                    "Current-month net cashflow included in the overview.",
                    aggregation="sum",
                    unit="currency",
                ),
                "utility_cost_total": measure_field(
                    "Current-month utility spend included in the overview.",
                    aggregation="sum",
                    unit="currency",
                ),
                "subscription_total_monthly": measure_field(
                    "Monthly-normalized recurring subscription spend included in the overview.",
                    aggregation="sum",
                    unit="currency",
                ),
                "account_balance_direction": status_field(
                    "Direction of the current account-balance trend."
                ),
                "balance_net_change": measure_field(
                    "Net account balance change for the overview month.",
                    aggregation="sum",
                    unit="currency",
                ),
                "currency": dimension_field(
                    "ISO currency code for the monetary overview measures."
                ),
            },
        ),
        PublicationDefinition(
            key="open_attention_items",
            schema_name="open_attention_items",
            schema_version="1.0.0",
            display_name="Open Attention Items",
            description="Aggregated attention items across domains — anomalies, contract reviews, upcoming renewals, and imminent payments.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "item_id": identifier_field(
                    "Stable synthetic identifier for the attention item."
                ),
                "item_type": dimension_field(
                    "Attention-item category such as anomaly or renewal."
                ),
                "title": dimension_field(
                    "Short human-readable title for the attention item."
                ),
                "detail": dimension_field(
                    "Longer explanation of why the item needs attention.",
                    filterable=False,
                ),
                "severity": status_field(
                    "Priority level for the attention item."
                ),
                "source_domain": dimension_field(
                    "Domain that produced the attention item."
                ),
            },
        ),
        PublicationDefinition(
            key="recent_significant_changes",
            schema_name="recent_significant_changes",
            schema_version="1.0.0",
            display_name="Recent Significant Changes",
            description="Biggest month-over-month changes in cashflow, category spend, and utility costs.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "change_type": dimension_field(
                    "Type of change being highlighted, such as cashflow or utility cost."
                ),
                "period": time_field(
                    "Period label for the highlighted month-over-month comparison.",
                    grain="month",
                ),
                "description": dimension_field(
                    "Human-readable description of the highlighted change.",
                    filterable=False,
                ),
                "current_value": measure_field(
                    "Value observed in the current comparison period.",
                    aggregation="latest",
                    unit="currency",
                ),
                "previous_value": measure_field(
                    "Value observed in the immediately preceding comparison period.",
                    aggregation="latest",
                    unit="currency",
                ),
                "change_pct": measure_field(
                    "Percent delta between the current and previous values.",
                    aggregation="pct_change",
                    unit="percent",
                ),
                "direction": status_field(
                    "Directional interpretation of the significant change."
                ),
            },
        ),
        PublicationDefinition(
            key="current_operating_baseline",
            schema_name="current_operating_baseline",
            schema_version="1.0.0",
            display_name="Current Operating Baseline",
            description="Household financial baseline — average monthly spend, recurring costs, utility baseline, and current account balance.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "baseline_type": dimension_field(
                    "Baseline category represented by the row."
                ),
                "description": dimension_field(
                    "Human-readable description of the baseline value.",
                    filterable=False,
                ),
                "value": measure_field(
                    "Baseline metric value for the current operating picture.",
                    aggregation="latest",
                    unit="currency",
                ),
                "period_label": time_field(
                    "Reference period label used for the baseline calculation.",
                    grain="month",
                ),
                "currency": dimension_field(
                    "ISO currency code for the baseline value."
                ),
            },
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
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "overview",
                "web_render_mode": "detail",
                "web_anchor": "overview",
                "web_nav_group": "Overview",
            },
        ),
    ),
)
