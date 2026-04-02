from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from packages.domains.homelab.pipelines.ha_mqtt_models import HaMqttEntityDefinition
from packages.pipelines.reporting_service import ReportingService
from packages.platform.capability_types import CapabilityPack
from packages.platform.publication_contracts import (
    PublicationColumnContract,
    PublicationContract,
    UiDescriptorContract,
    build_publication_contracts,
    build_ui_descriptor_contracts,
)

HA_RENDERER_NAME = "ha"
_SUPPORTED_HA_AGGREGATIONS = frozenset({"count", "sum", "latest", "max"})
logger = logging.getLogger("homelab_analytics.ha_contract_renderer")


@dataclass(frozen=True)
class HaPublicationEntity:
    entity: HaMqttEntityDefinition
    relation_name: str
    state_aggregation: str
    state_field: str | None = None
    filter_field: str | None = None
    filter_values: tuple[str, ...] = ()


def _ha_descriptor_index(
    ui_descriptors: Sequence[UiDescriptorContract],
) -> dict[str, UiDescriptorContract]:
    publication_to_descriptor: dict[str, UiDescriptorContract] = {}
    for descriptor in ui_descriptors:
        if HA_RENDERER_NAME not in descriptor.supported_renderers:
            continue
        for publication_key in descriptor.publication_keys:
            publication_to_descriptor.setdefault(publication_key, descriptor)
    return publication_to_descriptor


def _column_index(
    publication: PublicationContract,
) -> dict[str, PublicationColumnContract]:
    return {column.name: column for column in publication.columns}


