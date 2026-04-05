"""Config routes coordinator — delegates to source, schedule, and registry sub-modules."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI

from apps.api.routes.registry_routes import register_registry_routes
from apps.api.routes.schedule_routes import register_schedule_routes
from apps.api.routes.source_routes import register_source_routes
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.platform.capability_types import CapabilityPack
from packages.shared.extensions import ExtensionRegistry
from packages.shared.function_registry import FunctionRegistry
from packages.storage.control_plane import ControlPlaneAdminStore
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
)


def register_config_routes(
    app: FastAPI,
    *,
    registry: ExtensionRegistry,
    function_registry: FunctionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry,
    builtin_packs: Sequence[CapabilityPack],
    resolved_config_repository: ControlPlaneAdminStore,
    external_registry_cache_root: Path,
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
    register_source_routes(
        app,
        function_registry=function_registry,
        resolved_config_repository=resolved_config_repository,
        configured_ingestion_service=configured_ingestion_service,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=to_jsonable,
        build_dataset_contract_diff=build_dataset_contract_diff,
        build_column_mapping_diff=build_column_mapping_diff,
    )
    register_schedule_routes(
        app,
        registry=registry,
        promotion_handler_registry=promotion_handler_registry,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=to_jsonable,
    )
    register_registry_routes(
        app,
        registry=registry,
        function_registry=function_registry,
        promotion_handler_registry=promotion_handler_registry,
        builtin_packs=builtin_packs,
        resolved_config_repository=resolved_config_repository,
        external_registry_cache_root=external_registry_cache_root,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=to_jsonable,
    )
