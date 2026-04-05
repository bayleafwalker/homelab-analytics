"""Bootstrap source freshness configurations for all domain packs.

Creates SourceFreshnessConfig records for each domain's source assets,
enabling the confidence model to evaluate actual freshness rather than
defaulting everything to CURRENT.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from packages.storage.ingestion_catalog import SourceFreshnessConfigCreate

if TYPE_CHECKING:
    from packages.platform.capability_types import CapabilityPack
    from packages.storage.control_plane import ControlPlaneStore


# Configuration templates for each domain's sources
# Keyed by domain name → dataset name → config parameters
DOMAIN_FRESHNESS_CONFIGS = {
    "finance": {
        "account_transactions": {
            "acquisition_mode": "pull",
            "expected_frequency": "monthly",
            "coverage_kind": "calendar_month",
            "due_day_of_month": 15,
            "expected_window_days": 7,
            "freshness_sla_days": 30,
            "sensitivity_class": "high",
            "reminder_channel": "operator_dashboard",
            "requires_human_action": False,
        },
        "subscriptions": {
            "acquisition_mode": "pull",
            "expected_frequency": "quarterly",
            "coverage_kind": "calendar_quarter",
            "due_day_of_month": 15,
            "expected_window_days": 10,
            "freshness_sla_days": 90,
            "sensitivity_class": "medium",
            "reminder_channel": "operator_dashboard",
            "requires_human_action": False,
        },
        "configured_csv": {
            "acquisition_mode": "manual",
            "expected_frequency": "ad_hoc",
            "coverage_kind": "custom",
            "due_day_of_month": None,
            "expected_window_days": 0,
            "freshness_sla_days": 365,
            "sensitivity_class": "low",
            "reminder_channel": "none",
            "requires_human_action": True,
        },
    },
    "utilities": {
        "utility_rates": {
            "acquisition_mode": "pull",
            "expected_frequency": "monthly",
            "coverage_kind": "calendar_month",
            "due_day_of_month": 1,
            "expected_window_days": 10,
            "freshness_sla_days": 45,
            "sensitivity_class": "medium",
            "reminder_channel": "operator_dashboard",
            "requires_human_action": False,
        },
        "contract_prices": {
            "acquisition_mode": "pull",
            "expected_frequency": "quarterly",
            "coverage_kind": "calendar_quarter",
            "due_day_of_month": 1,
            "expected_window_days": 14,
            "freshness_sla_days": 90,
            "sensitivity_class": "medium",
            "reminder_channel": "operator_dashboard",
            "requires_human_action": False,
        },
    },
    "homelab": {
        "homelab_metrics": {
            "acquisition_mode": "pull",
            "expected_frequency": "weekly",
            "coverage_kind": "calendar_week",
            "due_day_of_month": None,
            "expected_window_days": 3,
            "freshness_sla_days": 14,
            "sensitivity_class": "low",
            "reminder_channel": "none",
            "requires_human_action": False,
        },
        "homelab_costs": {
            "acquisition_mode": "pull",
            "expected_frequency": "monthly",
            "coverage_kind": "calendar_month",
            "due_day_of_month": 5,
            "expected_window_days": 7,
            "freshness_sla_days": 30,
            "sensitivity_class": "low",
            "reminder_channel": "operator_dashboard",
            "requires_human_action": False,
        },
    },
}


def ensure_domain_freshness_configs(
    control_plane: ControlPlaneStore,
    capability_packs: tuple[CapabilityPack, ...],
) -> dict[str, int]:
    """Ensure freshness configs exist for all domain source assets.

    Creates SourceFreshnessConfig records for sources that don't already have
    them. This enables the confidence model to evaluate actual freshness state.

    Args:
        control_plane: Control plane store for config persistence
        capability_packs: Domain capability packs to process

    Returns:
        Summary dict: {domain_name: config_count_created}
    """
    created_counts: dict[str, int] = {}

    # List all existing source assets
    all_assets = {asset.source_asset_id: asset for asset in control_plane.list_source_assets()}
    existing_configs = {
        config.source_asset_id
        for config in control_plane.list_source_freshness_configs()
    }

    # Process each pack
    for pack in capability_packs:
        domain_name = pack.name
        domain_configs = DOMAIN_FRESHNESS_CONFIGS.get(domain_name, {})

        if not domain_configs:
            # No freshness configs defined for this domain
            continue

        created_for_domain = 0

        # For each source in the pack
        for source_def in pack.sources:
            dataset_name = source_def.dataset_name

            if dataset_name not in domain_configs:
                # No config defined for this dataset
                continue

            # Find source assets for this dataset
            matching_assets = [
                asset
                for asset in all_assets.values()
                if asset.source_asset_id.endswith(f"_{dataset_name}")
                or dataset_name in asset.source_asset_id
            ]

            if not matching_assets:
                # No source assets yet; skip (they'll be created later)
                continue

            config_template = domain_configs[dataset_name]

            for asset in matching_assets:
                if asset.source_asset_id in existing_configs:
                    # Config already exists; skip
                    continue

                # Create freshness config
                try:
                    control_plane.create_source_freshness_config(
                        SourceFreshnessConfigCreate(
                            source_asset_id=asset.source_asset_id,
                            acquisition_mode=config_template["acquisition_mode"],
                            expected_frequency=config_template["expected_frequency"],
                            coverage_kind=config_template["coverage_kind"],
                            due_day_of_month=config_template["due_day_of_month"],
                            expected_window_days=config_template["expected_window_days"],
                            freshness_sla_days=config_template["freshness_sla_days"],
                            sensitivity_class=config_template["sensitivity_class"],
                            reminder_channel=config_template["reminder_channel"],
                            requires_human_action=config_template["requires_human_action"],
                            created_at=datetime.now(UTC),
                            updated_at=datetime.now(UTC),
                        )
                    )
                    created_for_domain += 1
                except Exception:
                    # Silently skip on duplicate or other errors
                    # (config may have been created concurrently)
                    pass

        if created_for_domain > 0:
            created_counts[domain_name] = created_for_domain

    return created_counts
