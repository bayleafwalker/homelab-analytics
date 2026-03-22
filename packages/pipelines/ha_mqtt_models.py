from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HaMqttEntityDefinition:
    object_id: str
    name: str
    state_key: str
    icon: str | None = None
    device_class: str | None = None
    unit_of_measurement: str | None = None
    publication_key: str | None = None
    ui_descriptor_key: str | None = None
