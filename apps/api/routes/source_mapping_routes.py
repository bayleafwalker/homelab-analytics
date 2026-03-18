"""Source mapping routes: column mappings CRUD, diff, archive, and preview."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException

from apps.api.models import (
    ArchivedStateRequest,
    ColumnMappingPreviewRequest,
    ColumnMappingRequest,
)
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.shared.function_registry import FunctionRegistry, validate_function_key
from packages.storage.control_plane import ControlPlaneAdminStore
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRecord,
    ColumnMappingRule,
)


def register_source_mapping_routes(
    app: FastAPI,
    *,
    function_registry: FunctionRegistry,
    resolved_config_repository: ControlPlaneAdminStore,
    configured_ingestion_service: ConfiguredCsvIngestionService,
    require_unsafe_admin: Callable[[], None],
    to_jsonable: Callable[[Any], Any],
    build_column_mapping_diff: Callable[
        [ColumnMappingRecord, ColumnMappingRecord], dict[str, Any]
    ],
) -> None:
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
        for rule in payload.rules:
            if rule.function_key:
                validate_function_key(
                    rule.function_key,
                    function_registry=function_registry,
                    kind="column_mapping_value",
                )
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
                        function_key=rule.function_key,
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
