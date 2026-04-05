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
    dimension_field,
    identifier_field,
    measure_field,
    status_field,
    time_field,
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
            schema_version="1.0.0",
            display_name="Current Electricity Prices",
            description="Latest electricity tariff rates derived from contract price data.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "contract_id": identifier_field(
                    "Stable contract identifier for the active tariff row."
                ),
                "contract_name": dimension_field(
                    "Human-readable contract or tariff name."
                ),
                "provider": dimension_field(
                    "Supplier or provider offering the tariff."
                ),
                "contract_type": dimension_field(
                    "Contract family such as spot, fixed, or subscription."
                ),
                "price_component": dimension_field(
                    "Tariff component represented by the row, such as energy or standing charge."
                ),
                "billing_cycle": dimension_field(
                    "Billing cadence attached to the tariff component."
                ),
                "unit_price": measure_field(
                    "Current tariff price for the stated quantity unit.",
                    aggregation="latest",
                    unit="currency_per_unit",
                ),
                "currency": dimension_field(
                    "ISO currency code for the tariff price."
                ),
                "quantity_unit": dimension_field(
                    "Usage unit associated with the tariff price, such as kWh."
                ),
                "valid_from": time_field(
                    "Date when the tariff row became effective.",
                    grain="day",
                ),
                "valid_to": time_field(
                    "Date when the tariff row expires, if known.",
                    grain="day",
                ),
                "status": status_field(
                    "Lifecycle status for the tariff row."
                ),
            },
        ),
        PublicationDefinition(
            key="utility_cost_summary",
            schema_name="utility_cost_summary",
            schema_version="1.0.0",
            display_name="Utility Cost Summary",
            description="Monthly utility cost breakdown combining contract prices and usage.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "period_start": time_field(
                    "Inclusive start date for the summarized utility period.",
                    grain="day",
                ),
                "period_end": time_field(
                    "Inclusive end date for the summarized utility period.",
                    grain="day",
                ),
                "period_day": time_field(
                    "Daily bucket label when the summary is materialized at day grain.",
                    grain="day",
                ),
                "period_month": time_field(
                    "Monthly bucket label when the summary is materialized at month grain.",
                    grain="month",
                ),
                "meter_id": identifier_field(
                    "Stable identifier for the meter or service point."
                ),
                "meter_name": dimension_field(
                    "Human-readable meter or service-point name."
                ),
                "utility_type": dimension_field(
                    "Utility category such as electricity, water, or gas."
                ),
                "usage_quantity": measure_field(
                    "Total consumed quantity for the summarized period.",
                    aggregation="sum",
                    unit="usage_unit",
                ),
                "usage_unit": dimension_field(
                    "Normalized measurement unit for the usage quantity."
                ),
                "billed_amount": measure_field(
                    "Total billed cost for the summarized period.",
                    aggregation="sum",
                    unit="currency",
                ),
                "currency": dimension_field(
                    "ISO currency code for the billed amount."
                ),
                "unit_cost": measure_field(
                    "Effective cost per usage unit for the summarized period.",
                    aggregation="avg",
                    unit="currency_per_unit",
                ),
                "bill_count": measure_field(
                    "Number of bill rows contributing to the period summary.",
                    aggregation="count",
                    unit="count",
                ),
                "usage_record_count": measure_field(
                    "Number of usage readings contributing to the period summary.",
                    aggregation="count",
                    unit="count",
                ),
                "coverage_status": status_field(
                    "Coverage quality describing whether both billing and usage data are present."
                ),
            },
        ),
        PublicationDefinition(
            key="contract_price_current",
            schema_name="contract_price_current",
            schema_version="1.0.0",
            display_name="Current Contract Prices",
            description="Latest contracted unit prices for utilities and services.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "contract_id": identifier_field(
                    "Stable contract identifier for the active price row."
                ),
                "contract_name": dimension_field(
                    "Human-readable contract name."
                ),
                "provider": dimension_field(
                    "Supplier or provider attached to the contract."
                ),
                "contract_type": dimension_field(
                    "Contract family or product type."
                ),
                "price_component": dimension_field(
                    "Price component represented by the row."
                ),
                "billing_cycle": dimension_field(
                    "Billing cadence attached to the price component."
                ),
                "unit_price": measure_field(
                    "Current contracted unit price for the price component.",
                    aggregation="latest",
                    unit="currency_per_unit",
                ),
                "currency": dimension_field(
                    "ISO currency code for the unit price."
                ),
                "quantity_unit": dimension_field(
                    "Quantity unit associated with the contracted unit price."
                ),
                "valid_from": time_field(
                    "Date when the price row became effective.",
                    grain="day",
                ),
                "valid_to": time_field(
                    "Date when the price row expires, if known.",
                    grain="day",
                ),
                "status": status_field(
                    "Lifecycle status for the contract price row."
                ),
            },
        ),
        PublicationDefinition(
            key="utility_cost_trend_monthly",
            schema_name="utility_cost_trend_monthly",
            schema_version="1.0.0",
            display_name="Utility Cost Trend (Monthly)",
            description="Monthly aggregated utility costs and usage per utility type.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
            field_semantics={
                "billing_month": time_field(
                    "Calendar month bucket for the utility trend row.",
                    grain="month",
                ),
                "utility_type": dimension_field(
                    "Utility category tracked by the monthly trend."
                ),
                "total_cost": measure_field(
                    "Total utility cost for the month and utility type.",
                    aggregation="sum",
                    unit="currency",
                ),
                "usage_amount": measure_field(
                    "Total metered usage for the month and utility type.",
                    aggregation="sum",
                    unit="usage_unit",
                ),
                "unit_price_effective": measure_field(
                    "Effective blended price per usage unit for the month.",
                    aggregation="avg",
                    unit="currency_per_unit",
                ),
                "currency": dimension_field(
                    "ISO currency code for the monthly cost values."
                ),
                "meter_count": measure_field(
                    "Number of meters represented in the monthly aggregate.",
                    aggregation="count",
                    unit="count",
                ),
            },
        ),
        PublicationDefinition(
            key="usage_vs_price_summary",
            schema_name="usage_vs_price_summary",
            schema_version="1.0.0",
            display_name="Usage vs Price Summary",
            description="Month-over-month comparison of usage and price changes — answers whether cost increases are driven by price or consumption.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
            field_semantics={
                "utility_type": dimension_field(
                    "Utility category being compared month over month."
                ),
                "period": time_field(
                    "Comparison period label for the month-over-month summary.",
                    grain="month",
                ),
                "usage_change_pct": measure_field(
                    "Percent change in usage versus the previous comparison period.",
                    aggregation="pct_change",
                    unit="percent",
                ),
                "price_change_pct": measure_field(
                    "Percent change in effective unit price versus the previous period.",
                    aggregation="pct_change",
                    unit="percent",
                ),
                "cost_change_pct": measure_field(
                    "Percent change in total cost versus the previous period.",
                    aggregation="pct_change",
                    unit="percent",
                ),
                "dominant_driver": status_field(
                    "Primary factor driving the cost change, such as price or usage."
                ),
            },
        ),
        PublicationDefinition(
            key="contract_review_candidates",
            schema_name="contract_review_candidates",
            schema_version="1.0.0",
            display_name="Contract Review Candidates",
            description="Utility contracts flagged for review based on price, tenure, or market comparison signals.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "contract_id": identifier_field(
                    "Stable contract identifier for the review candidate."
                ),
                "provider": dimension_field(
                    "Supplier or provider attached to the contract."
                ),
                "utility_type": dimension_field(
                    "Utility category for the contract under review."
                ),
                "reason": status_field(
                    "Primary reason the contract was flagged for review."
                ),
                "score": measure_field(
                    "Composite review score used to rank review urgency.",
                    aggregation="none",
                    unit="score",
                ),
                "current_price": measure_field(
                    "Current contracted unit price used in the review comparison.",
                    aggregation="latest",
                    unit="currency_per_unit",
                ),
                "market_reference": measure_field(
                    "Benchmark market unit price used for comparison.",
                    aggregation="benchmark",
                    unit="currency_per_unit",
                ),
                "currency": dimension_field(
                    "ISO currency code for the price comparison."
                ),
            },
        ),
        PublicationDefinition(
            key="contract_renewal_watchlist",
            schema_name="contract_renewal_watchlist",
            schema_version="1.0.0",
            display_name="Contract Renewal Watchlist",
            description="Active utility contracts with renewal or expiry dates within the next 90 days.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "contract_id": identifier_field(
                    "Stable contract identifier for the renewal watchlist row."
                ),
                "contract_name": dimension_field(
                    "Human-readable contract name."
                ),
                "provider": dimension_field(
                    "Supplier or provider attached to the contract."
                ),
                "utility_type": dimension_field(
                    "Utility category for the watchlisted contract."
                ),
                "renewal_date": time_field(
                    "Next renewal or expiry date for the contract.",
                    grain="day",
                ),
                "days_until_renewal": measure_field(
                    "Number of days remaining until the renewal or expiry event.",
                    aggregation="latest",
                    unit="days",
                ),
                "current_price": measure_field(
                    "Current contracted unit price as of the watchlist snapshot.",
                    aggregation="latest",
                    unit="currency_per_unit",
                ),
                "currency": dimension_field(
                    "ISO currency code for the current price."
                ),
                "contract_duration_days": measure_field(
                    "Full contract duration expressed in days.",
                    aggregation="latest",
                    unit="days",
                ),
            },
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
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "discovery",
                "web_anchor": "utility-costs",
                "web_nav_group": "Utilities",
            },
        ),
        UiDescriptor(
            key="contract-prices",
            nav_label="Contract Prices",
            nav_path="/reports/contract-prices",
            kind="table",
            publication_keys=("contract_price_current",),
            icon="file-text",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "discovery",
                "web_anchor": "contract-prices",
                "web_nav_group": "Utilities",
            },
        ),
        UiDescriptor(
            key="utility-cost-trend",
            nav_label="Cost Trend",
            nav_path="/reports/utility-cost-trend",
            kind="dashboard",
            publication_keys=("utility_cost_trend_monthly",),
            icon="trending-up",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "detail",
                "web_anchor": "utility-cost-trend",
                "web_nav_group": "Utilities",
            },
        ),
        UiDescriptor(
            key="usage-vs-price",
            nav_label="Usage vs Price",
            nav_path="/reports/usage-vs-price",
            kind="report",
            publication_keys=("usage_vs_price_summary",),
            icon="bar-chart",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "discovery",
                "web_anchor": "usage-vs-price",
                "web_nav_group": "Utilities",
            },
        ),
        UiDescriptor(
            key="contract-review",
            nav_label="Contract Review",
            nav_path="/reports/contract-review",
            kind="table",
            publication_keys=("contract_review_candidates",),
            icon="alert-circle",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "discovery",
                "web_anchor": "contract-review",
                "web_nav_group": "Utilities",
            },
        ),
        UiDescriptor(
            key="contract-renewals",
            nav_label="Renewals",
            nav_path="/reports/contract-renewals",
            kind="table",
            publication_keys=("contract_renewal_watchlist",),
            icon="calendar",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "discovery",
                "web_anchor": "contract-renewals",
                "web_nav_group": "Utilities",
            },
        ),
    ),
)
