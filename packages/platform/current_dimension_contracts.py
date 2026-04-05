from __future__ import annotations

from dataclasses import dataclass, field

from packages.platform.capability_types import PublicationFieldDefinition


@dataclass(frozen=True)
class CurrentDimensionContractDefinition:
    schema_name: str
    schema_version: str
    display_name: str
    description: str
    visibility: str = "public"
    lineage_required: bool = True
    retention_policy: str = "indefinite"
    field_overrides: dict[str, PublicationFieldDefinition] = field(default_factory=dict)
