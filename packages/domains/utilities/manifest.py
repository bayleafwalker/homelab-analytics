"""Utilities domain capability pack manifest — declares publications and UI descriptors.

Sources and workflows are intentionally empty: utility publication data
(electricity prices, utility cost summaries) is produced by the finance domain's
ingest-contract-prices workflow, which owns the contract_prices source. The utilities
pack declares ownership of the resulting publications and their UI surfaces.
"""
from __future__ import annotations

from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    UiDescriptor,
)

UTILITIES_PACK = CapabilityPack(
    name="utilities",
    version="1.0.0",
    sources=(),
    workflows=(),
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
