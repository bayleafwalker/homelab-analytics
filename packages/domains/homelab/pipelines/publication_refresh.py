"""Homelab-pack publication refresh handlers (homelab, infrastructure, HA).

Each handler refreshes one reporting publication from this pack's
transformation functions; the household composition registers them with the
publication refresh registry.
"""

from __future__ import annotations

from packages.domains.homelab.pipelines.transformation_home_automation import (
    refresh_automation_reliability,
    refresh_climate_summary,
    refresh_device_battery,
)
from packages.domains.homelab.pipelines.transformation_homelab import (
    refresh_backup_freshness,
    refresh_service_health_current,
    refresh_storage_risk,
    refresh_workload_cost_7d,
)
from packages.domains.homelab.pipelines.transformation_infrastructure import (
    refresh_cluster_utilization,
    refresh_infra_cost,
    refresh_uptime_summary,
)
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshHandler,
    StoreRefreshHandler,
)

HOMELAB_PUBLICATION_REFRESH_HANDLERS: dict[str, PublicationRefreshHandler] = {
    "mart_service_health_current": StoreRefreshHandler(refresh_service_health_current),
    "mart_backup_freshness": StoreRefreshHandler(refresh_backup_freshness),
    "mart_storage_risk": StoreRefreshHandler(refresh_storage_risk),
    "mart_workload_cost_7d": StoreRefreshHandler(refresh_workload_cost_7d),
    "mart_cluster_utilization": StoreRefreshHandler(refresh_cluster_utilization),
    "mart_uptime_summary": StoreRefreshHandler(refresh_uptime_summary),
    "mart_infra_cost": StoreRefreshHandler(refresh_infra_cost),
    "mart_climate_summary": StoreRefreshHandler(refresh_climate_summary),
    "mart_automation_reliability": StoreRefreshHandler(refresh_automation_reliability),
    "mart_device_battery": StoreRefreshHandler(refresh_device_battery),
}
