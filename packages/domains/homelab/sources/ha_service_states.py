"""Home Assistant service-states source definition."""
from __future__ import annotations

from packages.platform.capability_types import SourceDefinition

HA_SERVICE_STATES_SOURCE = SourceDefinition(
    dataset_name="ha_service_states",
    display_name="HA Service States",
    description="Home Assistant entity states for services (containers, VMs, add-ons).",
    retry_kind="ha_service_states",
)
