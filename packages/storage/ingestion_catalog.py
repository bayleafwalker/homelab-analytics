from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from packages.pipelines.builtin_packages import BUILTIN_TRANSFORMATION_PACKAGE_SPECS
from packages.pipelines.csv_validation import ColumnContract, ColumnType, DatasetContract
from packages.shared.extensions import ExtensionRegistry


@dataclass(frozen=True)
class SourceSystemCreate:
    source_system_id: str
    name: str
    source_type: str
    transport: str
    schedule_mode: str
    description: str | None = None
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SourceSystemRecord:
    source_system_id: str
    name: str
    source_type: str
    transport: str
    schedule_mode: str
    description: str | None
    enabled: bool
    created_at: datetime


@dataclass(frozen=True)
class DatasetColumnConfig:
    name: str
    type: ColumnType
    required: bool = True


@dataclass(frozen=True)
class DatasetContractConfigCreate:
    dataset_contract_id: str
    dataset_name: str
    version: int
    allow_extra_columns: bool
    columns: tuple[DatasetColumnConfig, ...]
    archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DatasetContractConfigRecord:
    dataset_contract_id: str
    dataset_name: str
    version: int
    allow_extra_columns: bool
    columns: tuple[DatasetColumnConfig, ...]
    archived: bool
    created_at: datetime


@dataclass(frozen=True)
class ColumnMappingRule:
    target_column: str
    source_column: str | None = None
    default_value: str | None = None
    function_key: str | None = None


@dataclass(frozen=True)
class ColumnMappingCreate:
    column_mapping_id: str
    source_system_id: str
    dataset_contract_id: str
    version: int
    rules: tuple[ColumnMappingRule, ...]
    archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ColumnMappingRecord:
    column_mapping_id: str
    source_system_id: str
    dataset_contract_id: str
    version: int
    rules: tuple[ColumnMappingRule, ...]
    archived: bool
    created_at: datetime


@dataclass(frozen=True)
class SourceAssetCreate:
    source_asset_id: str
    source_system_id: str
    dataset_contract_id: str
    column_mapping_id: str
    name: str
    asset_type: str
    transformation_package_id: str | None = None
    description: str | None = None
    enabled: bool = True
    archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SourceAssetRecord:
    source_asset_id: str
    source_system_id: str
    dataset_contract_id: str
    column_mapping_id: str
    transformation_package_id: str | None
    name: str
    asset_type: str
    description: str | None
    enabled: bool
    archived: bool
    created_at: datetime


@dataclass(frozen=True)
class SourceFreshnessConfigCreate:
    source_asset_id: str
    acquisition_mode: str
    expected_frequency: str
    coverage_kind: str
    due_day_of_month: int | None
    expected_window_days: int
    freshness_sla_days: int
    sensitivity_class: str
    reminder_channel: str
    requires_human_action: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SourceFreshnessConfigRecord:
    source_asset_id: str
    acquisition_mode: str
    expected_frequency: str
    coverage_kind: str
    due_day_of_month: int | None
    expected_window_days: int
    freshness_sla_days: int
    sensitivity_class: str
    reminder_channel: str
    requires_human_action: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ReferenceFactCreate:
    entity_type: str
    entity_key: str
    attribute: str
    value: str
    effective_from: date
    fact_id: str | None = None
    effective_to: date | None = None
    source: str = "operator"
    created_by: str = ""
    note: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_by: str | None = None
    closed_at: datetime | None = None


@dataclass(frozen=True)
class ReferenceFactRecord:
    fact_id: str
    entity_type: str
    entity_key: str
    attribute: str
    value: str
    effective_from: date
    effective_to: date | None
    source: str
    created_by: str
    note: str | None
    created_at: datetime
    closed_by: str | None
    closed_at: datetime | None


@dataclass(frozen=True)
class TransformationPackageCreate:
    transformation_package_id: str
    name: str
    handler_key: str
    version: int
    description: str | None = None
    archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class TransformationPackageRecord:
    transformation_package_id: str
    name: str
    handler_key: str
    version: int
    description: str | None
    archived: bool
    created_at: datetime


