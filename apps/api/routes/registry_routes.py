"""Registry config routes: extension registry sources, revisions, activations, introspection."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI

from apps.api.models import (
    ArchivedStateRequest,
    ExtensionRegistryActivationRequest,
    ExtensionRegistrySourceRequest,
    ExtensionRegistrySyncRequest,
)
from packages.pipelines.composition.publication_contract_inputs import (
    HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS,
)
from packages.pipelines.promotion_registry import (
    PromotionHandlerRegistry,
    serialize_promotion_handler_registry,
)
from packages.platform.capability_types import CapabilityPack
from packages.shared.extensions import ExtensionRegistry, serialize_extension_registry
from packages.shared.external_registry import sync_extension_registry_source
from packages.shared.function_registry import FunctionRegistry, serialize_function_registry
from packages.shared.secrets import EnvironmentSecretResolver
from packages.storage.control_plane import ControlPlaneAdminStore
from packages.storage.external_registry_catalog import ExtensionRegistrySourceCreate
from packages.storage.ingestion_catalog import serialize_publication_keys


def register_registry_routes(
    app: FastAPI,
    *,
    registry: ExtensionRegistry,
    function_registry: FunctionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry,
    builtin_packs: Sequence[CapabilityPack],
    resolved_config_repository: ControlPlaneAdminStore,
    external_registry_cache_root: Path,
    require_unsafe_admin: Callable[[], None],
    ensure_matching_identifier: Callable[[str, str, str], None],
    to_jsonable: Callable[[Any], Any],
) -> None:
    @app.get("/extensions")
    async def list_extensions() -> dict[str, Any]:
        require_unsafe_admin()
        return {"extensions": serialize_extension_registry(registry)}

    @app.get("/functions")
    async def list_functions() -> dict[str, Any]:
        require_unsafe_admin()
        return {"functions": serialize_function_registry(function_registry)}

    @app.get("/config/transformation-handlers")
    async def list_transformation_handlers() -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "transformation_handlers": serialize_promotion_handler_registry(
                promotion_handler_registry
            )
        }

    @app.get("/config/publication-keys")
    async def list_publication_keys() -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "publication_keys": serialize_publication_keys(
                extension_registry=registry,
                promotion_handler_registry=promotion_handler_registry,
            )
        }

    @app.get("/config/extension-registry-sources")
    async def list_extension_registry_sources(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "extension_registry_sources": to_jsonable(
                resolved_config_repository.list_extension_registry_sources(
                    include_archived=include_archived
                )
            )
        }

    @app.get("/config/extension-registry-sources/{extension_registry_source_id}")
    async def get_extension_registry_source(
        extension_registry_source_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "extension_registry_source": to_jsonable(
                resolved_config_repository.get_extension_registry_source(
                    extension_registry_source_id
                )
            )
        }

    @app.post("/config/extension-registry-sources", status_code=201)
    async def create_extension_registry_source(
        payload: ExtensionRegistrySourceRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        source = resolved_config_repository.create_extension_registry_source(
            ExtensionRegistrySourceCreate(
                extension_registry_source_id=payload.extension_registry_source_id,
                name=payload.name,
                source_kind=payload.source_kind,
                location=payload.location,
                desired_ref=payload.desired_ref,
                subdirectory=payload.subdirectory,
                auth_secret_name=payload.auth_secret_name,
                auth_secret_key=payload.auth_secret_key,
                enabled=payload.enabled,
            )
        )
        return {"extension_registry_source": to_jsonable(source)}

    @app.patch("/config/extension-registry-sources/{extension_registry_source_id}")
    async def update_extension_registry_source(
        extension_registry_source_id: str,
        payload: ExtensionRegistrySourceRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier(
            "extension_registry_source_id",
            extension_registry_source_id,
            payload.extension_registry_source_id,
        )
        existing = resolved_config_repository.get_extension_registry_source(
            extension_registry_source_id
        )
        source = resolved_config_repository.update_extension_registry_source(
            ExtensionRegistrySourceCreate(
                extension_registry_source_id=payload.extension_registry_source_id,
                name=payload.name,
                source_kind=payload.source_kind,
                location=payload.location,
                desired_ref=payload.desired_ref,
                subdirectory=payload.subdirectory,
                auth_secret_name=payload.auth_secret_name,
                auth_secret_key=payload.auth_secret_key,
                enabled=payload.enabled,
                archived=existing.archived,
                created_at=existing.created_at,
            )
        )
        return {"extension_registry_source": to_jsonable(source)}

    @app.patch(
        "/config/extension-registry-sources/{extension_registry_source_id}/archive"
    )
    async def set_extension_registry_source_archived_state(
        extension_registry_source_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        source = resolved_config_repository.set_extension_registry_source_archived_state(
            extension_registry_source_id,
            archived=payload.archived,
        )
        return {"extension_registry_source": to_jsonable(source)}

    @app.post("/config/extension-registry-sources/{extension_registry_source_id}/sync")
    async def sync_extension_registry_source_route(
        extension_registry_source_id: str,
        payload: ExtensionRegistrySyncRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        result = sync_extension_registry_source(
            resolved_config_repository,
            extension_registry_source_id,
            activate=payload.activate,
            builtin_packs=builtin_packs,
            publication_relations=(
                HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.publication_relations
            ),
            current_dimension_relations=(
                HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.current_dimension_relations
            ),
            current_dimension_contracts=(
                HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.current_dimension_contracts
            ),
            cache_root=external_registry_cache_root,
            secret_resolver=EnvironmentSecretResolver(),
        )
        if not result.passed:
            raise ValueError(
                result.revision.validation_error
                or "External registry sync failed."
            )
        return {
            "extension_registry_source": to_jsonable(result.source),
            "extension_registry_revision": to_jsonable(result.revision),
            "extension_registry_activation": to_jsonable(result.activation),
        }

    @app.post(
        "/config/extension-registry-sources/{extension_registry_source_id}/activate"
    )
    async def activate_extension_registry_source(
        extension_registry_source_id: str,
        payload: ExtensionRegistryActivationRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        activation = resolved_config_repository.activate_extension_registry_revision(
            extension_registry_source_id=extension_registry_source_id,
            extension_registry_revision_id=payload.extension_registry_revision_id,
        )
        return {"extension_registry_activation": to_jsonable(activation)}

    @app.get("/config/extension-registry-revisions")
    async def list_extension_registry_revisions(
        extension_registry_source_id: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "extension_registry_revisions": to_jsonable(
                resolved_config_repository.list_extension_registry_revisions(
                    extension_registry_source_id=extension_registry_source_id
                )
            )
        }

    @app.get("/config/extension-registry-revisions/{extension_registry_revision_id}")
    async def get_extension_registry_revision(
        extension_registry_revision_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "extension_registry_revision": to_jsonable(
                resolved_config_repository.get_extension_registry_revision(
                    extension_registry_revision_id
                )
            )
        }

    @app.get("/config/extension-registry-activations")
    async def list_extension_registry_activations() -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "extension_registry_activations": to_jsonable(
                resolved_config_repository.list_extension_registry_activations()
            )
        }

    @app.get("/control/registry/summary")
    async def get_registry_summary() -> dict[str, Any]:
        # Read-only operator surface — no unsafe_admin required.
        sources = resolved_config_repository.list_extension_registry_sources(
            include_archived=False
        )
        activations = resolved_config_repository.list_extension_registry_activations()
        active_revision: dict[str, Any] | None = None
        if activations:
            latest = max(activations, key=lambda a: a.activated_at)
            revision = resolved_config_repository.get_extension_registry_revision(
                latest.extension_registry_revision_id
            )
            active_revision = {
                "id": revision.extension_registry_revision_id,
                "revision_ref": revision.resolved_ref,
                "activated_at": to_jsonable(latest.activated_at),
            }
        discovered_handlers = [
            handler.handler_key
            for handler in promotion_handler_registry.list()
        ]
        all_extensions = registry.list_extensions()
        publication_keys = [
            pub.relation_name
            for ext in all_extensions
            for pub in ext.publication_relations
        ]
        function_keys = [
            fn.function_key for fn in function_registry.list()
        ]
        return {
            "sources": [
                {
                    "id": s.extension_registry_source_id,
                    "url": s.location,
                    "status": "enabled" if s.enabled else "disabled",
                    "source_created_at": to_jsonable(s.created_at),
                }
                for s in sources
            ],
            "active_revision": active_revision,
            "discovered_handlers": discovered_handlers,
            "publication_keys": publication_keys,
            "function_keys": function_keys,
            "loaded_extension_count": len(all_extensions),
        }
