"""Home Assistant storage-sensor readings source definition."""
from __future__ import annotations

from packages.platform.capability_types import SourceDefinition

HA_STORAGE_SENSORS_SOURCE = SourceDefinition(
    dataset_name="ha_storage_sensors",
    display_name="HA Storage Sensors",
    description="Home Assistant storage sensor readings — capacity and usage per device.",
    retry_kind="ha_storage_sensors",
)
