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
    dimension_field,
    identifier_field,
    measure_field,
    status_field,
    time_field,
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
            schema_version="1.0.0",
            display_name="Service Health (Current)",
            description="Latest health state per service with uptime and last-change timestamp.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            renderer_hints={
                "ha_object_id": "homelab_analytics_services_unhealthy",
                "ha_entity_name": "Homelab Services Unhealthy",
                "ha_state_aggregation": "count",
                "ha_filter_field": "state",
                "ha_filter_values": "degraded,stopped",
                "ha_icon": "mdi:server-alert",
            },
            field_semantics={
                "service_id": identifier_field(
                    "Stable service identifier emitted by the homelab source."
                ),
                "service_name": dimension_field(
                    "Human-readable service name."
                ),
                "service_type": dimension_field(
                    "Service class such as container, VM, or integration."
                ),
                "host": dimension_field(
                    "Host or node currently running the service."
                ),
                "criticality": status_field(
                    "Declared service criticality used for prioritization."
                ),
                "managed_by": dimension_field(
                    "System or operator responsible for the service lifecycle."
                ),
                "state": status_field(
                    "Current service health state."
                ),
                "uptime_seconds": measure_field(
                    "Elapsed uptime for the current service state window.",
                    aggregation="latest",
                    unit="seconds",
                ),
                "last_state_change": time_field(
                    "Timestamp when the service last changed state.",
                    grain="timestamp",
                ),
                "recorded_at": time_field(
                    "Timestamp when the health snapshot was recorded.",
                    grain="timestamp",
                ),
            },
        ),
        PublicationDefinition(
            key="backup_freshness",
            schema_name="backup_freshness",
            schema_version="1.0.0",
            display_name="Backup Freshness",
            description="Most recent backup per target with staleness flag (>24h = stale).",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            renderer_hints={
                "ha_object_id": "homelab_analytics_backups_stale",
                "ha_entity_name": "Homelab Backups Stale",
                "ha_state_aggregation": "count",
                "ha_filter_field": "is_stale",
                "ha_filter_values": "true",
                "ha_icon": "mdi:archive-alert",
            },
            field_semantics={
                "target": identifier_field(
                    "Backup target or job identifier being monitored."
                ),
                "last_backup_at": time_field(
                    "Timestamp of the most recent completed backup.",
                    grain="timestamp",
                ),
                "last_status": status_field(
                    "Status of the most recent backup attempt."
                ),
                "last_size_bytes": measure_field(
                    "Size of the most recent backup payload.",
                    aggregation="latest",
                    unit="bytes",
                ),
                "hours_since_backup": measure_field(
                    "Elapsed hours since the most recent backup completed.",
                    aggregation="latest",
                    unit="hours",
                ),
                "is_stale": status_field(
                    "Boolean stale flag derived from the freshness threshold."
                ),
                "backup_count_7d": measure_field(
                    "Number of backup runs observed in the trailing seven days.",
                    aggregation="count",
                    unit="count",
                ),
            },
        ),
        PublicationDefinition(
            key="storage_risk",
            schema_name="storage_risk",
            schema_version="1.0.0",
            display_name="Storage Risk",
            description="Per-device capacity usage with risk tier (warn >80%, crit >90%).",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            renderer_hints={
                "ha_object_id": "homelab_analytics_storage_risk_devices",
                "ha_entity_name": "Homelab Storage Risk Devices",
                "ha_state_aggregation": "count",
                "ha_filter_field": "risk_tier",
                "ha_filter_values": "warn,crit",
                "ha_icon": "mdi:harddisk-alert",
            },
            field_semantics={
                "entity_id": identifier_field(
                    "Stable storage entity identifier from the telemetry source."
                ),
                "device_name": dimension_field(
                    "Human-readable storage device name."
                ),
                "recorded_at": time_field(
                    "Timestamp when the storage measurement was recorded.",
                    grain="timestamp",
                ),
                "capacity_bytes": measure_field(
                    "Total storage capacity for the monitored device.",
                    aggregation="latest",
                    unit="bytes",
                ),
                "used_bytes": measure_field(
                    "Used storage capacity for the monitored device.",
                    aggregation="latest",
                    unit="bytes",
                ),
                "free_bytes": measure_field(
                    "Remaining free storage capacity for the monitored device.",
                    aggregation="latest",
                    unit="bytes",
                ),
                "pct_used": measure_field(
                    "Percent of storage capacity currently consumed.",
                    aggregation="latest",
                    unit="percent",
                ),
                "risk_tier": status_field(
                    "Derived storage-risk tier based on utilization thresholds."
                ),
            },
        ),
        PublicationDefinition(
            key="workload_cost_7d",
            schema_name="workload_cost_7d",
            schema_version="1.0.0",
            display_name="Workload Cost (7-day rolling)",
            description="Rolling 7-day average CPU and memory per workload with cost estimate.",
            visibility="public",
            lineage_required=True,
            retention_policy="rolling_12_months",
            renderer_hints={
                "ha_object_id": "homelab_analytics_workload_cost_estimate",
                "ha_entity_name": "Homelab Workload Cost Estimate",
                "ha_state_aggregation": "sum",
                "ha_state_field": "est_monthly_cost",
                "ha_icon": "mdi:cpu-64-bit",
            },
            field_semantics={
                "workload_id": identifier_field(
                    "Stable workload identifier from the telemetry source."
                ),
                "display_name": dimension_field(
                    "Human-readable workload name."
                ),
                "host": dimension_field(
                    "Host or node currently running the workload."
                ),
                "workload_type": dimension_field(
                    "Workload class such as VM, container, or service."
                ),
                "avg_cpu_pct_7d": measure_field(
                    "Seven-day rolling average CPU utilization.",
                    aggregation="avg",
                    unit="percent",
                ),
                "avg_mem_gb_7d": measure_field(
                    "Seven-day rolling average memory consumption.",
                    aggregation="avg",
                    unit="gigabytes",
                ),
                "reading_count_7d": measure_field(
                    "Number of telemetry readings included in the rolling window.",
                    aggregation="count",
                    unit="count",
                ),
                "est_monthly_cost": measure_field(
                    "Estimated monthly infrastructure cost for the workload.",
                    aggregation="estimate",
                    unit="currency",
                ),
            },
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
            supported_renderers=("web", "ha"),
            renderer_hints={
                "web_surface": "homelab",
                "web_render_mode": "discovery",
                "web_anchor": "homelab-services",
                "web_nav_group": "Operations",
            },
        ),
        UiDescriptor(
            key="homelab-backups",
            nav_label="Backups",
            nav_path="/homelab/backups",
            kind="table",
            publication_keys=("backup_freshness",),
            icon="archive",
            supported_renderers=("web", "ha"),
            renderer_hints={
                "web_surface": "homelab",
                "web_render_mode": "discovery",
                "web_anchor": "homelab-backups",
                "web_nav_group": "Operations",
            },
        ),
        UiDescriptor(
            key="homelab-storage",
            nav_label="Storage",
            nav_path="/homelab/storage",
            kind="dashboard",
            publication_keys=("storage_risk",),
            icon="hard-drive",
            supported_renderers=("web", "ha"),
            renderer_hints={
                "web_surface": "homelab",
                "web_render_mode": "discovery",
                "web_anchor": "homelab-storage",
                "web_nav_group": "Operations",
            },
        ),
        UiDescriptor(
            key="homelab-workloads",
            nav_label="Workloads",
            nav_path="/homelab/workloads",
            kind="table",
            publication_keys=("workload_cost_7d",),
            icon="cpu",
            supported_renderers=("web", "ha"),
            renderer_hints={
                "web_surface": "homelab",
                "web_render_mode": "discovery",
                "web_anchor": "homelab-workloads",
                "web_nav_group": "Operations",
            },
        ),
    ),
)