def _parse_filter_values(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(
        token.strip().lower()
        for token in value.split(",")
        if token.strip()
    )


def _ha_unit_for_column(column: PublicationColumnContract | None) -> str | None:
    if column is None or column.unit is None:
        return None
    return {
        "percent": "%",
        "bytes": "B",
        "gigabytes": "GB",
        "seconds": "s",
        "hours": "h",
        "days": "d",
    }.get(column.unit)


def _normalized_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def _decimal_value(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _serialize_decimal(value: Decimal) -> str:
    quantized = format(value, "f")
    if "." not in quantized:
        return quantized
    normalized = quantized.rstrip("0").rstrip(".")
    return normalized or "0"


def _filtered_rows(
    entity: HaPublicationEntity,
    rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    if entity.filter_field is None or not entity.filter_values:
        return list(rows)
    allowed = set(entity.filter_values)
    return [
        row
        for row in rows
        if _normalized_value(row.get(entity.filter_field)) in allowed
    ]


def _render_state(
    entity: HaPublicationEntity,
    rows: Sequence[dict[str, Any]],
) -> str | int:
    matching_rows = _filtered_rows(entity, rows)
    if entity.state_aggregation == "count":
        return len(matching_rows)

    state_field = entity.state_field
    if state_field is None:
        return "unavailable"

    if entity.state_aggregation == "latest":
        for row in matching_rows:
            value = row.get(state_field)
            if value is not None:
                return str(value)
        return "unavailable"

    numeric_values = [
        decimal_value
        for row in matching_rows
        for decimal_value in (_decimal_value(row.get(state_field)),)
        if decimal_value is not None
    ]
    if not numeric_values:
        return "unavailable"
    if entity.state_aggregation == "sum":
        return _serialize_decimal(sum(numeric_values, start=Decimal("0")))
    if entity.state_aggregation == "max":
        return _serialize_decimal(max(numeric_values))
    raise ValueError(f"Unsupported HA state aggregation: {entity.state_aggregation}")


def build_ha_publication_entities(
    capability_packs: Sequence[CapabilityPack],
) -> list[HaPublicationEntity]:
    publication_contracts = build_publication_contracts(capability_packs)
    ui_descriptors = build_ui_descriptor_contracts(capability_packs)
    descriptor_index = _ha_descriptor_index(ui_descriptors)

    entities: list[HaPublicationEntity] = []
    for publication in publication_contracts:
        if HA_RENDERER_NAME not in publication.supported_renderers:
            continue

        descriptor = descriptor_index.get(publication.publication_key)
        if descriptor is None:
            raise ValueError(
                "HA renderer publication is missing an HA-enabled UI descriptor: "
                f"{publication.publication_key}"
            )

        renderer_hints = publication.renderer_hints
        state_aggregation = renderer_hints.get("ha_state_aggregation")
        if state_aggregation is None:
            raise ValueError(
                "HA renderer publication is missing ha_state_aggregation: "
                f"{publication.publication_key}"
            )
        if state_aggregation not in _SUPPORTED_HA_AGGREGATIONS:
            raise ValueError(
                "HA renderer publication declares unsupported ha_state_aggregation "
                f"'{state_aggregation}': {publication.publication_key}"
            )

        state_field = renderer_hints.get("ha_state_field")
        filter_field = renderer_hints.get("ha_filter_field")
        filter_values = _parse_filter_values(
            renderer_hints.get("ha_filter_values") or renderer_hints.get("ha_filter_value")
        )
        columns_by_name = _column_index(publication)

        if state_field is not None and state_field not in columns_by_name:
            raise ValueError(
                "HA renderer publication references unknown ha_state_field "
                f"'{state_field}': {publication.publication_key}"
            )
        if filter_field is not None and filter_field not in columns_by_name:
            raise ValueError(
                "HA renderer publication references unknown ha_filter_field "
                f"'{filter_field}': {publication.publication_key}"
            )
        if state_aggregation != "count" and state_field is None:
            raise ValueError(
                "HA renderer publication requires ha_state_field for aggregation "
                f"'{state_aggregation}': {publication.publication_key}"
            )

        object_id = renderer_hints.get(
            "ha_object_id",
            f"homelab_analytics_{publication.publication_key}",
        )
        entity_name = renderer_hints.get("ha_entity_name", publication.display_name)
        column = columns_by_name.get(state_field) if state_field is not None else None
        entity = HaMqttEntityDefinition(
            object_id=object_id,
            name=entity_name,
            state_key=object_id,
            icon=renderer_hints.get("ha_icon"),
            device_class=renderer_hints.get("ha_device_class"),
            unit_of_measurement=renderer_hints.get("ha_unit") or _ha_unit_for_column(column),
            publication_key=publication.publication_key,
            ui_descriptor_key=descriptor.key,
        )
        entities.append(
            HaPublicationEntity(
                entity=entity,
                relation_name=publication.relation_name,
                state_aggregation=state_aggregation,
                state_field=state_field,
                filter_field=filter_field,
                filter_values=filter_values,
            )
        )

    return sorted(entities, key=lambda entity: entity.entity.object_id)


class HaContractRenderer:
    def __init__(
        self,
        reporting_service: ReportingService,
        *,
        capability_packs: Sequence[CapabilityPack],
    ) -> None:
        self._reporting_service = reporting_service
        self._publication_entities = tuple(
            build_ha_publication_entities(capability_packs)
        )

    def entity_definitions(self) -> tuple[HaMqttEntityDefinition, ...]:
        return tuple(entity.entity for entity in self._publication_entities)

    def publication_keys(self) -> tuple[str, ...]:
        return tuple(
            entity.entity.publication_key
            for entity in self._publication_entities
            if entity.entity.publication_key is not None
        )

    def render_states(self) -> dict[str, str | int]:
        rows_by_relation: dict[str, list[dict[str, Any]]] = {}
        rendered_states: dict[str, str | int] = {}
        for entity in self._publication_entities:
            try:
                rows = rows_by_relation.setdefault(
                    entity.relation_name,
                    self._reporting_service.get_relation_rows(entity.relation_name),
                )
            except Exception as exc:
                logger.warning(
                    "HA renderer could not fetch publication rows",
                    extra={
                        "publication_key": entity.entity.publication_key,
                        "relation_name": entity.relation_name,
                        "error": str(exc),
                    },
                )
                rendered_states[entity.entity.state_key] = "unavailable"
                continue
            rendered_states[entity.entity.state_key] = _render_state(entity, rows)
        return rendered_states
