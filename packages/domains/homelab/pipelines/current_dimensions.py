"""Homelab-pack current-dimension readers (HA entities, infrastructure, services)."""

from __future__ import annotations

from packages.domains.homelab.pipelines.transformation_home_automation import (
    get_current_entities,
)
from packages.domains.homelab.pipelines.transformation_homelab import (
    get_current_services,
    get_current_workloads,
)
from packages.domains.homelab.pipelines.transformation_infrastructure import (
    get_current_devices,
    get_current_nodes,
)
from packages.pipelines.current_dimension_registry import CurrentDimensionReader

HOMELAB_CURRENT_DIMENSION_READERS: dict[str, CurrentDimensionReader] = {
    "dim_entity": get_current_entities,
    "dim_node": get_current_nodes,
    "dim_device": get_current_devices,
    "dim_service": get_current_services,
    "dim_workload": get_current_workloads,
}
