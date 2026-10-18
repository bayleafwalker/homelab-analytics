"""Homelab-pack mart readers served by ReportingService from the warehouse."""

from __future__ import annotations

from packages.domains.homelab.pipelines.ha_models import (
    DIM_HA_ENTITY_TABLE,
    FACT_HA_STATE_CHANGE_TABLE,
)
from packages.domains.homelab.pipelines.ha_service import (
    get_ha_entities,
    get_ha_entity_history,
)
from packages.domains.homelab.pipelines.homelab_models import (
    MART_BACKUP_FRESHNESS_TABLE,
    MART_SERVICE_HEALTH_CURRENT_TABLE,
    MART_STORAGE_RISK_TABLE,
    MART_WORKLOAD_COST_7D_TABLE,
)
from packages.domains.homelab.pipelines.transformation_homelab import (
    get_backup_freshness,
    get_service_health_current,
    get_storage_risk,
    get_workload_cost_7d,
)
from packages.pipelines.mart_read_registry import MartReader, SchemaEnsuringReader

HOMELAB_MART_READERS: dict[str, MartReader] = {
    MART_SERVICE_HEALTH_CURRENT_TABLE: get_service_health_current,
    MART_BACKUP_FRESHNESS_TABLE: get_backup_freshness,
    MART_STORAGE_RISK_TABLE: get_storage_risk,
    MART_WORKLOAD_COST_7D_TABLE: get_workload_cost_7d,
    # HA entity reads (no published mart) ensure the HA tables before reading.
    DIM_HA_ENTITY_TABLE: SchemaEnsuringReader(get_ha_entities),
    FACT_HA_STATE_CHANGE_TABLE: SchemaEnsuringReader(get_ha_entity_history),
}
