from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TextIO

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.extension_registries import (
    PipelineRegistries,
    load_pipeline_registries,
)
from packages.pipelines.pipeline_catalog import sync_pipeline_catalog
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.pipelines.reporting_service import (
    ReportingAccessMode,
    ReportingService,
)
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_domain_registry import (
    TransformationDomainRegistry,
)
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshRegistry,
)
from packages.pipelines.transformation_service import TransformationService
from packages.shared.auth import maybe_bootstrap_local_admin
from packages.shared.external_registry import resolve_active_extension_settings
from packages.shared.extensions import ExtensionRegistry, load_extension_registry
from packages.shared.function_registry import FunctionRegistry, load_function_registry
from packages.shared.settings import AppSettings
from packages.storage.control_plane import ControlPlaneStore
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.runtime import (
    build_blob_store,
    build_config_store,
    build_reporting_store,
    build_run_metadata_store,
)


@dataclass(frozen=True)
class WorkerRuntime:
    settings: AppSettings
    output: TextIO
    error_output: TextIO
    logger: logging.Logger
    service: AccountTransactionService
    config_repository: ControlPlaneStore
    configured_definition_service: ConfiguredIngestionDefinitionService
    extension_registry: ExtensionRegistry
    function_registry: FunctionRegistry
    promotion_handler_registry: PromotionHandlerRegistry
    transformation_domain_registry: TransformationDomainRegistry
    publication_refresh_registry: PublicationRefreshRegistry


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_extension_registry(
    settings: AppSettings,
    *,
    config_repository: ControlPlaneStore | None = None,
) -> ExtensionRegistry:
    resolved_settings = (
        resolve_active_extension_settings(
            config_repository,
            configured_paths=settings.extension_paths,
            configured_modules=settings.extension_modules,
        )
        if config_repository is not None
        else None
    )
    return load_extension_registry(
        extension_paths=(
            resolved_settings.extension_paths
            if resolved_settings is not None
            else settings.extension_paths
        ),
        extension_modules=(
            resolved_settings.extension_modules
            if resolved_settings is not None
            else settings.extension_modules
        ),
    )


def build_pipeline_registries(
    settings: AppSettings,
    *,
    config_repository: ControlPlaneStore | None = None,
) -> PipelineRegistries:
    resolved_settings = (
        resolve_active_extension_settings(
            config_repository,
            configured_paths=settings.extension_paths,
            configured_modules=settings.extension_modules,
        )
        if config_repository is not None
        else None
    )
    return load_pipeline_registries(
        extension_paths=(
            resolved_settings.extension_paths
            if resolved_settings is not None
            else settings.extension_paths
        ),
        extension_modules=(
            resolved_settings.extension_modules
            if resolved_settings is not None
            else settings.extension_modules
        ),
    )


def build_function_registry(
    settings: AppSettings,
    *,
    config_repository: ControlPlaneStore | None = None,
) -> FunctionRegistry:
    resolved_settings = (
        resolve_active_extension_settings(
            config_repository,
            configured_paths=settings.extension_paths,
            configured_modules=settings.extension_modules,
        )
        if config_repository is not None
        else None
    )
    return load_function_registry(
        extension_paths=(
            resolved_settings.extension_paths
            if resolved_settings is not None
            else settings.extension_paths
        ),
        function_modules=(
            resolved_settings.function_modules
            if resolved_settings is not None
            else ()
        ),
    )


def build_config_repository(settings: AppSettings) -> ControlPlaneStore:
    return build_config_store(settings)


def build_transformation_service(
    settings: AppSettings,
    *,
    publication_refresh_registry: PublicationRefreshRegistry | None = None,
    domain_registry: TransformationDomainRegistry | None = None,
) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    return TransformationService(
        DuckDBStore.open(str(analytics_path)),
        control_plane_store=build_config_store(settings),
        publication_refresh_registry=publication_refresh_registry,
        domain_registry=domain_registry,
    )


def build_reporting_service(
    settings: AppSettings,
    transformation_service: TransformationService,
    extension_registry: ExtensionRegistry | None = None,
) -> ReportingService:
    return ReportingService(
        transformation_service,
        publication_store=build_reporting_store(settings),
        extension_registry=extension_registry,
        access_mode=ReportingAccessMode.WAREHOUSE,
        control_plane_store=build_config_store(settings),
    )


def build_subscription_service(settings: AppSettings) -> SubscriptionService:
    return SubscriptionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_contract_price_service(settings: AppSettings) -> ContractPriceService:
    return ContractPriceService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_worker_runtime(
    *,
    settings: AppSettings,
    output: TextIO,
    error_output: TextIO,
    logger: logging.Logger,
) -> WorkerRuntime:
    service = build_service(settings)
    config_repository = build_config_repository(settings)
    extension_registry = build_extension_registry(
        settings,
        config_repository=config_repository,
    )
    function_registry = build_function_registry(
        settings,
        config_repository=config_repository,
    )
    pipeline_registries = build_pipeline_registries(
        settings,
        config_repository=config_repository,
    )
    maybe_bootstrap_local_admin(config_repository, settings)
    sync_pipeline_catalog(
        config_repository,
        pipeline_registries.pipeline_catalog_registry,
        extension_registry=extension_registry,
        promotion_handler_registry=pipeline_registries.promotion_handler_registry,
    )
    return WorkerRuntime(
        settings=settings,
        output=output,
        error_output=error_output,
        logger=logger,
        service=service,
        config_repository=config_repository,
        configured_definition_service=ConfiguredIngestionDefinitionService(
            landing_root=settings.landing_root,
            metadata_repository=service.metadata_repository,
            config_repository=config_repository,
            blob_store=service.blob_store,
            function_registry=function_registry,
        ),
        extension_registry=extension_registry,
        function_registry=function_registry,
        promotion_handler_registry=pipeline_registries.promotion_handler_registry,
        transformation_domain_registry=pipeline_registries.transformation_domain_registry,
        publication_refresh_registry=pipeline_registries.publication_refresh_registry,
    )