@dataclass(frozen=True)
class PublicationDefinitionCreate:
    publication_definition_id: str
    transformation_package_id: str
    publication_key: str
    name: str
    description: str | None = None
    archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PublicationDefinitionRecord:
    publication_definition_id: str
    transformation_package_id: str
    publication_key: str
    name: str
    description: str | None
    archived: bool
    created_at: datetime


@dataclass(frozen=True)
class RequestHeaderSecretRef:
    name: str
    secret_name: str
    secret_key: str


@dataclass(frozen=True)
class IngestionDefinitionCreate:
    ingestion_definition_id: str
    source_asset_id: str
    transport: str
    schedule_mode: str
    source_path: str
    file_pattern: str = "*.csv"
    processed_path: str | None = None
    failed_path: str | None = None
    poll_interval_seconds: int | None = None
    request_url: str | None = None
    request_method: str | None = None
    request_headers: tuple[RequestHeaderSecretRef, ...] = ()
    request_timeout_seconds: int | None = None
    response_format: str | None = None
    output_file_name: str | None = None
    enabled: bool = True
    archived: bool = False
    source_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class IngestionDefinitionRecord:
    ingestion_definition_id: str
    source_asset_id: str
    transport: str
    schedule_mode: str
    source_path: str
    file_pattern: str
    processed_path: str | None
    failed_path: str | None
    poll_interval_seconds: int | None
    request_url: str | None
    request_method: str | None
    request_headers: tuple[RequestHeaderSecretRef, ...]
    request_timeout_seconds: int | None
    response_format: str | None
    output_file_name: str | None
    enabled: bool
    archived: bool
    source_name: str | None
    created_at: datetime


def resolve_dataset_contract(
    dataset_contract: DatasetContractConfigRecord,
) -> DatasetContract:
    return DatasetContract(
        dataset_name=dataset_contract.dataset_name,
        columns=tuple(
            ColumnContract(
                name=column.name,
                type=column.type,
                required=column.required,
            )
            for column in dataset_contract.columns
        ),
        allow_extra_columns=dataset_contract.allow_extra_columns,
    )


def generate_reference_fact_id() -> str:
    return uuid.uuid4().hex


def _deserialize_columns(value: str) -> tuple[DatasetColumnConfig, ...]:
    return tuple(
        DatasetColumnConfig(
            name=column["name"],
            type=ColumnType(column["type"]),
            required=column["required"],
        )
        for column in json.loads(value)
    )


def _deserialize_rules(value: str) -> tuple[ColumnMappingRule, ...]:
    return tuple(
        ColumnMappingRule(
            target_column=rule["target_column"],
            source_column=rule.get("source_column"),
            default_value=rule.get("default_value"),
            function_key=rule.get("function_key"),
        )
        for rule in json.loads(value)
    )


def _serialize_request_headers(headers: tuple[RequestHeaderSecretRef, ...]) -> str:
    return json.dumps(
        [
            {
                "name": header.name,
                "secret_name": header.secret_name,
                "secret_key": header.secret_key,
            }
            for header in headers
        ]
    )


def _deserialize_request_headers(value: str | None) -> tuple[RequestHeaderSecretRef, ...]:
    if not value:
        return ()
    return tuple(
        RequestHeaderSecretRef(
            name=header["name"],
            secret_name=header["secret_name"],
            secret_key=header["secret_key"],
        )
        for header in json.loads(value)
    )


def _validate_mapping_rules(rules: tuple[ColumnMappingRule, ...]) -> None:
    seen_targets: set[str] = set()

    for rule in rules:
        if rule.target_column in seen_targets:
            raise ValueError(
                f"Duplicate mapping rule for target column: {rule.target_column}"
            )
        if rule.source_column is None and rule.default_value is None:
            raise ValueError(
                f"Mapping rule must define source_column or default_value for target column: {rule.target_column}"
            )
        if rule.function_key is not None and not rule.function_key.strip():
            raise ValueError(
                f"Mapping rule function_key must not be empty for target column: {rule.target_column}"
            )
        seen_targets.add(rule.target_column)


_BUILTIN_TRANSFORMATION_PACKAGES = tuple(
    TransformationPackageCreate(
        transformation_package_id=spec.transformation_package_id,
        name=spec.name,
        handler_key=spec.handler_key,
        version=spec.version,
        description=spec.description,
    )
    for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS
)


