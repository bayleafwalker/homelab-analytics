from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from packages.pipelines.csv_validation import ColumnType
from packages.storage.auth_store import UserRole


class SourceSystemRequest(BaseModel):
    source_system_id: str
    name: str
    source_type: str
    transport: str
    schedule_mode: str
    description: str | None = None
    enabled: bool = True


class DatasetColumnRequest(BaseModel):
    name: str
    type: ColumnType
    required: bool = True


class DatasetContractRequest(BaseModel):
    dataset_contract_id: str
    dataset_name: str
    version: int
    allow_extra_columns: bool
    columns: list[DatasetColumnRequest]


class ColumnMappingRuleRequest(BaseModel):
    target_column: str
    source_column: str | None = None
    default_value: str | None = None


class ColumnMappingRequest(BaseModel):
    column_mapping_id: str
    source_system_id: str
    dataset_contract_id: str
    version: int
    rules: list[ColumnMappingRuleRequest]


class SourceAssetRequest(BaseModel):
    source_asset_id: str
    source_system_id: str
    dataset_contract_id: str
    column_mapping_id: str
    name: str
    asset_type: str
    transformation_package_id: str | None = None
    description: str | None = None
    enabled: bool = True


class TransformationPackageRequest(BaseModel):
    transformation_package_id: str
    name: str
    handler_key: str
    version: int
    description: str | None = None


class PublicationDefinitionRequest(BaseModel):
    publication_definition_id: str
    transformation_package_id: str
    publication_key: str
    name: str
    description: str | None = None


class RequestHeaderRequest(BaseModel):
    name: str
    secret_name: str
    secret_key: str


class IngestionDefinitionRequest(BaseModel):
    ingestion_definition_id: str
    source_asset_id: str
    transport: str
    schedule_mode: str
    source_path: str = ""
    file_pattern: str = "*.csv"
    processed_path: str | None = None
    failed_path: str | None = None
    poll_interval_seconds: int | None = None
    request_url: str | None = None
    request_method: str | None = None
    request_headers: list[RequestHeaderRequest] = Field(default_factory=list)
    request_timeout_seconds: int | None = None
    response_format: str | None = None
    output_file_name: str | None = None
    enabled: bool = True
    source_name: str | None = None


class ExecutionScheduleRequest(BaseModel):
    schedule_id: str
    target_kind: str
    target_ref: str
    cron_expression: str
    timezone: str = "UTC"
    enabled: bool = True
    max_concurrency: int = 1


class ScheduleDispatchRequest(BaseModel):
    schedule_id: str | None = None
    limit: int | None = None


class ConfiguredCsvIngestRequest(BaseModel):
    source_path: str
    source_system_id: str | None = None
    dataset_contract_id: str | None = None
    column_mapping_id: str | None = None
    source_asset_id: str | None = None
    source_name: str = "configured-upload"


class ArchivedStateRequest(BaseModel):
    archived: bool


class ColumnMappingPreviewRequest(BaseModel):
    dataset_contract_id: str
    column_mapping_id: str
    sample_csv: str
    preview_limit: int = 5


class LoginRequest(BaseModel):
    username: str
    password: str


class LocalUserCreateRequest(BaseModel):
    username: str
    password: str
    role: UserRole


class LocalUserUpdateRequest(BaseModel):
    role: UserRole | None = None
    enabled: bool | None = None


class LocalUserPasswordResetRequest(BaseModel):
    password: str


class ServiceTokenCreateRequest(BaseModel):
    token_name: str
    role: UserRole
    scopes: list[str]
    expires_at: datetime | None = None
