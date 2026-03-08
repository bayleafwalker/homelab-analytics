from __future__ import annotations

from pydantic import BaseModel, Field

from packages.pipelines.csv_validation import ColumnType


class SourceSystemRequest(BaseModel):
    source_system_id: str
    name: str
    source_type: str
    transport: str
    schedule_mode: str
    description: str | None = None


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


class ConfiguredCsvIngestRequest(BaseModel):
    source_path: str
    source_system_id: str
    dataset_contract_id: str
    column_mapping_id: str
    source_asset_id: str | None = None
    source_name: str = "configured-upload"
