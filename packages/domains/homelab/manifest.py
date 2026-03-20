"""Homelab domain capability pack manifest — sources, workflows, publications, and UI.

The homelab pack owns service health, backup freshness, storage risk, and workload cost
publications. Primary data source is Home Assistant (REST/WebSocket) or CSV landing.

See docs/sprints/homelab-capability-pack.md for the full implementation plan.
"""
from __future__ import annotations

from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    UiDescriptor,
    WorkflowDefinition,
)

# TODO: create packages/domains/homelab/sources/ with ha_service_states,
#       ha_backup_runs, ha_storage_sensors, ha_workload_sensors sources
#       and import them here before registering the pack.

HOMELAB_PACK = CapabilityPack(
    name="homelab",
    version="0.1.0",
    sources=(),  # sources added once homelab source modules exist
    workflows=(
        WorkflowDefinition(
            workflow_id="derive-homelab-publications",
            display_name="Derive Homelab Publications",
            source_dataset_name="ha_service_states",
            retry_policy="always",
            idempotency_mode="run_id",
            required_permissions=("operator",),
            command_name="derive-homelab-publications",
            publication_keys=(
                "service_health_current",
                "backup_freshness",
                "storage_risk",
                "workload_cost_7d",
            ),
        ),
    ),
    publications=(
        PublicationDefinition(
            key="service_health_current",
            display_name="Service Health (Current)",
            description="Latest health state per service with uptime and last-change timestamp.",
        ),
        PublicationDefinition(
            key="backup_freshness",
            display_name="Backup Freshness",
            description="Most recent backup per target with staleness flag (>24h = stale).",
        ),
        PublicationDefinition(
            key="storage_risk",
            display_name="Storage Risk",
            description="Per-device capacity usage with risk tier (warn >80%, crit >90%).",
        ),
        PublicationDefinition(
            key="workload_cost_7d",
            display_name="Workload Cost (7-day rolling)",
            description="Rolling 7-day average CPU and memory per workload with cost estimate.",
        ),
    ),
    ui=(
        UiDescriptor(
            page_path="/homelab",
            display_name="Homelab",
            nav_label="Homelab",
            required_publications=(
                "service_health_current",
                "backup_freshness",
                "storage_risk",
                "workload_cost_7d",
            ),
        ),
    ),
)
