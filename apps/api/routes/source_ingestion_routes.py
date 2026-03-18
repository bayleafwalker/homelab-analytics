"""Source ingestion routes: ingestion definitions CRUD, archive, and delete."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI

from apps.api.models import ArchivedStateRequest, IngestionDefinitionRequest
from packages.storage.control_plane import ControlPlaneAdminStore
from packages.storage.ingestion_config import (
    IngestionDefinitionCreate,
    RequestHeaderSecretRef,
)


def register_source_ingestion_routes(
    app: FastAPI,
    *,
    resolved_config_repository: ControlPlaneAdminStore,
    require_unsafe_admin: Callable[[], None],
    ensure_matching_identifier: Callable[[str, str, str], None],
    to_jsonable: Callable[[Any], Any],
) -> None:
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
