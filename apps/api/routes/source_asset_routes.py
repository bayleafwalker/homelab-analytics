"""Source asset routes: source assets CRUD, archive, and delete."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI

from apps.api.models import ArchivedStateRequest, SourceAssetRequest
from packages.storage.control_plane import ControlPlaneAdminStore
from packages.storage.ingestion_config import SourceAssetCreate


def register_source_asset_routes(
    app: FastAPI,
    *,
    resolved_config_repository: ControlPlaneAdminStore,
    require_unsafe_admin: Callable[[], None],
    ensure_matching_identifier: Callable[[str, str, str], None],
    to_jsonable: Callable[[Any], Any],
) -> None:
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
