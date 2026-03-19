"""Utilities domain capability pack manifest — sources, workflows, publications, and UI.

The utilities pack owns the utility_rates and contract_prices sources and publishes
electricity_price_current, utility_cost_summary, and contract_price_current.
"""
from __future__ import annotations

from packages.domains.utilities.sources.contract_prices import CONTRACT_PRICES_SOURCE
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
    sources=(UTILITY_RATES_SOURCE, CONTRACT_PRICES_SOURCE),
    workflows=(
        WorkflowDefinition(
            workflow_id="derive-utility-publications",
            display_name="Derive Utility Publications",
            source_dataset_name="utility_rates",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="derive-utility-publications",
            publication_keys=(
                "electricity_price_current",
                "utility_cost_summary",
                "utility_cost_trend_monthly",
                "usage_vs_price_summary",
            ),
        ),
        WorkflowDefinition(
            workflow_id="ingest-contract-prices",
            display_name="Ingest Contract Prices",
            source_dataset_name="contract_prices",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="ingest-contract-prices",
            publication_keys=(
                "contract_price_current",
                "contract_review_candidates",
                "contract_renewal_watchlist",
            ),
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
        PublicationDefinition(
            key="contract_price_current",
            schema_name="contract_price_current",
            display_name="Current Contract Prices",
            description="Latest contracted unit prices for utilities and services.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="utility_cost_trend_monthly",
            schema_name="utility_cost_trend_monthly",
            display_name="Utility Cost Trend (Monthly)",
            description="Monthly aggregated utility costs and usage per utility type.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
        ),
        PublicationDefinition(
            key="usage_vs_price_summary",
            schema_name="usage_vs_price_summary",
            display_name="Usage vs Price Summary",
            description="Month-over-month comparison of usage and price changes — answers whether cost increases are driven by price or consumption.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
        ),
        PublicationDefinition(
            key="contract_review_candidates",
            schema_name="contract_review_candidates",
            display_name="Contract Review Candidates",
            description="Utility contracts flagged for review based on price, tenure, or market comparison signals.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="contract_renewal_watchlist",
            schema_name="contract_renewal_watchlist",
            display_name="Contract Renewal Watchlist",
            description="Active utility contracts with renewal or expiry dates within the next 90 days.",
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
        UiDescriptor(
            key="contract-prices",
            nav_label="Contract Prices",
            nav_path="/reports/contract-prices",
            kind="table",
            publication_keys=("contract_price_current",),
            icon="file-text",
        ),
        UiDescriptor(
            key="utility-cost-trend",
            nav_label="Cost Trend",
            nav_path="/reports/utility-cost-trend",
            kind="dashboard",
            publication_keys=("utility_cost_trend_monthly",),
            icon="trending-up",
        ),
        UiDescriptor(
            key="usage-vs-price",
            nav_label="Usage vs Price",
            nav_path="/reports/usage-vs-price",
            kind="report",
            publication_keys=("usage_vs_price_summary",),
            icon="bar-chart",
        ),
        UiDescriptor(
            key="contract-review",
            nav_label="Contract Review",
            nav_path="/reports/contract-review",
            kind="table",
            publication_keys=("contract_review_candidates",),
            icon="alert-circle",
        ),
        UiDescriptor(
            key="contract-renewals",
            nav_label="Renewals",
            nav_path="/reports/contract-renewals",
            kind="table",
            publication_keys=("contract_renewal_watchlist",),
            icon="calendar",
        ),
    ),
)
