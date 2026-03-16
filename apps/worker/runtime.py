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
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.pipelines.reporting_service import (
    ReportingAccessMode,
    ReportingService,
)
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshRegistry,
)
from packages.pipelines.transformation_service import TransformationService
from packages.shared.auth import maybe_bootstrap_local_admin
from packages.shared.extensions import ExtensionRegistry, load_extension_registry
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
    promotion_handler_registry: PromotionHandlerRegistry
    publication_refresh_registry: PublicationRefreshRegistry


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_extension_registry(settings: AppSettings) -> ExtensionRegistry:
    return load_extension_registry(
        extension_paths=settings.extension_paths,
        extension_modules=settings.extension_modules,
    )


def build_pipeline_registries(settings: AppSettings) -> PipelineRegistries:
    return load_pipeline_registries(
        extension_paths=settings.extension_paths,
        extension_modules=settings.extension_modules,
    )


def build_config_repository(settings: AppSettings) -> ControlPlaneStore:
    return build_config_store(settings)


def build_transformation_service(
    settings: AppSettings,
    *,
    publication_refresh_registry: PublicationRefreshRegistry | None = None,
) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    return TransformationService(
        DuckDBStore.open(str(analytics_path)),
        control_plane_store=build_config_store(settings),
        publication_refresh_registry=publication_refresh_registry,
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
    extension_registry = build_extension_registry(settings)
    pipeline_registries = build_pipeline_registries(settings)
    maybe_bootstrap_local_admin(config_repository, settings)
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
        ),
        extension_registry=extension_registry,
        promotion_handler_registry=pipeline_registries.promotion_handler_registry,
        publication_refresh_registry=pipeline_registries.publication_refresh_registry,
    )
