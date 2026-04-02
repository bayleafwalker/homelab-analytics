from __future__ import annotations

from typing import cast

from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.finance.pipelines.contract_price_service import ContractPriceService
from packages.domains.finance.pipelines.subscription_service import SubscriptionService
from packages.pipelines.extension_registries import PipelineRegistries
from packages.pipelines.lazy_transformation_service import LazyTransformationService
from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.pipelines.transformation_domain_registry import TransformationDomainRegistry
from packages.pipelines.transformation_refresh_registry import PublicationRefreshRegistry
from packages.pipelines.transformation_service import TransformationService
from packages.platform.runtime.builder import (
    build_account_transaction_service as _platform_build_service,
)
from packages.platform.runtime.builder import (
    build_container,
)
from packages.platform.runtime.builder import (
    build_contract_price_service as _platform_build_contract_price_service,
)
from packages.platform.runtime.builder import (
    build_extension_registry as _platform_build_extension_registry,
)
from packages.platform.runtime.builder import (
    build_function_registry as _platform_build_function_registry,
)
from packages.platform.runtime.builder import (
    build_pipeline_registries as _platform_build_pipeline_registries,
)
from packages.platform.runtime.builder import (
    build_reporting_service as _platform_build_reporting_service,
)
from packages.platform.runtime.builder import (
    build_subscription_service as _platform_build_subscription_service,
)
from packages.platform.runtime.builder import (
    build_transformation_service as _platform_build_transformation_service,
)
from packages.shared.extensions import ExtensionRegistry
from packages.shared.settings import AppSettings
from packages.storage.control_plane import ControlPlaneStore


def build_extension_registry(
    settings: AppSettings,
    *,
    config_repository=None,
) -> ExtensionRegistry:
    return _platform_build_extension_registry(
        settings,
        config_repository=config_repository,
    )


def build_function_registry(settings: AppSettings, *, config_repository=None):
    return _platform_build_function_registry(
        settings,
        config_repository=config_repository,
    )


def build_pipeline_registries(
    settings: AppSettings,
    *,
    config_repository=None,
) -> PipelineRegistries:
    return _platform_build_pipeline_registries(
        settings,
        config_repository=config_repository,
    )


def build_service(settings: AppSettings) -> AccountTransactionService:
    return _platform_build_service(settings)


def build_subscription_service(settings: AppSettings) -> SubscriptionService:
    return _platform_build_subscription_service(settings)


def build_contract_price_service(settings: AppSettings) -> ContractPriceService:
    return _platform_build_contract_price_service(settings)


def build_transformation_service(
    settings: AppSettings,
    *,
    control_plane_store: ControlPlaneStore | None = None,
    publication_refresh_registry: PublicationRefreshRegistry | None = None,
    domain_registry: TransformationDomainRegistry | None = None,
    container=None,
) -> TransformationService:
    resolved_container = container
    if resolved_container is None and (
        control_plane_store is None
        or publication_refresh_registry is None
        or domain_registry is None
    ):
        resolved_container = build_container(settings)
    if control_plane_store is None:
        control_plane_store = resolved_container.control_plane_store
    if publication_refresh_registry is None:
        publication_refresh_registry = resolved_container.publication_refresh_registry
    if domain_registry is None:
        domain_registry = resolved_container.transformation_domain_registry
    return _platform_build_transformation_service(
        settings,
        control_plane_store=control_plane_store,
        publication_refresh_registry=publication_refresh_registry,
        domain_registry=domain_registry,
    )


def build_lazy_transformation_service(
    settings: AppSettings,
    *,
    container=None,
) -> TransformationService:
    resolved_container = container or build_container(settings)
    return cast(
        TransformationService,
        LazyTransformationService(
            lambda: build_transformation_service(settings, container=resolved_container)
        ),
    )


def build_reporting_service(
    settings: AppSettings,
    transformation_service: TransformationService,
    extension_registry: ExtensionRegistry | None = None,
    control_plane_store=None,
    *,
    access_mode: ReportingAccessMode = ReportingAccessMode.WAREHOUSE,
) -> ReportingService:
    return _platform_build_reporting_service(
        settings,
        transformation_service,
        publication_store=None,
        extension_registry=extension_registry,
        control_plane_store=control_plane_store,
        access_mode=access_mode,
    )
