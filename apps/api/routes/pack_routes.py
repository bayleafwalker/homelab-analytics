"""Pack lifecycle routes: the operator surface over cached registry packs.

    GET  /control/packs                      catalog with compatibility badges
    GET  /control/packs/history              append-only lifecycle history
    POST /control/packs/{pack_key}/plan      dry-run plan (writes nothing)
    POST /control/packs/{pack_key}/actions   apply install/upgrade/rollback/
                                             disable/enable/pin/unpin with a reason

Every route sits under the admin-only ``/control/`` policy (``admin.write``,
``admin.write`` service-token scope). Nothing here syncs a registry source
or fetches code: the catalog is built from revisions an earlier sync already
validated and cached locally. Refused changes return 409 with the plan and
are recorded in the history like applied ones.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from packages.application.use_cases.pack_lifecycle import (
    MAX_REASON_LENGTH,
    PackChangeRefusedError,
    PackLifecycleContext,
    PackLifecycleValidationError,
    actor_from_principal,
    apply_pack_change,
    build_pack_catalog,
    build_pack_lifecycle_context,
    serialize_event,
    serialize_installation,
)
from packages.platform.capability_types import CapabilityPack
from packages.storage.control_plane import ExternalRegistryStore
from packages.storage.pack_lifecycle import PackLifecycleConflictError, PackLifecycleStore

PackAction = Literal["install", "upgrade", "rollback", "disable", "enable", "pin", "unpin"]


class PackDiagnosticModel(BaseModel):
    code: str
    severity: Literal["blocking", "warning"]
    message: str
    publication_key: str | None = None
    pack_key: str | None = None


class PackPublicationChangeModel(BaseModel):
    publication_key: str
    change: Literal["added", "removed", "schema_changed", "unchanged"]
    from_schema_version: str | None
    to_schema_version: str | None
    breaking: bool
    dependents: list[str]


class PackPlanSourceModel(BaseModel):
    extension_registry_source_id: str
    source_name: str
    extension_registry_revision_id: str
    entry_digest: str


class PackPlanModel(BaseModel):
    pack_key: str
    action: str
    from_version: str | None
    to_version: str | None
    from_enabled: bool | None
    to_enabled: bool | None
    allowed: bool
    compatibility_status: Literal["compatible", "warning", "incompatible"]
    platform_version: str
    checked_at: str
    source: PackPlanSourceModel | None
    diagnostics: list[PackDiagnosticModel]
    publication_changes: list[PackPublicationChangeModel]
    contracts_affected: list[str]


class PackCompatibilitySnapshotModel(BaseModel):
    status: Literal["compatible", "warning", "incompatible"]
    platform_version: str
    checked_at: str
    issues: list[str]
    warnings: list[str]


class PackInstallationModel(BaseModel):
    installed_version: str
    previous_version: str | None
    pinned_version: str | None
    enabled: bool
    state: Literal["enabled", "disabled"]
    extension_registry_source_id: str
    extension_registry_revision_id: str
    entry_digest: str
    available_versions: list[str]
    compatibility_snapshot: PackCompatibilitySnapshotModel
    installed_at: str
    updated_at: str


class PackInstallationRecordModel(PackInstallationModel):
    pack_key: str


class PackPublicationContractModel(BaseModel):
    publication_key: str
    schema_version: str


class PackVersionModel(BaseModel):
    version: str
    relation: Literal["available", "installed", "upgrade", "rollback", "older"]
    compatibility_status: Literal["compatible", "warning", "incompatible"]
    issues: list[str]
    warnings: list[str]
    requires_platform_version: str
    dependencies: list[str]
    publications: list[PackPublicationContractModel]
    requires_publications: list[str]
    extension_registry_source_id: str
    source_name: str
    extension_registry_revision_id: str
    entry_digest: str


class PackCatalogItemModel(BaseModel):
    pack_key: str
    display_name: str
    pack_kind: str
    trust_level: str
    description: str
    state: Literal["not_installed", "enabled", "disabled"]
    installation: PackInstallationModel | None
    latest_version: str | None
    upgrade_available: bool
    installed_version_cached: bool
    versions: list[PackVersionModel]


class PlatformPackModel(BaseModel):
    name: str
    version: str
    publication_count: int


class PackRegistrySummaryModel(BaseModel):
    sources_scanned: int
    revisions_scanned: int
    entries: int
    errors: list[str]


class PackCatalogModel(BaseModel):
    platform_version: str
    packs: list[PackCatalogItemModel]
    platform_packs: list[PlatformPackModel]
    registry: PackRegistrySummaryModel


class PackLifecycleEventModel(BaseModel):
    event_id: str
    pack_key: str
    action: str
    outcome: Literal["applied", "refused"]
    from_version: str | None
    to_version: str | None
    reason: str
    extension_registry_source_id: str | None
    extension_registry_revision_id: str | None
    entry_digest: str | None
    compatibility_snapshot: PackCompatibilitySnapshotModel
    plan: PackPlanModel
    actor: str
    actor_role: str | None
    actor_auth_provider: str
    actor_authenticated: bool
    occurred_at: str


class PackHistoryModel(BaseModel):
    events: list[PackLifecycleEventModel]


class PackPlanRequest(BaseModel):
    model_config = {"extra": "forbid"}

    action: PackAction
    version: str | None = Field(
        default=None,
        description="Target version for install/upgrade; defaults to the newest cached version.",
    )


class PackActionRequest(PackPlanRequest):
    reason: str = Field(
        min_length=1,
        max_length=MAX_REASON_LENGTH,
        description="Why the operator is making this change; stored in the history.",
    )


class PackActionResultModel(BaseModel):
    plan: PackPlanModel
    event: PackLifecycleEventModel
    installation: PackInstallationRecordModel


def register_pack_routes(
    app: FastAPI,
    *,
    resolved_config_repository: object,
    capability_packs: Sequence[CapabilityPack],
    platform_version: str,
) -> None:
    def _context() -> PackLifecycleContext:
        if not isinstance(resolved_config_repository, PackLifecycleStore) or not isinstance(
            resolved_config_repository, ExternalRegistryStore
        ):
            raise HTTPException(
                status_code=404, detail="The control plane has no pack lifecycle store."
            )
        return build_pack_lifecycle_context(
            resolved_config_repository,
            platform_packs=tuple(capability_packs),
            platform_version=platform_version,
        )

    @app.get("/control/packs", response_model=PackCatalogModel)
    async def list_pack_catalog() -> dict[str, Any]:
        return build_pack_catalog(_context())

    @app.get("/control/packs/history", response_model=PackHistoryModel)
    async def list_pack_history(
        pack_key: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        context = _context()
        events = context.store.list_pack_lifecycle_events(pack_key=pack_key, limit=limit)
        return {"events": [serialize_event(event) for event in events]}

    @app.post("/control/packs/{pack_key}/plan", response_model=PackPlanModel)
    async def plan_pack_lifecycle_change(pack_key: str, body: PackPlanRequest) -> dict[str, Any]:
        try:
            result = apply_pack_change(
                _context(),
                pack_key=pack_key,
                action=body.action,
                version=body.version,
                reason="",
                actor=actor_from_principal(None),
                dry_run=True,
            )
        except PackLifecycleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.plan.to_dict()

    @app.post("/control/packs/{pack_key}/actions", response_model=PackActionResultModel)
    async def apply_pack_lifecycle_change(
        pack_key: str, body: PackActionRequest, request: Request
    ) -> dict[str, Any]:
        principal = cast(Any, getattr(request.state, "principal", None))
        try:
            result = apply_pack_change(
                _context(),
                pack_key=pack_key,
                action=body.action,
                version=body.version,
                reason=body.reason,
                actor=actor_from_principal(principal),
            )
        except PackLifecycleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except PackChangeRefusedError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "event_id": exc.event.event_id,
                    "plan": exc.plan.to_dict(),
                },
            ) from exc
        except PackLifecycleConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"message": f"{exc} Reload the catalog and plan again."},
            ) from exc
        assert result.event is not None and result.installation is not None
        return {
            "plan": result.plan.to_dict(),
            "event": serialize_event(result.event),
            "installation": serialize_installation(result.installation),
        }
