"""Source config routes coordinator — delegates to focused sub-modules by resource family."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI

from apps.api.routes.source_asset_routes import register_source_asset_routes
from apps.api.routes.source_contract_routes import register_source_contract_routes
from apps.api.routes.source_ingestion_routes import register_source_ingestion_routes
from apps.api.routes.source_mapping_routes import register_source_mapping_routes
from apps.api.routes.source_system_routes import register_source_system_routes
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.shared.function_registry import FunctionRegistry
from packages.storage.control_plane import ControlPlaneAdminStore
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
)


def register_source_routes(
    app: FastAPI,
    *,
    function_registry: FunctionRegistry,
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
    register_source_system_routes(
        app,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=to_jsonable,
    )
    register_source_contract_routes(
        app,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        to_jsonable=to_jsonable,
        build_dataset_contract_diff=build_dataset_contract_diff,
    )
    register_source_mapping_routes(
        app,
        function_registry=function_registry,
        resolved_config_repository=resolved_config_repository,
        configured_ingestion_service=configured_ingestion_service,
        require_unsafe_admin=require_unsafe_admin,
        to_jsonable=to_jsonable,
        build_column_mapping_diff=build_column_mapping_diff,
    )
    register_source_asset_routes(
        app,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=to_jsonable,
    )
    register_source_ingestion_routes(
        app,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=to_jsonable,
    )
