from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    PublicationFieldDefinition,
)
from packages.platform.current_dimension_contracts import CurrentDimensionContractDefinition
from packages.shared.extensions import ExtensionRegistry

if TYPE_CHECKING:
    from packages.storage.control_plane import ControlPlaneStore


@dataclass(frozen=True)
class PublicationColumnContract:
    name: str
    storage_type: str
    json_type: str
    nullable: bool
    description: str
    semantic_role: str
    unit: str | None = None
    grain: str | None = None
    aggregation: str | None = None
    filterable: bool = True
    sortable: bool = True


@dataclass(frozen=True)
class PublicationContract:
    publication_key: str
    relation_name: str
    schema_name: str
    schema_version: str
    display_name: str
    description: str | None
    pack_name: str | None
    pack_version: str | None
    visibility: str
    retention_policy: str
    lineage_required: bool
    supported_renderers: tuple[str, ...] = ()
    renderer_hints: dict[str, str] = field(default_factory=dict)
    ui_descriptor_keys: tuple[str, ...] = ()
    columns: tuple[PublicationColumnContract, ...] = ()
    # Confidence metadata (optional, set at export time from latest snapshot)
    freshness_state: str | None = None
    completeness_pct: int | None = None
    confidence_verdict: str | None = None
    assessed_at: str | None = None  # ISO format timestamp


@dataclass(frozen=True)
class UiDescriptorContract:
    key: str
    nav_label: str
    nav_path: str
    kind: str
    publication_keys: tuple[str, ...]
    icon: str | None
    required_permissions: tuple[str, ...]
    supported_renderers: tuple[str, ...]
    renderer_hints: dict[str, str]
    default_filters: dict[str, str]


@dataclass(frozen=True)
class PublicationRelation:
    relation_name: str
    columns: list[tuple[str, str]]
    order_by: str
    source_query: str | None = None


def _json_type_for_storage_type(storage_type: str) -> str:
    normalized_type = storage_type.upper().replace(" NOT NULL", "").strip()
    base_type = normalized_type.split("(", maxsplit=1)[0].strip()
    if base_type in {
        "DECIMAL",
        "DATE",
        "TIMESTAMP",
        "VARCHAR",
        "CHAR",
        "TEXT",
        "UUID",
    }:
        return "string"
    if base_type in {
        "INTEGER",
        "INT",
        "BIGINT",
        "SMALLINT",
        "TINYINT",
        "DOUBLE",
        "FLOAT",
        "REAL",
        "NUMERIC",
    }:
        return "number"
    if base_type == "BOOLEAN":
        return "boolean"
    return "string"


def _json_nullable(storage_type: str) -> bool:
    return "NOT NULL" not in storage_type.upper()


def _default_description(column_name: str) -> str:
    return column_name.replace("_", " ").capitalize()


def _infer_semantic_role(column_name: str, json_type: str) -> str:
    lower_name = column_name.lower()
    if lower_name.endswith("_id"):
        return "identifier"
    if (
        lower_name.startswith("is_")
        or lower_name in {
            "status",
            "state",
            "direction",
            "severity",
            "assessment",
            "risk_tier",
            "criticality",
            "coverage_status",
            "dominant_driver",
            "last_status",
            "anomaly_type",
            "account_balance_direction",
        }
    ):
        return "status"
    if (
        lower_name.endswith("_at")
        or lower_name.endswith("_date")
        or lower_name.endswith("_month")
        or lower_name.startswith("period_")
        or lower_name in {
            "period",
            "period_label",
            "current_month",
            "valid_from",
            "valid_to",
            "renewal_date",
        }
    ):
        return "time"
    if json_type == "number" or any(
        token in lower_name
        for token in (
            "amount",
            "price",
            "cost",
            "income",
            "expense",
            "net",
            "balance",
            "usage",
            "count",
            "ratio",
            "pct",
            "score",
            "value",
            "quantity",
            "bytes",
            "seconds",
            "hours",
            "days",
            "total",
            "equivalent",
        )
    ):
        return "measure"
    return "dimension"


