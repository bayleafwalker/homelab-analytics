"""Finance domain capability pack manifest — declares sources, workflows, and publications."""
from __future__ import annotations

from packages.domains.finance.sources.account_transactions import ACCOUNT_TRANSACTIONS_SOURCE
from packages.domains.finance.sources.subscriptions import SUBSCRIPTIONS_SOURCE
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

FINANCE_PACK = CapabilityPack(
    name="finance",
    version="1.0.0",
    sources=(
        ACCOUNT_TRANSACTIONS_SOURCE,
        SUBSCRIPTIONS_SOURCE,
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
            publication_keys=(
                "monthly_cashflow",
                "spend_by_category_monthly",
                "recent_large_transactions",
                "account_balance_trend",
                "transaction_anomalies_current",
            ),
            identity_strategy_id="bank_transaction_v1",
        ),
        WorkflowDefinition(
            workflow_id="ingest-subscriptions",
            display_name="Ingest Subscriptions",
            source_dataset_name="subscriptions",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="ingest-subscriptions",
            publication_keys=("subscription_summary", "upcoming_fixed_costs_30d"),
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
            schema_version="1.0.0",
            display_name="Monthly Cashflow",
            description="Aggregated monthly income and expense summary from account transactions.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
            field_semantics={
                "booking_month": time_field(
                    "Calendar month bucket for the aggregated cashflow row.",
                    grain="month",
                ),
                "income": measure_field(
                    "Total credited amount posted during the month.",
                    aggregation="sum",
                    unit="currency",
                ),
                "expense": measure_field(
                    "Total debited amount posted during the month.",
                    aggregation="sum",
                    unit="currency",
                ),
                "net": measure_field(
                    "Net cash movement for the month after income and expense are combined.",
                    aggregation="sum",
                    unit="currency",
                ),
                "transaction_count": measure_field(
                    "Number of transactions included in the monthly aggregate.",
                    aggregation="count",
                    unit="count",
                ),
            },
        ),
        PublicationDefinition(
            key="subscription_summary",
            schema_name="subscription_summary",
            schema_version="1.0.0",
            display_name="Subscription Summary",
            description="Active recurring subscription costs grouped by category.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
            field_semantics={
                "contract_id": identifier_field(
                    "Stable contract identifier for the recurring charge."
                ),
                "contract_name": dimension_field(
                    "Human-readable subscription or contract name."
                ),
                "provider": dimension_field(
                    "Provider or merchant responsible for the recurring charge."
                ),
                "billing_cycle": dimension_field(
                    "Declared billing cadence for the subscription."
                ),
                "amount": measure_field(
                    "Charge amount in the provider billing cadence.",
                    aggregation="latest",
                    unit="currency",
                ),
                "currency": dimension_field(
                    "ISO currency code for the subscription charge."
                ),
                "start_date": time_field(
                    "Date when the subscription became active.",
                    grain="day",
                ),
                "end_date": time_field(
                    "Date when the subscription ended, if known.",
                    grain="day",
                ),
                "monthly_equivalent": measure_field(
                    "Charge normalized to a monthly amount for comparison across billing cycles.",
                    aggregation="normalized_monthly",
                    unit="currency",
                ),
                "status": status_field(
                    "Current subscription status such as active or inactive."
                ),
            },
        ),
        PublicationDefinition(
            key="spend_by_category_monthly",
            schema_name="spend_by_category_monthly",
            schema_version="1.0.0",
            display_name="Spend by Category Monthly",
            description="Monthly expense totals grouped by counterparty and category.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
            field_semantics={
                "booking_month": time_field(
                    "Calendar month bucket for the spend aggregate.",
                    grain="month",
                ),
                "counterparty_name": dimension_field(
                    "Canonical merchant or counterparty name."
                ),
                "category": dimension_field(
                    "Resolved spending category for the grouped transactions."
                ),
                "total_expense": measure_field(
                    "Total expense amount for the month, counterparty, and category.",
                    aggregation="sum",
                    unit="currency",
                ),
                "transaction_count": measure_field(
                    "Number of transactions contributing to the grouped expense total.",
                    aggregation="count",
                    unit="count",
                ),
            },
        ),
        PublicationDefinition(
            key="recent_large_transactions",
            schema_name="recent_large_transactions",
            schema_version="1.0.0",
            display_name="Recent Large Transactions",
            description="Notable transactions above a threshold in recent months.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "transaction_id": identifier_field(
                    "Stable transaction identifier from the canonical transaction fact."
                ),
                "booked_at": time_field(
                    "Timestamp when the transaction was booked by the source account.",
                    grain="timestamp",
                ),
                "booking_month": time_field(
                    "Calendar month bucket derived from the booking timestamp.",
                    grain="month",
                ),
                "account_id": identifier_field(
                    "Stable account identifier associated with the transaction."
                ),
                "counterparty_name": dimension_field(
                    "Canonical counterparty name for the transaction."
                ),
                "amount": measure_field(
                    "Signed transaction amount for the flagged large transaction.",
                    aggregation="none",
                    unit="currency",
                ),
                "currency": dimension_field(
                    "ISO currency code for the transaction amount."
                ),
                "description": dimension_field(
                    "Source description or memo attached to the transaction.",
                    filterable=False,
                ),
                "direction": status_field(
                    "Transaction direction such as inflow or outflow."
                ),
            },
        ),
        PublicationDefinition(
            key="account_balance_trend",
            schema_name="account_balance_trend",
            schema_version="1.0.0",
            display_name="Account Balance Trend",
            description="Cumulative balance trend per account derived from transaction history.",
            visibility="public",
            lineage_required=True,
            retention_policy="indefinite",
            field_semantics={
                "booking_month": time_field(
                    "Calendar month bucket for the account balance snapshot.",
                    grain="month",
                ),
                "account_id": identifier_field(
                    "Stable account identifier for the balance series."
                ),
                "net_change": measure_field(
                    "Net account movement during the month.",
                    aggregation="sum",
                    unit="currency",
                ),
                "cumulative_balance": measure_field(
                    "Running account balance after applying all monthly movements.",
                    aggregation="latest",
                    unit="currency",
                ),
                "transaction_count": measure_field(
                    "Number of transactions contributing to the monthly account movement.",
                    aggregation="count",
                    unit="count",
                ),
            },
        ),
        PublicationDefinition(
            key="transaction_anomalies_current",
            schema_name="transaction_anomalies_current",
            schema_version="1.0.0",
            display_name="Transaction Anomalies",
            description="Recent transactions flagged as anomalous — first-time counterparties or unusual amounts.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "transaction_id": identifier_field(
                    "Stable transaction identifier for the anomalous event."
                ),
                "booking_date": time_field(
                    "Booking date for the anomalous transaction.",
                    grain="day",
                ),
                "counterparty_name": dimension_field(
                    "Canonical counterparty name for the anomalous transaction."
                ),
                "amount": measure_field(
                    "Signed amount of the anomalous transaction.",
                    aggregation="none",
                    unit="currency",
                ),
                "direction": status_field(
                    "Transaction direction for the anomalous event."
                ),
                "anomaly_type": status_field(
                    "Classification describing why the transaction was flagged."
                ),
                "anomaly_reason": dimension_field(
                    "Human-readable explanation for the anomaly classification.",
                    filterable=False,
                ),
            },
        ),
        PublicationDefinition(
            key="upcoming_fixed_costs_30d",
            schema_name="upcoming_fixed_costs_30d",
            schema_version="1.0.0",
            display_name="Upcoming Fixed Costs (30 days)",
            description="Active recurring subscriptions projected as upcoming charges in the next 30 days.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            field_semantics={
                "contract_name": dimension_field(
                    "Human-readable contract or subscription name."
                ),
                "provider": dimension_field(
                    "Provider expected to bill the upcoming fixed cost."
                ),
                "frequency": dimension_field(
                    "Expected billing cadence used for the forecast."
                ),
                "expected_amount": measure_field(
                    "Projected charge amount for the upcoming billing event.",
                    aggregation="none",
                    unit="currency",
                ),
                "currency": dimension_field(
                    "ISO currency code for the projected charge."
                ),
                "expected_date": time_field(
                    "Date when the next recurring charge is expected.",
                    grain="day",
                ),
                "confidence": status_field(
                    "Confidence band for the projected billing event."
                ),
            },
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
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "detail",
                "web_anchor": "cashflow",
            },
        ),
        UiDescriptor(
            key="subscriptions",
            nav_label="Subscriptions",
            nav_path="/reports/subscriptions",
            kind="report",
            publication_keys=("subscription_summary",),
            icon="repeat",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "detail",
                "web_anchor": "subscriptions",
            },
        ),
        UiDescriptor(
            key="spending-by-category",
            nav_label="Spending by Category",
            nav_path="/reports/spending-by-category",
            kind="report",
            publication_keys=("spend_by_category_monthly",),
            icon="pie-chart",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "detail",
                "web_anchor": "spending-by-category",
            },
        ),
        UiDescriptor(
            key="large-transactions",
            nav_label="Large Transactions",
            nav_path="/reports/large-transactions",
            kind="table",
            publication_keys=("recent_large_transactions",),
            icon="alert-circle",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "discovery",
                "web_anchor": "large-transactions",
            },
        ),
        UiDescriptor(
            key="balance-trend",
            nav_label="Balance Trend",
            nav_path="/reports/balance-trend",
            kind="dashboard",
            publication_keys=("account_balance_trend",),
            icon="trending-up",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "detail",
                "web_anchor": "balance-trend",
            },
        ),
        UiDescriptor(
            key="anomalies",
            nav_label="Anomalies",
            nav_path="/reports/anomalies",
            kind="table",
            publication_keys=("transaction_anomalies_current",),
            icon="alert-triangle",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "discovery",
                "web_anchor": "anomalies",
            },
        ),
        UiDescriptor(
            key="upcoming-costs",
            nav_label="Upcoming Costs",
            nav_path="/reports/upcoming-costs",
            kind="table",
            publication_keys=("upcoming_fixed_costs_30d",),
            icon="calendar",
            supported_renderers=("web",),
            renderer_hints={
                "web_surface": "reports",
                "web_render_mode": "discovery",
                "web_anchor": "upcoming-costs",
            },
        ),
    ),
)