_BUILTIN_PUBLICATION_DEFINITIONS = tuple(
    PublicationDefinitionCreate(
        publication_definition_id=publication.publication_definition_id,
        transformation_package_id=spec.transformation_package_id,
        publication_key=publication.publication_key,
        name=publication.name,
    )
    for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS
    for publication in spec.publications
)


def allowed_publication_keys(
    *,
    extension_registry: ExtensionRegistry | None = None,
) -> set[str]:
    from packages.pipelines.builtin_reporting import PUBLICATION_RELATIONS

    allowed_keys = set(PUBLICATION_RELATIONS)
    if extension_registry is not None:
        allowed_keys.update(
            publication.relation_name
            for publication in extension_registry.list_reporting_publications()
        )
    return allowed_keys


def serialize_publication_keys(
    *,
    extension_registry: ExtensionRegistry | None = None,
    promotion_handler_registry=None,
) -> list[dict[str, object]]:
    from packages.pipelines.promotion_registry import get_default_promotion_handler_registry

    registry = promotion_handler_registry or get_default_promotion_handler_registry()
    publication_map: dict[str, dict[str, set[str]]] = {}
    for handler in registry.list():
        for publication_key in handler.supported_publications:
            entry = publication_map.setdefault(
                publication_key,
                {
                    "source_kinds": set(),
                    "supported_handlers": set(),
                    "default_handlers": set(),
                    "reporting_extensions": set(),
                },
            )
            entry["source_kinds"].add("transformation_handler")
            entry["supported_handlers"].add(handler.handler_key)
            if publication_key in handler.default_publications:
                entry["default_handlers"].add(handler.handler_key)
    if extension_registry is not None:
        for extension in extension_registry.list_extensions("reporting"):
            for publication in extension.publication_relations:
                entry = publication_map.setdefault(
                    publication.relation_name,
                    {
                        "source_kinds": set(),
                        "supported_handlers": set(),
                        "default_handlers": set(),
                        "reporting_extensions": set(),
                    },
                )
                entry["source_kinds"].add("reporting_extension")
                entry["reporting_extensions"].add(extension.key)
    return [
        {
            "publication_key": publication_key,
            "source_kinds": sorted(values["source_kinds"]),
            "supported_handlers": sorted(values["supported_handlers"]),
            "default_handlers": sorted(values["default_handlers"]),
            "reporting_extensions": sorted(values["reporting_extensions"]),
        }
        for publication_key, values in sorted(publication_map.items())
    ]


def allowed_transformation_handler_keys(*, promotion_handler_registry=None) -> set[str]:
    from packages.pipelines.promotion_registry import get_default_promotion_handler_registry

    registry = promotion_handler_registry or get_default_promotion_handler_registry()
    return {handler.handler_key for handler in registry.list()}


def validate_transformation_handler_key(
    handler_key: str,
    *,
    promotion_handler_registry=None,
) -> None:
    if handler_key in allowed_transformation_handler_keys(
        promotion_handler_registry=promotion_handler_registry
    ):
        return

    raise ValueError(
        "Unknown transformation handler key. Register a promotion handler or use an existing built-in handler key: "
        f"{handler_key!r}"
    )


def validate_publication_support(
    publication_key: str,
    *,
    handler_key: str,
    transformation_package_id: str | None = None,
    extension_registry: ExtensionRegistry | None = None,
    promotion_handler_registry,
) -> None:
    validate_publication_key(
        publication_key,
        extension_registry=extension_registry,
    )
    extension_publication_keys: set[str] = set()
    if extension_registry is not None:
        extension_publication_keys.update(
            publication.relation_name
            for publication in extension_registry.list_reporting_publications()
        )
    if publication_key in extension_publication_keys:
        return

    handler = promotion_handler_registry.get(handler_key)
    if publication_key in handler.supported_publications:
        return

    subject = transformation_package_id or handler_key
    raise ValueError(
        "Publication key is not supported by the selected transformation package handler: "
        f"{subject!r} does not support {publication_key!r}"
    )


def validate_publication_key(
    publication_key: str,
    *,
    extension_registry: ExtensionRegistry | None = None,
) -> None:
    if publication_key in allowed_publication_keys(
        extension_registry=extension_registry
    ):
        return

    raise ValueError(
        "Unknown publication key. Register a published reporting relation or use an existing built-in publication key: "
        f"{publication_key!r}"
    )