def _infer_measure_unit(column_name: str) -> str | None:
    lower_name = column_name.lower()
    if "pct" in lower_name:
        return "percent"
    if "ratio" in lower_name:
        return "ratio"
    if "bytes" in lower_name:
        return "bytes"
    if "seconds" in lower_name:
        return "seconds"
    if "hours" in lower_name:
        return "hours"
    if "days" in lower_name:
        return "days"
    if "count" in lower_name:
        return "count"
    if "gb" in lower_name:
        return "gigabytes"
    if any(
        token in lower_name
        for token in (
            "amount",
            "price",
            "cost",
            "income",
            "expense",
            "net",
            "balance",
            "value",
            "equivalent",
        )
    ):
        return "currency"
    return None


def _infer_time_grain(column_name: str, storage_type: str) -> str | None:
    lower_name = column_name.lower()
    upper_storage_type = storage_type.upper()
    if "TIMESTAMP" in upper_storage_type or lower_name.endswith("_at"):
        return "timestamp"
    if lower_name.endswith("_month") or lower_name in {
        "current_month",
        "period_month",
        "billing_month",
        "period",
        "period_label",
    }:
        return "month"
    if "DATE" in upper_storage_type or lower_name.endswith("_date") or lower_name in {
        "valid_from",
        "valid_to",
        "period_start",
        "period_end",
        "renewal_date",
    }:
        return "day"
    return None


def _infer_measure_aggregation(column_name: str) -> str:
    lower_name = column_name.lower()
    if lower_name.startswith("avg_"):
        return "avg"
    if "pct" in lower_name:
        return "pct_change"
    if "count" in lower_name:
        return "count"
    if any(
        token in lower_name
        for token in ("balance", "current_price", "market_reference", "unit_cost")
    ):
        return "latest"
    return "none"


def _default_field_definition(
    column_name: str,
    storage_type: str,
) -> PublicationFieldDefinition:
    json_type = _json_type_for_storage_type(storage_type)
    semantic_role = _infer_semantic_role(column_name, json_type)
    return PublicationFieldDefinition(
        description=_default_description(column_name),
        semantic_role=semantic_role,
        unit=_infer_measure_unit(column_name) if semantic_role == "measure" else None,
        grain=_infer_time_grain(column_name, storage_type) if semantic_role == "time" else None,
        aggregation=(
            _infer_measure_aggregation(column_name)
            if semantic_role == "measure"
            else None
        ),
        filterable=semantic_role != "measure",
        sortable=True,
    )


def _build_columns(
    columns: Sequence[tuple[str, str]],
    *,
    field_definitions: Mapping[str, PublicationFieldDefinition],
) -> tuple[PublicationColumnContract, ...]:
    return tuple(
        PublicationColumnContract(
            name=name,
            storage_type=storage_type,
            json_type=_json_type_for_storage_type(storage_type),
            nullable=_json_nullable(storage_type),
            description=field_definitions[name].description,
            semantic_role=field_definitions[name].semantic_role,
            unit=field_definitions[name].unit,
            grain=field_definitions[name].grain,
            aggregation=field_definitions[name].aggregation,
            filterable=field_definitions[name].filterable,
            sortable=field_definitions[name].sortable,
        )
        for name, storage_type in columns
    )


def _pack_publication_relations(
    capability_packs: Sequence[CapabilityPack],
) -> dict[str, tuple[CapabilityPack, PublicationDefinition]]:
    publication_metadata: dict[str, tuple[CapabilityPack, PublicationDefinition]] = {}
    for pack in capability_packs:
        for publication in pack.publications:
            relation_name = f"mart_{publication.schema_name}"
            publication_metadata[relation_name] = (pack, publication)
    return publication_metadata


def _ui_descriptor_index(
    capability_packs: Sequence[CapabilityPack],
) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    publication_to_descriptor_keys: dict[str, set[str]] = {}
    publication_to_renderers: dict[str, set[str]] = {}
    for pack in capability_packs:
        for ui in pack.ui_descriptors:
            for publication_key in ui.publication_keys:
                publication_to_descriptor_keys.setdefault(publication_key, set()).add(ui.key)
                publication_to_renderers.setdefault(publication_key, set()).update(
                    ui.supported_renderers
                )
    publication_keys = set(publication_to_descriptor_keys) | set(publication_to_renderers)
    return {
        publication_key: (
            tuple(sorted(publication_to_descriptor_keys.get(publication_key, set()))),
            tuple(sorted(publication_to_renderers.get(publication_key, {"web"}))),
        )
        for publication_key in publication_keys
    }


