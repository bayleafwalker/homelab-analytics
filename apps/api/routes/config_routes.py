from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException

from apps.api.models import (
    ArchivedStateRequest,
    ColumnMappingPreviewRequest,
    ColumnMappingRequest,
    DatasetContractRequest,
    ExecutionScheduleRequest,
    IngestionDefinitionRequest,
    PublicationDefinitionRequest,
    SourceAssetRequest,
    SourceSystemRequest,
    TransformationPackageRequest,
)
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.shared.extensions import ExtensionRegistry, serialize_extension_registry
from packages.storage.control_plane import (
    ControlPlaneAdminStore,
    ExecutionScheduleCreate,
)
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    PublicationDefinitionCreate,
    RequestHeaderSecretRef,
    SourceAssetCreate,
    SourceSystemCreate,
    TransformationPackageCreate,
)


def register_config_routes(
    app: FastAPI,
    *,
    registry: ExtensionRegistry,
    resolved_config_repository: ControlPlaneAdminStore,
    configured_ingestion_service: ConfiguredCsvIngestionService,
    require_unsafe_admin: Callable[[], None],
    ensure_matching_identifier: Callable[[str, str, str], None],
    to_jsonable: Callable[[Any], Any],
    build_dataset_contract_diff: Callable[
        [DatasetContractConfigRecord, DatasetContractConfigRecord], dict[str, Any]
    ],
    build_column_mapping_diff: Callable[
        [ColumnMappingRecord, ColumnMappingRecord], dict[str, Any]
    ],
) -> None:
    @app.get("/extensions")
    async def list_extensions() -> dict[str, Any]:
        require_unsafe_admin()
        return {"extensions": serialize_extension_registry(registry)}

    @app.get("/sources")
    async def list_sources() -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "source_systems": to_jsonable(
                resolved_config_repository.list_source_systems()
            ),
            "source_assets": to_jsonable(
                resolved_config_repository.list_source_assets()
            ),
        }

    @app.get("/config/source-systems")
    async def list_source_systems() -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "source_systems": to_jsonable(
                resolved_config_repository.list_source_systems()
            )
        }

    @app.post("/config/source-systems", status_code=201)
    async def create_source_system(payload: SourceSystemRequest) -> dict[str, Any]:
        require_unsafe_admin()
        source_system = resolved_config_repository.create_source_system(
            SourceSystemCreate(
                source_system_id=payload.source_system_id,
                name=payload.name,
                source_type=payload.source_type,
                transport=payload.transport,
                schedule_mode=payload.schedule_mode,
                description=payload.description,
                enabled=payload.enabled,
            )
        )
        return {"source_system": to_jsonable(source_system)}

    @app.patch("/config/source-systems/{source_system_id}")
    async def update_source_system(
        source_system_id: str,
        payload: SourceSystemRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier(
            "source_system_id",
            source_system_id,
            payload.source_system_id,
        )
        existing = resolved_config_repository.get_source_system(source_system_id)
        source_system = resolved_config_repository.update_source_system(
            SourceSystemCreate(
                source_system_id=payload.source_system_id,
                name=payload.name,
                source_type=payload.source_type,
                transport=payload.transport,
                schedule_mode=payload.schedule_mode,
                description=payload.description,
                enabled=payload.enabled,
                created_at=existing.created_at,
            )
        )
        return {"source_system": to_jsonable(source_system)}

    @app.get("/config/dataset-contracts")
    async def list_dataset_contracts(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "dataset_contracts": to_jsonable(
                resolved_config_repository.list_dataset_contracts(
                    include_archived=include_archived
                )
            )
        }

    @app.get("/config/dataset-contracts/{dataset_contract_id}")
    async def get_dataset_contract(dataset_contract_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "dataset_contract": to_jsonable(
                resolved_config_repository.get_dataset_contract(dataset_contract_id)
            )
        }

    @app.get("/config/dataset-contracts/{dataset_contract_id}/diff")
    async def get_dataset_contract_diff(
        dataset_contract_id: str,
        other_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        left = resolved_config_repository.get_dataset_contract(dataset_contract_id)
        right = resolved_config_repository.get_dataset_contract(other_id)
        return {
            "diff": build_dataset_contract_diff(
                left,
                right,
            )
        }

    @app.post("/config/dataset-contracts", status_code=201)
    async def create_dataset_contract(
        payload: DatasetContractRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        dataset_contract = resolved_config_repository.create_dataset_contract(
            DatasetContractConfigCreate(
                dataset_contract_id=payload.dataset_contract_id,
                dataset_name=payload.dataset_name,
                version=payload.version,
                allow_extra_columns=payload.allow_extra_columns,
                columns=tuple(
                    DatasetColumnConfig(
                        name=column.name,
                        type=column.type,
                        required=column.required,
                    )
                    for column in payload.columns
                ),
            )
        )
        return {"dataset_contract": to_jsonable(dataset_contract)}

    @app.patch("/config/dataset-contracts/{dataset_contract_id}/archive")
    async def set_dataset_contract_archived_state(
        dataset_contract_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        dataset_contract = resolved_config_repository.set_dataset_contract_archived_state(
            dataset_contract_id,
            archived=payload.archived,
        )
        return {"dataset_contract": to_jsonable(dataset_contract)}

    @app.get("/config/column-mappings")
    async def list_column_mappings(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "column_mappings": to_jsonable(
                resolved_config_repository.list_column_mappings(
                    include_archived=include_archived
                )
            )
        }

    @app.get("/config/column-mappings/{column_mapping_id}")
    async def get_column_mapping(column_mapping_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "column_mapping": to_jsonable(
                resolved_config_repository.get_column_mapping(column_mapping_id)
            )
        }

    @app.get("/config/column-mappings/{column_mapping_id}/diff")
    async def get_column_mapping_diff(
        column_mapping_id: str,
        other_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        left = resolved_config_repository.get_column_mapping(column_mapping_id)
        right = resolved_config_repository.get_column_mapping(other_id)
        return {"diff": build_column_mapping_diff(left, right)}

    @app.post("/config/column-mappings", status_code=201)
    async def create_column_mapping(payload: ColumnMappingRequest) -> dict[str, Any]:
        require_unsafe_admin()
        column_mapping = resolved_config_repository.create_column_mapping(
            ColumnMappingCreate(
                column_mapping_id=payload.column_mapping_id,
                source_system_id=payload.source_system_id,
                dataset_contract_id=payload.dataset_contract_id,
                version=payload.version,
                rules=tuple(
                    ColumnMappingRule(
                        target_column=rule.target_column,
                        source_column=rule.source_column,
                        default_value=rule.default_value,
                    )
                    for rule in payload.rules
                ),
            )
        )
        return {"column_mapping": to_jsonable(column_mapping)}

    @app.patch("/config/column-mappings/{column_mapping_id}/archive")
    async def set_column_mapping_archived_state(
        column_mapping_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        column_mapping = resolved_config_repository.set_column_mapping_archived_state(
            column_mapping_id,
            archived=payload.archived,
        )
        return {"column_mapping": to_jsonable(column_mapping)}

    @app.post("/config/column-mappings/preview")
    async def preview_column_mapping(
        payload: ColumnMappingPreviewRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        column_mapping = resolved_config_repository.get_column_mapping(
            payload.column_mapping_id
        )
        if column_mapping.dataset_contract_id != payload.dataset_contract_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Column mapping dataset contract does not match the requested preview contract."
                ),
            )
        preview = configured_ingestion_service.preview_mapping(
            source_bytes=payload.sample_csv.encode("utf-8"),
            source_system_id=column_mapping.source_system_id,
            dataset_contract_id=payload.dataset_contract_id,
            column_mapping_id=payload.column_mapping_id,
            preview_limit=payload.preview_limit,
        )
        return {"preview": to_jsonable(preview)}

    @app.get("/config/transformation-packages")
    async def list_transformation_packages() -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "transformation_packages": to_jsonable(
                resolved_config_repository.list_transformation_packages()
            )
        }

    @app.post("/config/transformation-packages", status_code=201)
    async def create_transformation_package(
        payload: TransformationPackageRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        transformation_package = resolved_config_repository.create_transformation_package(
            TransformationPackageCreate(
                transformation_package_id=payload.transformation_package_id,
                name=payload.name,
                handler_key=payload.handler_key,
                version=payload.version,
                description=payload.description,
            )
        )
        return {"transformation_package": to_jsonable(transformation_package)}

    @app.get("/config/publication-definitions")
    async def list_publication_definitions(
        transformation_package_id: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "publication_definitions": to_jsonable(
                resolved_config_repository.list_publication_definitions(
                    transformation_package_id=transformation_package_id
                )
            )
        }

    @app.post("/config/publication-definitions", status_code=201)
    async def create_publication_definition(
        payload: PublicationDefinitionRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        publication_definition = resolved_config_repository.create_publication_definition(
            PublicationDefinitionCreate(
                publication_definition_id=payload.publication_definition_id,
                transformation_package_id=payload.transformation_package_id,
                publication_key=payload.publication_key,
                name=payload.name,
                description=payload.description,
            ),
            extension_registry=registry,
        )
        return {"publication_definition": to_jsonable(publication_definition)}

    @app.get("/config/source-assets")
    async def list_source_assets(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "source_assets": to_jsonable(
                resolved_config_repository.list_source_assets(
                    include_archived=include_archived
                )
            )
        }

    @app.post("/config/source-assets", status_code=201)
    async def create_source_asset(payload: SourceAssetRequest) -> dict[str, Any]:
        require_unsafe_admin()
        source_asset = resolved_config_repository.create_source_asset(
            SourceAssetCreate(
                source_asset_id=payload.source_asset_id,
                source_system_id=payload.source_system_id,
                dataset_contract_id=payload.dataset_contract_id,
                column_mapping_id=payload.column_mapping_id,
                name=payload.name,
                asset_type=payload.asset_type,
                transformation_package_id=payload.transformation_package_id,
                description=payload.description,
                enabled=payload.enabled,
            )
        )
        return {"source_asset": to_jsonable(source_asset)}

    @app.patch("/config/source-assets/{source_asset_id}")
    async def update_source_asset(
        source_asset_id: str,
        payload: SourceAssetRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier(
            "source_asset_id",
            source_asset_id,
            payload.source_asset_id,
        )
        existing = resolved_config_repository.get_source_asset(source_asset_id)
        source_asset = resolved_config_repository.update_source_asset(
            SourceAssetCreate(
                source_asset_id=payload.source_asset_id,
                source_system_id=payload.source_system_id,
                dataset_contract_id=payload.dataset_contract_id,
                column_mapping_id=payload.column_mapping_id,
                transformation_package_id=payload.transformation_package_id,
                name=payload.name,
                asset_type=payload.asset_type,
                description=payload.description,
                enabled=payload.enabled,
                archived=existing.archived,
                created_at=existing.created_at,
            )
        )
        return {"source_asset": to_jsonable(source_asset)}

    @app.patch("/config/source-assets/{source_asset_id}/archive")
    async def set_source_asset_archived_state(
        source_asset_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        source_asset = resolved_config_repository.set_source_asset_archived_state(
            source_asset_id,
            archived=payload.archived,
        )
        return {"source_asset": to_jsonable(source_asset)}

    @app.delete("/config/source-assets/{source_asset_id}", status_code=204)
    async def delete_source_asset(source_asset_id: str) -> None:
        require_unsafe_admin()
        resolved_config_repository.delete_source_asset(source_asset_id)

    @app.get("/config/ingestion-definitions")
    async def list_ingestion_definitions(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "ingestion_definitions": to_jsonable(
                resolved_config_repository.list_ingestion_definitions(
                    include_archived=include_archived
                )
            )
        }

    @app.post("/config/ingestion-definitions", status_code=201)
    async def create_ingestion_definition(
        payload: IngestionDefinitionRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ingestion_definition = resolved_config_repository.create_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id=payload.ingestion_definition_id,
                source_asset_id=payload.source_asset_id,
                transport=payload.transport,
                schedule_mode=payload.schedule_mode,
                source_path=payload.source_path,
                file_pattern=payload.file_pattern,
                processed_path=payload.processed_path,
                failed_path=payload.failed_path,
                poll_interval_seconds=payload.poll_interval_seconds,
                request_url=payload.request_url,
                request_method=payload.request_method,
                request_headers=tuple(
                    RequestHeaderSecretRef(
                        name=header.name,
                        secret_name=header.secret_name,
                        secret_key=header.secret_key,
                    )
                    for header in payload.request_headers
                ),
                request_timeout_seconds=payload.request_timeout_seconds,
                response_format=payload.response_format,
                output_file_name=payload.output_file_name,
                enabled=payload.enabled,
                source_name=payload.source_name,
            )
        )
        return {"ingestion_definition": to_jsonable(ingestion_definition)}

    @app.patch("/config/ingestion-definitions/{ingestion_definition_id}")
    async def update_ingestion_definition(
        ingestion_definition_id: str,
        payload: IngestionDefinitionRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier(
            "ingestion_definition_id",
            ingestion_definition_id,
            payload.ingestion_definition_id,
        )
        existing = resolved_config_repository.get_ingestion_definition(
            ingestion_definition_id
        )
        ingestion_definition = resolved_config_repository.update_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id=payload.ingestion_definition_id,
                source_asset_id=payload.source_asset_id,
                transport=payload.transport,
                schedule_mode=payload.schedule_mode,
                source_path=payload.source_path,
                file_pattern=payload.file_pattern,
                processed_path=payload.processed_path,
                failed_path=payload.failed_path,
                poll_interval_seconds=payload.poll_interval_seconds,
                request_url=payload.request_url,
                request_method=payload.request_method,
                request_headers=tuple(
                    RequestHeaderSecretRef(
                        name=header.name,
                        secret_name=header.secret_name,
                        secret_key=header.secret_key,
                    )
                    for header in payload.request_headers
                ),
                request_timeout_seconds=payload.request_timeout_seconds,
                response_format=payload.response_format,
                output_file_name=payload.output_file_name,
                enabled=payload.enabled,
                archived=existing.archived,
                source_name=payload.source_name,
                created_at=existing.created_at,
            )
        )
        return {"ingestion_definition": to_jsonable(ingestion_definition)}

    @app.patch("/config/ingestion-definitions/{ingestion_definition_id}/archive")
    async def set_ingestion_definition_archived_state(
        ingestion_definition_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ingestion_definition = (
            resolved_config_repository.set_ingestion_definition_archived_state(
                ingestion_definition_id,
                archived=payload.archived,
            )
        )
        return {"ingestion_definition": to_jsonable(ingestion_definition)}

    @app.delete("/config/ingestion-definitions/{ingestion_definition_id}", status_code=204)
    async def delete_ingestion_definition(ingestion_definition_id: str) -> None:
        require_unsafe_admin()
        resolved_config_repository.delete_ingestion_definition(ingestion_definition_id)

    @app.get("/config/execution-schedules")
    async def list_execution_schedules(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "execution_schedules": to_jsonable(
                resolved_config_repository.list_execution_schedules(
                    include_archived=include_archived
                )
            )
        }

    @app.post("/config/execution-schedules", status_code=201)
    async def create_execution_schedule(
        payload: ExecutionScheduleRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        schedule = resolved_config_repository.create_execution_schedule(
            ExecutionScheduleCreate(
                schedule_id=payload.schedule_id,
                target_kind=payload.target_kind,
                target_ref=payload.target_ref,
                cron_expression=payload.cron_expression,
                timezone=payload.timezone,
                enabled=payload.enabled,
                max_concurrency=payload.max_concurrency,
            )
        )
        return {"execution_schedule": to_jsonable(schedule)}

    @app.patch("/config/execution-schedules/{schedule_id}")
    async def update_execution_schedule(
        schedule_id: str,
        payload: ExecutionScheduleRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier("schedule_id", schedule_id, payload.schedule_id)
        existing = resolved_config_repository.get_execution_schedule(schedule_id)
        schedule = resolved_config_repository.update_execution_schedule(
            ExecutionScheduleCreate(
                schedule_id=payload.schedule_id,
                target_kind=payload.target_kind,
                target_ref=payload.target_ref,
                cron_expression=payload.cron_expression,
                timezone=payload.timezone,
                enabled=payload.enabled,
                archived=existing.archived,
                max_concurrency=payload.max_concurrency,
                next_due_at=existing.next_due_at,
                last_enqueued_at=existing.last_enqueued_at,
                created_at=existing.created_at,
            )
        )
        return {"execution_schedule": to_jsonable(schedule)}

    @app.patch("/config/execution-schedules/{schedule_id}/archive")
    async def set_execution_schedule_archived_state(
        schedule_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        schedule = resolved_config_repository.set_execution_schedule_archived_state(
            schedule_id,
            archived=payload.archived,
        )
        return {"execution_schedule": to_jsonable(schedule)}

    @app.delete("/config/execution-schedules/{schedule_id}", status_code=204)
    async def delete_execution_schedule(schedule_id: str) -> None:
        require_unsafe_admin()
        resolved_config_repository.delete_execution_schedule(schedule_id)
