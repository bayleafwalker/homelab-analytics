"""Utilities domain capability pack manifest — sources, workflows, publications, and UI.

The utilities pack owns the utility_rates source and a derive-utility-publications
workflow that produces electricity_price_current and utility_cost_summary.
"""
from __future__ import annotations

from packages.domains.utilities.sources.utility_rates import UTILITY_RATES_SOURCE
from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    UiDescriptor,
    WorkflowDefinition,
)

UTILITIES_PACK = CapabilityPack(
    name="utilities",
    version="1.0.0",
    sources=(UTILITY_RATES_SOURCE,),
    workflows=(
        WorkflowDefinition(
            workflow_id="derive-utility-publications",
            display_name="Derive Utility Publications",
            source_dataset_name="utility_rates",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="derive-utility-publications",
            publication_keys=("electricity_price_current", "utility_cost_summary"),
        ),
    ),
    publications=(
        PublicationDefinition(
            key="electricity_price_current",
            schema_name="electricity_price_current",
            display_name="Current Electricity Prices",
            description="Latest electricity tariff rates derived from contract price data.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="utility_cost_summary",
            schema_name="utility_cost_summary",
            display_name="Utility Cost Summary",
            description="Monthly utility cost breakdown combining contract prices and usage.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
    ),
    ui_descriptors=(
        UiDescriptor(
            key="utility-costs",
            nav_label="Utility Costs",
            nav_path="/reports/utility-costs",
            kind="dashboard",
            publication_keys=("electricity_price_current", "utility_cost_summary"),
            icon="zap",
        ),
    ),
)
