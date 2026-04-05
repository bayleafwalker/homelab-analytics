"""Home Assistant workload-sensor readings source definition."""
from __future__ import annotations

from packages.platform.capability_types import SourceDefinition

HA_WORKLOAD_SENSORS_SOURCE = SourceDefinition(
    dataset_name="ha_workload_sensors",
    display_name="HA Workload Sensors",
    description="Home Assistant workload sensor readings — CPU and memory per container/VM.",
    retry_kind="ha_workload_sensors",
)