def _publication_field_definitions(
    relation: PublicationRelation,
    *,
    publication: PublicationDefinition | None,
) -> dict[str, PublicationFieldDefinition]:
    column_names = [name for name, _storage_type in relation.columns]
    if publication is None:
        return {
            name: _default_field_definition(name, storage_type)
            for name, storage_type in relation.columns
        }

    semantic_keys = set(publication.field_semantics)
    column_name_set = set(column_names)
    unknown_semantic_keys = sorted(semantic_keys - column_name_set)
    if unknown_semantic_keys:
        raise ValueError(
            f"PublicationDefinition '{publication.key}' declares field semantics for unknown "
            f"columns: {', '.join(unknown_semantic_keys)}"
        )

    missing_semantic_keys = [name for name in column_names if name not in semantic_keys]
    if missing_semantic_keys:
        raise ValueError(
            f"PublicationDefinition '{publication.key}' is missing field semantics for "
            f"columns: {', '.join(missing_semantic_keys)}"
        )

    return {
        name: publication.field_semantics[name]
        for name in column_names
    }


def _current_dimension_field_definitions(
    relation: PublicationRelation,
    *,
    definition: CurrentDimensionContractDefinition,
) -> dict[str, PublicationFieldDefinition]:
    field_definitions = {
        name: _default_field_definition(name, storage_type)
        for name, storage_type in relation.columns
    }
    unknown_override_keys = sorted(set(definition.field_overrides) - set(field_definitions))
    if unknown_override_keys:
        raise ValueError(
            "Current dimension contract declares field semantics for unknown columns: "
            f"{', '.join(unknown_override_keys)}"
        )
    field_definitions.update(definition.field_overrides)
    return field_definitions


def build_publication_relation_map(
    *,
    base_relations: Mapping[str, Any],
    extension_registry: ExtensionRegistry | None = None,
) -> dict[str, PublicationRelation]:
    relation_map = {
        relation_name: PublicationRelation(
            relation_name=relation.relation_name,
            columns=list(relation.columns),
            order_by=relation.order_by,
            source_query=relation.source_query,
        )
        for relation_name, relation in base_relations.items()
    }
    if extension_registry is None:
        return relation_map

    for publication in extension_registry.list_reporting_publications():
        relation_name = publication.relation_name
        if relation_name in relation_map:
            raise ValueError(
                "Publication relation already registered: "
                f"{relation_name}"
            )
        relation_map[relation_name] = PublicationRelation(
            relation_name=publication.relation_name,
            columns=list(publication.columns),
            order_by=publication.order_by,
            source_query=publication.source_query,
        )
    return relation_map


def build_publication_contracts(
    capability_packs: Sequence[CapabilityPack],
    *,
    publication_relations: Mapping[str, Any],
    current_dimension_relations: Mapping[str, str] | None = None,
    current_dimension_contracts: Mapping[
        str,
        CurrentDimensionContractDefinition,
    ] | None = None,
) -> list[PublicationContract]:
    relation_map = {
        relation_name: PublicationRelation(
            relation_name=relation.relation_name,
            columns=list(relation.columns),
            order_by=relation.order_by,
            source_query=relation.source_query,
        )
        for relation_name, relation in publication_relations.items()
    }
    resolved_current_dimension_relations = current_dimension_relations or {}
    resolved_current_dimension_contracts = current_dimension_contracts or {}
    pack_publications = _pack_publication_relations(capability_packs)
    ui_descriptor_index = _ui_descriptor_index(capability_packs)
    current_dimension_relation_keys = {
        relation_name: publication_key
        for publication_key, relation_name in resolved_current_dimension_relations.items()
    }

    missing_relations = sorted(
        relation_name for relation_name in pack_publications if relation_name not in relation_map
    )
    if missing_relations:
        raise ValueError(
            "Capability pack publications are missing reporting relations: "
            f"{', '.join(missing_relations)}"
        )

    contracts: list[PublicationContract] = []
    for relation_name in sorted(relation_map):
        relation = relation_map[relation_name]
        publication_key = current_dimension_relation_keys.get(
            relation_name,
            relation_name,
        )
        pack_metadata = pack_publications.get(relation_name)
        current_dimension_definition = resolved_current_dimension_contracts.get(
            publication_key
        )
        if pack_metadata is not None:
            pack, publication = pack_metadata
            publication_key = publication.key
            schema_name = publication.schema_name
            schema_version = publication.schema_version
            display_name = publication.display_name or publication_key.replace("_", " ").title()
            description = publication.description
            renderer_hints = dict(publication.renderer_hints)
            pack_name = pack.name
            pack_version = pack.version
            visibility = publication.visibility
            retention_policy = publication.retention_policy
            lineage_required = publication.lineage_required
        else:
            publication = None
            schema_name = relation_name
            schema_version = "1.0.0"
            display_name = relation_name.replace("_", " ").title()
            description = None
            renderer_hints = {}
            pack_name = None
            pack_version = None
            visibility = "public"
            retention_policy = "indefinite"
            lineage_required = True
            if current_dimension_definition is not None:
                schema_name = current_dimension_definition.schema_name
                schema_version = current_dimension_definition.schema_version
                display_name = current_dimension_definition.display_name
                description = current_dimension_definition.description
                visibility = current_dimension_definition.visibility
                retention_policy = current_dimension_definition.retention_policy
                lineage_required = current_dimension_definition.lineage_required

        if publication is not None:
            field_definitions = _publication_field_definitions(
                relation,
                publication=publication,
            )
        elif current_dimension_definition is not None:
            field_definitions = _current_dimension_field_definitions(
                relation,
                definition=current_dimension_definition,
            )
        else:
            field_definitions = _publication_field_definitions(
                relation,
                publication=None,
            )
        ui_descriptor_keys, supported_renderers = ui_descriptor_index.get(
            publication_key,
            ((), ("web",)),
        )
        contracts.append(
            PublicationContract(
                publication_key=publication_key,
                relation_name=relation_name,
                schema_name=schema_name,
                schema_version=schema_version,
                display_name=display_name,
                description=description,
                pack_name=pack_name,
                pack_version=pack_version,
                visibility=visibility,
                retention_policy=retention_policy,
                lineage_required=lineage_required,
                supported_renderers=supported_renderers,
                renderer_hints=renderer_hints,
                ui_descriptor_keys=ui_descriptor_keys,
                columns=_build_columns(
                    relation.columns,
                    field_definitions=field_definitions,
                ),
            )
        )
    return contracts


