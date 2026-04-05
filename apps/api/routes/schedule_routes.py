"""Schedule config routes: execution schedules, transformation packages, publication definitions."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI

from apps.api.models import (
    ArchivedStateRequest,
    ExecutionScheduleRequest,
    PublicationDefinitionRequest,
    TransformationPackageRequest,
)
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.shared.extensions import ExtensionRegistry
from packages.storage.control_plane import ControlPlaneAdminStore, ExecutionScheduleCreate
from packages.storage.ingestion_config import (
    PublicationDefinitionCreate,
    TransformationPackageCreate,
)


def register_schedule_routes(
    app: FastAPI,
    *,
    registry: ExtensionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry,
    resolved_config_repository: ControlPlaneAdminStore,
    require_unsafe_admin: Callable[[], None],
    ensure_matching_identifier: Callable[[str, str, str], None],
    to_jsonable: Callable[[Any], Any],
) -> None:
    @app.get("/config/transformation-packages")
    async def list_transformation_packages(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "transformation_packages": to_jsonable(
                resolved_config_repository.list_transformation_packages(
                    include_archived=include_archived
                )
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
            ),
            promotion_handler_registry=promotion_handler_registry,
        )
        return {"transformation_package": to_jsonable(transformation_package)}

    @app.patch("/config/transformation-packages/{transformation_package_id}")
    async def update_transformation_package(
        transformation_package_id: str,
        payload: TransformationPackageRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier(
            "transformation_package_id",
            transformation_package_id,
            payload.transformation_package_id,
        )
        existing = resolved_config_repository.get_transformation_package(
            transformation_package_id
        )
        transformation_package = resolved_config_repository.update_transformation_package(
            TransformationPackageCreate(
                transformation_package_id=payload.transformation_package_id,
                name=payload.name,
                handler_key=payload.handler_key,
                version=payload.version,
                description=payload.description,
                archived=existing.archived,
                created_at=existing.created_at,
            ),
            extension_registry=registry,
            promotion_handler_registry=promotion_handler_registry,
        )
        return {"transformation_package": to_jsonable(transformation_package)}

    @app.patch("/config/transformation-packages/{transformation_package_id}/archive")
    async def set_transformation_package_archived_state(
        transformation_package_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        transformation_package = (
            resolved_config_repository.set_transformation_package_archived_state(
                transformation_package_id,
                archived=payload.archived,
            )
        )
        return {"transformation_package": to_jsonable(transformation_package)}

    @app.get("/config/publication-definitions")
    async def list_publication_definitions(
        transformation_package_id: str | None = None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "publication_definitions": to_jsonable(
                resolved_config_repository.list_publication_definitions(
                    transformation_package_id=transformation_package_id,
                    include_archived=include_archived,
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
            promotion_handler_registry=promotion_handler_registry,
        )
        return {"publication_definition": to_jsonable(publication_definition)}

    @app.patch("/config/publication-definitions/{publication_definition_id}")
    async def update_publication_definition(
        publication_definition_id: str,
        payload: PublicationDefinitionRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier(
            "publication_definition_id",
            publication_definition_id,
            payload.publication_definition_id,
        )
        existing = resolved_config_repository.get_publication_definition(
            publication_definition_id
        )
        publication_definition = resolved_config_repository.update_publication_definition(
            PublicationDefinitionCreate(
                publication_definition_id=payload.publication_definition_id,
                transformation_package_id=payload.transformation_package_id,
                publication_key=payload.publication_key,
                name=payload.name,
                description=payload.description,
                archived=existing.archived,
                created_at=existing.created_at,
            ),
            extension_registry=registry,
            promotion_handler_registry=promotion_handler_registry,
        )
        return {"publication_definition": to_jsonable(publication_definition)}

    @app.patch("/config/publication-definitions/{publication_definition_id}/archive")
    async def set_publication_definition_archived_state(
        publication_definition_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        publication_definition = (
            resolved_config_repository.set_publication_definition_archived_state(
                publication_definition_id,
                archived=payload.archived,
            )
        )
        return {"publication_definition": to_jsonable(publication_definition)}

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
