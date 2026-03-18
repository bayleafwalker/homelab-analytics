"""Finance domain capability pack manifest — declares sources, workflows, and publications."""
from __future__ import annotations

from packages.domains.finance.sources.account_transactions import ACCOUNT_TRANSACTIONS_SOURCE
from packages.domains.finance.sources.contract_prices import CONTRACT_PRICES_SOURCE
from packages.domains.finance.sources.subscriptions import SUBSCRIPTIONS_SOURCE
from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    UiDescriptor,
    WorkflowDefinition,
)

FINANCE_PACK = CapabilityPack(
    name="finance",
    version="1.0.0",
    sources=(
        ACCOUNT_TRANSACTIONS_SOURCE,
        SUBSCRIPTIONS_SOURCE,
        CONTRACT_PRICES_SOURCE,
    ),
    workflows=(
        WorkflowDefinition(
            workflow_id="ingest-account-transactions",
            display_name="Ingest Account Transactions",
            source_dataset_name="account_transactions",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="ingest-account-transactions",
            publication_keys=("monthly_cashflow",),
        ),
        WorkflowDefinition(
            workflow_id="ingest-subscriptions",
            display_name="Ingest Subscriptions",
            source_dataset_name="subscriptions",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="ingest-subscriptions",
            publication_keys=("subscription_summary",),
        ),
        WorkflowDefinition(
            workflow_id="ingest-contract-prices",
            display_name="Ingest Contract Prices",
            source_dataset_name="contract_prices",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="ingest-contract-prices",
            publication_keys=("contract_price_current",),
        ),
        WorkflowDefinition(
            workflow_id="ingest-configured-csv",
            display_name="Ingest Configured CSV",
            source_dataset_name="configured_csv",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="ingest-configured-csv",
            publication_keys=(),
        ),
    ),
    publications=(
        PublicationDefinition(
            key="monthly_cashflow",
            schema_name="monthly_cashflow",
            display_name="Monthly Cashflow",
            description="Aggregated monthly income and expense summary from account transactions.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
        ),
        PublicationDefinition(
            key="subscription_summary",
            schema_name="subscription_summary",
            display_name="Subscription Summary",
            description="Active recurring subscription costs grouped by category.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
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
    ),
    ui_descriptors=(
        UiDescriptor(
            key="cashflow",
            nav_label="Cashflow",
            nav_path="/reports/cashflow",
            kind="dashboard",
            publication_keys=("monthly_cashflow",),
            icon="chart-bar",
        ),
        UiDescriptor(
            key="subscriptions",
            nav_label="Subscriptions",
            nav_path="/reports/subscriptions",
            kind="report",
            publication_keys=("subscription_summary",),
            icon="repeat",
        ),
        UiDescriptor(
            key="contract-prices",
            nav_label="Contract Prices",
            nav_path="/reports/contract-prices",
            kind="table",
            publication_keys=("contract_price_current",),
            icon="file-text",
        ),
    ),
)
