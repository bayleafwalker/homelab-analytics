from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Union, cast

from pydantic import BaseModel, ConfigDict, create_model

from packages.platform.publication_contracts import (
    PublicationColumnContract,
    PublicationContract,
    UiDescriptorContract,
)


class PublicationColumnContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    storage_type: str
    json_type: str
    nullable: bool
    description: str
    semantic_role: str
    unit: str | None = None
    grain: str | None = None
    aggregation: str | None = None
    filterable: bool
    sortable: bool


class PublicationContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_key: str
    relation_name: str
    schema_name: str
    schema_version: str
    display_name: str
    description: str | None = None
    pack_name: str | None = None
    pack_version: str | None = None
    visibility: str
    retention_policy: str
    lineage_required: bool
    supported_renderers: list[str]
    renderer_hints: dict[str, str]
    ui_descriptor_keys: list[str]
    columns: list[PublicationColumnContractModel]


class UiDescriptorContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    nav_label: str
    nav_path: str
    kind: str
    publication_keys: list[str]
    icon: str | None = None
    required_permissions: list[str]
    supported_renderers: list[str]
    renderer_hints: dict[str, str]
    default_filters: dict[str, str]


class PublicationContractsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_contracts: list[PublicationContractModel]


class UiDescriptorsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ui_descriptors: list[UiDescriptorContractModel]


class HaMqttStatusModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    connected: bool
    last_publish_at: str | None = None
    publish_count: int
    entity_count: int
    static_entity_count: int
    contract_entity_count: int
    publication_keys: list[str]


class LocalUserModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    username: str
    role: str
    enabled: bool
    created_at: str
    last_login_at: str | None = None
    auth_provider: str


class ServiceTokenModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_id: str
    token_name: str
    role: str
    scopes: list[str]
    expires_at: str | None = None
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None
    revoked: bool
    expired: bool


class RunIssueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    column: str | None = None
    row_number: int | None = None


class PromotionResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    facts_loaded: int
    marts_refreshed: list[str]
    publication_keys: list[str]
    skipped: bool
    skip_reason: str | None = None


class RunModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_name: str
    dataset_name: str
    file_name: str
    raw_path: str
    manifest_path: str
    sha256: str
    row_count: int
    header: list[str]
    status: str
    passed: bool
    issues: list[RunIssueModel]
    created_at: str
    context: dict[str, Any] | None = None
    recovery: dict[str, Any] | None = None


class RunMutationResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: RunModel
    promotion: PromotionResultModel | None = None


class ScheduleDispatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispatch_id: str
    schedule_id: str
    target_kind: str
    target_ref: str
    enqueued_at: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    run_ids: list[str]
    failure_reason: str | None = None
    worker_detail: str | None = None
    claimed_by_worker_id: str | None = None
    claimed_at: str | None = None
    claim_expires_at: str | None = None


class ScheduleDispatchResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispatch: ScheduleDispatchModel


class ConfiguredIngestionProcessResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion_definition_id: str
    discovered_files: int
    processed_files: int
    rejected_files: int
    run_ids: list[str]


class ConfiguredIngestionProcessResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: ConfiguredIngestionProcessResultModel
    promotions: list[PromotionResultModel] | None = None


class LocalUserResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: LocalUserModel


class ServiceTokenResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_token: ServiceTokenModel


class ServiceTokenCreateResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_token: ServiceTokenModel
    token_value: str


_STORAGE_TYPE_TO_PYTHON_TYPE: dict[str, Any] = {
    "DECIMAL": str,
    "DATE": str,
    "TIMESTAMP": str,
    "VARCHAR": str,
    "CHAR": str,
    "TEXT": str,
    "UUID": str,
    "INTEGER": int,
    "INT": int,
    "BIGINT": int,
    "SMALLINT": int,
    "TINYINT": int,
    "DOUBLE": float,
    "FLOAT": float,
    "REAL": float,
    "NUMERIC": float,
    "BOOLEAN": bool,
}


def _python_type_for_storage_type(storage_type: str) -> Any:
    normalized_type = storage_type.upper().replace(" NOT NULL", "").strip()
    base_type = normalized_type.split("(", maxsplit=1)[0].strip()
    return _STORAGE_TYPE_TO_PYTHON_TYPE.get(base_type, str)


def build_row_model(
    model_name: str,
    columns: Sequence[tuple[str, str]],
) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    for column_name, storage_type in columns:
        python_type = _python_type_for_storage_type(storage_type)
        if "NOT NULL" in storage_type.upper():
            fields[column_name] = (python_type, ...)
        else:
            fields[column_name] = (python_type | None, None)
    return cast(type[BaseModel], create_model(model_name, __base__=BaseModel, **cast(Any, fields)))


def build_row_union_type(models: Sequence[type[BaseModel]]) -> Any:
    if not models:
        return dict[str, Any]
    if len(models) == 1:
        return models[0]
    return Union[tuple(models)]  # type: ignore[arg-type]


def build_rows_response_model(
    model_name: str,
    row_model: Any,
    extra_fields: Mapping[str, tuple[Any, Any]] | None = None,
) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {"rows": (list[row_model], ...)}
    for field_name, field_spec in (extra_fields or {}).items():
        fields[field_name] = field_spec
    return cast(type[BaseModel], create_model(model_name, __base__=BaseModel, **cast(Any, fields)))


def build_item_response_model(
    model_name: str,
    item_field_name: str,
    item_model: Any,
    extra_fields: Mapping[str, tuple[Any, Any]] | None = None,
) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {item_field_name: (item_model, ...)}
    for field_name, field_spec in (extra_fields or {}).items():
        fields[field_name] = field_spec
    return cast(type[BaseModel], create_model(model_name, __base__=BaseModel, **cast(Any, fields)))


def build_object_response_model(
    model_name: str,
    fields: Mapping[str, tuple[Any, Any]],
) -> type[BaseModel]:
    return cast(
        type[BaseModel],
        create_model(model_name, __base__=BaseModel, **cast(Any, dict(fields))),
    )


def publication_contract_model_from_dataclass(contract: PublicationContract) -> PublicationContractModel:
    return PublicationContractModel.model_validate(contract, from_attributes=True)


def ui_descriptor_model_from_dataclass(descriptor: UiDescriptorContract) -> UiDescriptorContractModel:
    return UiDescriptorContractModel.model_validate(descriptor, from_attributes=True)


def publication_column_model_from_dataclass(
    column: PublicationColumnContract,
) -> PublicationColumnContractModel:
    return PublicationColumnContractModel.model_validate(column, from_attributes=True)
