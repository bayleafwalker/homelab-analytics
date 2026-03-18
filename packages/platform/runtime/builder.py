from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.extension_registries import PipelineRegistries, load_pipeline_registries
from packages.pipelines.pipeline_catalog import sync_pipeline_catalog
from packages.pipelines.subscription_service import SubscriptionService
from packages.platform.auth.configuration import maybe_bootstrap_local_admin
from packages.platform.capability_types import CapabilityPack
from packages.platform.runtime.container import AppContainer
from packages.shared.extensions import ExtensionRegistry, load_extension_registry
from packages.shared.external_registry import (
    ResolvedExtensionSettings,
    resolve_active_extension_settings,
)
from packages.shared.function_registry import FunctionRegistry, load_function_registry
from packages.shared.settings import AppSettings
from packages.storage.control_plane import ControlPlaneStore
from packages.storage.runtime import (
    build_blob_store,
    build_config_store,
    build_run_metadata_store,
)


def _resolve_extension_settings(
    settings: AppSettings,
    *,
    config_repository: ControlPlaneStore | None,
) -> ResolvedExtensionSettings | None:
    """Resolve active extension paths/modules from the control-plane if available.

    Extracted from the 3-times-duplicated pattern in both api/main.py and
    worker/runtime.py.
    """
    if config_repository is None:
        return None
    return resolve_active_extension_settings(
        config_repository,
        configured_paths=settings.extension_paths,
        configured_modules=settings.extension_modules,
    )


def build_extension_registry(
    settings: AppSettings,
    *,
    config_repository: ControlPlaneStore | None = None,
) -> ExtensionRegistry:
    resolved = _resolve_extension_settings(settings, config_repository=config_repository)
    return load_extension_registry(
        extension_paths=(
            resolved.extension_paths if resolved is not None else settings.extension_paths
        ),
        extension_modules=(
            resolved.extension_modules if resolved is not None else settings.extension_modules
        ),
    )


def build_function_registry(
    settings: AppSettings,
    *,
    config_repository: ControlPlaneStore | None = None,
) -> FunctionRegistry:
    resolved = _resolve_extension_settings(settings, config_repository=config_repository)
    return load_function_registry(
        extension_paths=(
            resolved.extension_paths if resolved is not None else settings.extension_paths
        ),
        function_modules=(
            resolved.function_modules if resolved is not None else ()
        ),
    )


def build_pipeline_registries(
    settings: AppSettings,
    *,
    config_repository: ControlPlaneStore | None = None,
) -> PipelineRegistries:
    resolved = _resolve_extension_settings(settings, config_repository=config_repository)
    return load_pipeline_registries(
        extension_paths=(
            resolved.extension_paths if resolved is not None else settings.extension_paths
        ),
        extension_modules=(
            resolved.extension_modules if resolved is not None else settings.extension_modules
        ),
    )


def build_container(
    settings: AppSettings,
    *,
    capability_packs: Sequence[CapabilityPack] = (),
) -> AppContainer:
    """Build the shared platform container used by both API and worker entrypoints.

    This is the single composition root for the application.  Both
    apps/api/main.py and apps/worker/runtime.py call this function and then
    add the adapter-specific wiring (FastAPI app, CLI dispatch loop, etc.) on
    top of the returned container.

    capability_packs: domain packs to register at startup; each is validated
    before the container is assembled.  The first pack (if any) is stored on
    the container as finance_pack for backward-compatible access.
    """
    for pack in capability_packs:
        pack.validate()

    all_pub_keys = [pub.key for pack in capability_packs for pub in pack.publications]
    duplicates = [key for key, count in Counter(all_pub_keys).items() if count > 1]
    if duplicates:
        raise ValueError(
            f"Publication keys owned by multiple capability packs: {duplicates}"
        )

    blob_store = build_blob_store(settings)
    run_metadata_store = build_run_metadata_store(settings)
    control_plane_store = build_config_store(settings)

    extension_registry = build_extension_registry(
        settings, config_repository=control_plane_store
    )
    function_registry = build_function_registry(
        settings, config_repository=control_plane_store
    )
    pipeline_registries = build_pipeline_registries(
        settings, config_repository=control_plane_store
    )

    maybe_bootstrap_local_admin(control_plane_store, settings)
    sync_pipeline_catalog(
        control_plane_store,
        pipeline_registries.pipeline_catalog_registry,
        extension_registry=extension_registry,
        promotion_handler_registry=pipeline_registries.promotion_handler_registry,
    )

    finance_pack = next((p for p in capability_packs if p.name == "finance"), None)

    service = AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=run_metadata_store,
        blob_store=blob_store,
    )

    return AppContainer(
        settings=settings,
        blob_store=blob_store,
        control_plane_store=control_plane_store,
        run_metadata_store=run_metadata_store,
        extension_registry=extension_registry,
        function_registry=function_registry,
        promotion_handler_registry=pipeline_registries.promotion_handler_registry,
        transformation_domain_registry=pipeline_registries.transformation_domain_registry,
        publication_refresh_registry=pipeline_registries.publication_refresh_registry,
        pipeline_catalog_registry=pipeline_registries.pipeline_catalog_registry,
        service=service,
        subscription_service=SubscriptionService(
            landing_root=settings.landing_root,
            metadata_repository=run_metadata_store,
            blob_store=blob_store,
        ),
        contract_price_service=ContractPriceService(
            landing_root=settings.landing_root,
            metadata_repository=run_metadata_store,
            blob_store=blob_store,
        ),
        configured_definition_service=ConfiguredIngestionDefinitionService(
            landing_root=settings.landing_root,
            metadata_repository=run_metadata_store,
            config_repository=control_plane_store,
            blob_store=blob_store,
            function_registry=function_registry,
        ),
        capability_packs=tuple(capability_packs),
        finance_pack=finance_pack,
    )
