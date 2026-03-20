"""Homelab domain capability pack manifest — sources, workflows, publications, and UI.

The homelab pack owns service health, backup freshness, storage risk, and workload cost
publications. Primary data source is Home Assistant (REST/WebSocket) or CSV/JSON landing.

See docs/architecture/category-governance.md and docs/sprints/homelab-capability-pack.md
for full context.
"""
from __future__ import annotations

from packages.domains.homelab.sources.ha_backup_runs import HA_BACKUP_RUNS_SOURCE
from packages.domains.homelab.sources.ha_service_states import HA_SERVICE_STATES_SOURCE
from packages.domains.homelab.sources.ha_storage_sensors import HA_STORAGE_SENSORS_SOURCE
from packages.domains.homelab.sources.ha_workload_sensors import HA_WORKLOAD_SENSORS_SOURCE
from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    UiDescriptor,
    WorkflowDefinition,
)

HOMELAB_PACK = CapabilityPack(
    name="homelab",
    version="0.1.0",
    sources=(
        HA_SERVICE_STATES_SOURCE,
        HA_BACKUP_RUNS_SOURCE,
        HA_STORAGE_SENSORS_SOURCE,
        HA_WORKLOAD_SENSORS_SOURCE,
    ),
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
            schema_name="service_health_current",
            display_name="Service Health (Current)",
            description="Latest health state per service with uptime and last-change timestamp.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="backup_freshness",
            schema_name="backup_freshness",
            display_name="Backup Freshness",
            description="Most recent backup per target with staleness flag (>24h = stale).",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="storage_risk",
            schema_name="storage_risk",
            display_name="Storage Risk",
            description="Per-device capacity usage with risk tier (warn >80%, crit >90%).",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
        PublicationDefinition(
            key="workload_cost_7d",
            schema_name="workload_cost_7d",
            display_name="Workload Cost (7-day rolling)",
            description="Rolling 7-day average CPU and memory per workload with cost estimate.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
        ),
    ),
    ui_descriptors=(
        UiDescriptor(
            key="homelab-services",
            nav_label="Services",
            nav_path="/homelab/services",
            kind="dashboard",
            publication_keys=("service_health_current",),
            icon="server",
        ),
        UiDescriptor(
            key="homelab-backups",
            nav_label="Backups",
            nav_path="/homelab/backups",
            kind="table",
            publication_keys=("backup_freshness",),
            icon="archive",
        ),
        UiDescriptor(
            key="homelab-storage",
            nav_label="Storage",
            nav_path="/homelab/storage",
            kind="dashboard",
            publication_keys=("storage_risk",),
            icon="hard-drive",
        ),
        UiDescriptor(
            key="homelab-workloads",
            nav_label="Workloads",
            nav_path="/homelab/workloads",
            kind="table",
            publication_keys=("workload_cost_7d",),
            icon="cpu",
        ),
    ),
)