def build_ui_descriptor_contracts(
    capability_packs: Sequence[CapabilityPack],
) -> list[UiDescriptorContract]:
    contracts: list[UiDescriptorContract] = []
    for pack in capability_packs:
        for descriptor in pack.ui_descriptors:
            contracts.append(
                UiDescriptorContract(
                    key=descriptor.key,
                    nav_label=descriptor.nav_label,
                    nav_path=descriptor.nav_path,
                    kind=descriptor.kind,
                    publication_keys=descriptor.publication_keys,
                    icon=descriptor.icon,
                    required_permissions=descriptor.required_permissions,
                    supported_renderers=descriptor.supported_renderers,
                    renderer_hints=dict(descriptor.renderer_hints),
                    default_filters=dict(descriptor.default_filters),
                )
            )
    return sorted(contracts, key=lambda descriptor: descriptor.key)


def build_publication_contract_catalog(
    capability_packs: Sequence[CapabilityPack],
    *,
    publication_relations: Mapping[str, Any],
    current_dimension_relations: Mapping[str, str] | None = None,
    current_dimension_contracts: Mapping[
        str,
        CurrentDimensionContractDefinition,
    ] | None = None,
    control_plane: ControlPlaneStore | None = None,
) -> dict[str, Any]:
    contracts = build_publication_contracts(
        capability_packs,
        publication_relations=publication_relations,
        current_dimension_relations=current_dimension_relations,
        current_dimension_contracts=current_dimension_contracts,
    )

    # Enrich contracts with latest confidence metadata if control_plane is available
    if control_plane is not None:
        from packages.pipelines.publication_confidence_service import (
            get_latest_publication_confidence,
        )

        enriched_contracts = []
        for contract in contracts:
            latest_confidence = get_latest_publication_confidence(
                contract.publication_key,
                control_plane,
            )
            if latest_confidence is not None:
                # Replace contract with enriched version
                contract = replace(
                    contract,
                    freshness_state=str(latest_confidence.freshness_state),
                    completeness_pct=latest_confidence.completeness_pct,
                    confidence_verdict=str(latest_confidence.confidence_verdict),
                    assessed_at=latest_confidence.assessed_at.isoformat(),
                )
            enriched_contracts.append(contract)
        contracts = enriched_contracts

    ui_descriptors = build_ui_descriptor_contracts(capability_packs)
    return {
        "publication_contracts": contracts,
        "ui_descriptors": ui_descriptors,
    }
