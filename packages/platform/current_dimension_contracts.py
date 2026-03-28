from __future__ import annotations

from dataclasses import dataclass, field

from packages.platform.capability_types import (
    PublicationFieldDefinition,
    dimension_field,
    identifier_field,
    measure_field,
    status_field,
)


@dataclass(frozen=True)
class CurrentDimensionContractDefinition:
    schema_name: str
    schema_version: str
    display_name: str
    description: str
    visibility: str = "public"
    lineage_required: bool = True
    retention_policy: str = "indefinite"
    field_overrides: dict[str, PublicationFieldDefinition] = field(default_factory=dict)


CURRENT_DIMENSION_CONTRACTS: dict[str, CurrentDimensionContractDefinition] = {
    "dim_account": CurrentDimensionContractDefinition(
        schema_name="dim_account",
        schema_version="1.0.0",
        display_name="Current Accounts",
        description="Current snapshot of canonical household account records.",
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current account row."),
            "account_id": identifier_field("Stable account identifier across promoted runs."),
            "currency": dimension_field("ISO currency code associated with the account."),
        },
    ),
    "dim_counterparty": CurrentDimensionContractDefinition(
        schema_name="dim_counterparty",
        schema_version="1.0.0",
        display_name="Current Counterparties",
        description=(
            "Current snapshot of canonical counterparties shared by transaction-facing "
            "finance reporting."
        ),
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current counterparty row."),
            "counterparty_name": dimension_field(
                "Canonical merchant or counterparty name used across finance facts."
            ),
            "category": dimension_field(
                "Current category slug assigned to the counterparty; this remains a "
                "free-text bridge until category_id governance lands in finance."
            ),
        },
    ),
    "dim_contract": CurrentDimensionContractDefinition(
        schema_name="dim_contract",
        schema_version="1.0.0",
        display_name="Current Contracts",
        description=(
            "Current snapshot of shared contract definitions used by subscriptions and "
            "utility-pricing workflows."
        ),
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current contract row."),
            "contract_id": identifier_field("Stable contract identifier across domains."),
            "contract_name": dimension_field("Human-readable contract or subscription name."),
            "provider": dimension_field(
                "Provider name captured on the shared contract dimension."
            ),
        },
    ),
    "dim_category": CurrentDimensionContractDefinition(
        schema_name="dim_category",
        schema_version="1.0.0",
        display_name="Current Categories",
        description="Current snapshot of the shared cross-domain category registry.",
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current category row."),
            "category_id": identifier_field("Stable category slug used across domains."),
            "display_name": dimension_field("Human-readable category label."),
            "parent_id": identifier_field(
                "Optional parent category identifier for the category hierarchy."
            ),
            "domain": dimension_field("Owning domain for the category or 'shared'."),
            "is_budget_eligible": status_field(
                "Whether the category can be targeted by budget definitions."
            ),
            "is_system": status_field(
                "Whether the category is seeded by the platform rather than operator-defined."
            ),
        },
    ),
    "dim_meter": CurrentDimensionContractDefinition(
        schema_name="dim_meter",
        schema_version="1.0.0",
        display_name="Current Meters",
        description="Current snapshot of canonical utility meters and their source metadata.",
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current meter row."),
            "meter_id": identifier_field("Stable meter identifier across utility runs."),
        },
    ),
    "dim_budget": CurrentDimensionContractDefinition(
        schema_name="dim_budget",
        schema_version="1.0.0",
        display_name="Current Budgets",
        description="Current snapshot of budget definitions keyed to canonical categories.",
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current budget row."),
            "budget_id": identifier_field("Stable budget identifier across promoted runs."),
            "category_id": identifier_field("Canonical category identifier targeted by the budget."),
        },
    ),
    "dim_loan": CurrentDimensionContractDefinition(
        schema_name="dim_loan",
        schema_version="1.0.0",
        display_name="Current Loans",
        description="Current snapshot of canonical household loan definitions and terms.",
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current loan row."),
            "loan_id": identifier_field("Stable loan identifier across repayment runs."),
            "principal": measure_field(
                "Original principal amount captured on the loan dimension.",
                aggregation="latest",
                unit="currency",
            ),
        },
    ),
    "dim_asset": CurrentDimensionContractDefinition(
        schema_name="dim_asset",
        schema_version="1.0.0",
        display_name="Current Assets",
        description="Current snapshot of tracked household and homelab assets.",
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current asset row."),
            "asset_id": identifier_field("Stable asset identifier across inventory updates."),
            "purchase_price": measure_field(
                "Recorded purchase price for the asset.",
                aggregation="latest",
                unit="currency",
            ),
        },
    ),
    "dim_entity": CurrentDimensionContractDefinition(
        schema_name="dim_entity",
        schema_version="1.0.0",
        display_name="Current Home Automation Entities",
        description=(
            "Current snapshot of canonical Home Assistant entities kept separate from "
            "homelab operational models."
        ),
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current entity row."),
            "entity_id": identifier_field("Stable Home Assistant entity identifier."),
            "entity_domain": dimension_field("Entity domain such as sensor or light."),
            "entity_class": dimension_field("Normalized entity class derived from the entity id."),
        },
    ),
}
