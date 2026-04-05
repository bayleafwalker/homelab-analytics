"""Source system routes: source systems CRUD and combined sources listing."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI

from apps.api.models import SourceSystemRequest
from packages.storage.control_plane import ControlPlaneAdminStore
from packages.storage.ingestion_config import SourceSystemCreate


def register_source_system_routes(
    app: FastAPI,
    *,
    resolved_config_repository: ControlPlaneAdminStore,
    require_unsafe_admin: Callable[[], None],
    ensure_matching_identifier: Callable[[str, str, str], None],
    to_jsonable: Callable[[Any], Any],
) -> None:
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
