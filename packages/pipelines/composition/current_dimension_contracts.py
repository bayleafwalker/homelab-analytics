from __future__ import annotations

from packages.platform.capability_types import (
    dimension_field,
    identifier_field,
    measure_field,
    status_field,
)
from packages.platform.current_dimension_contracts import (
    CurrentDimensionContractDefinition,
)

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
    "dim_household_member": CurrentDimensionContractDefinition(
        schema_name="dim_household_member",
        schema_version="1.0.0",
        display_name="Current Household Members",
        description=(
            "Current snapshot of canonical household members used for attribution of "
            "transactions, assets, loans, and subscriptions."
        ),
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current household member row."),
            "member_id": identifier_field(
                "Stable household member identifier used for attribution across domains."
            ),
            "display_name": dimension_field(
                "Human-readable member name shown in attribution surfaces."
            ),
            "role": dimension_field(
                "Member role within the household (head, partner, dependent, lodger)."
            ),
            "active": status_field(
                "Whether the member is currently active and eligible for attribution."
            ),
        },
    ),
    "dim_service": CurrentDimensionContractDefinition(
        schema_name="dim_service",
        schema_version="1.0.0",
        display_name="Current Services",
        description=(
            "Current snapshot of canonical homelab services including containers, VMs, "
            "add-ons, and integrations managed across hosts."
        ),
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current service row."),
            "service_id": identifier_field("Stable service identifier used across homelab facts."),
            "service_name": dimension_field("Human-readable name of the service."),
            "service_type": dimension_field(
                "Service category: container, vm, addon, or integration."
            ),
            "host": dimension_field("Host on which the service is running."),
            "criticality": dimension_field(
                "Operational criticality tier: critical, standard, or background."
            ),
            "managed_by": dimension_field(
                "Orchestration platform managing the service: homeassistant, portainer, or manual."
            ),
        },
    ),
    "dim_workload": CurrentDimensionContractDefinition(
        schema_name="dim_workload",
        schema_version="1.0.0",
        display_name="Current Workloads",
        description=(
            "Current snapshot of canonical homelab workloads representing containers, "
            "VMs, and processes running across hosts."
        ),
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current workload row."),
            "workload_id": identifier_field("Stable workload identifier used across homelab facts."),
            "entity_id": identifier_field(
                "Home Assistant entity identifier associated with the workload, if any."
            ),
            "display_name": dimension_field("Human-readable workload name shown in dashboards."),
            "host": dimension_field("Host on which the workload is running."),
            "workload_type": dimension_field(
                "Workload category: container, vm, or process."
            ),
        },
    ),
    "dim_node": CurrentDimensionContractDefinition(
        schema_name="dim_node",
        schema_version="1.0.0",
        display_name="Current Infrastructure Nodes",
        description=(
            "Current snapshot of canonical infrastructure nodes including physical hosts "
            "and virtual machines in the homelab cluster."
        ),
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current node row."),
            "hostname": identifier_field("Stable hostname used as the natural key for the node."),
            "node_name": dimension_field("Human-readable node name shown in infrastructure views."),
            "role": dimension_field("Cluster role of the node such as control-plane or worker."),
            "cpu": dimension_field("CPU model or descriptor for the node."),
            "ram_gb": measure_field(
                "Total RAM installed on the node, in gigabytes.",
                aggregation="latest",
                unit="gb",
            ),
            "os": dimension_field("Operating system running on the node."),
        },
    ),
    "dim_device": CurrentDimensionContractDefinition(
        schema_name="dim_device",
        schema_version="1.0.0",
        display_name="Current Devices",
        description=(
            "Current snapshot of canonical physical devices tracked in the homelab "
            "inventory including network gear, sensors, and smart home hardware."
        ),
        field_overrides={
            "sk": identifier_field("Stable surrogate key for the current device row."),
            "device_id": identifier_field("Stable device identifier used across homelab facts."),
            "device_name": dimension_field("Human-readable device name shown in inventory views."),
            "device_type": dimension_field("Device category such as switch, sensor, or hub."),
            "location": dimension_field("Physical location or room where the device is installed."),
            "power_rating_watts": measure_field(
                "Rated power consumption of the device, in watts.",
                aggregation="latest",
                unit="watts",
            ),
        },
    ),
}
