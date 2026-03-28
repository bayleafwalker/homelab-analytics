from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TextIO

from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.extension_registries import PipelineRegistries
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
from packages.platform.runtime.container import AppContainer
from packages.shared.extensions import ExtensionRegistry
from packages.shared.settings import AppSettings


@dataclass(frozen=True)
class WorkerRuntime:
    """Thin wrapper around AppContainer for the worker CLI dispatch loop.

    Carries the I/O streams the CLI needs alongside the shared container.
    Behaviour is otherwise identical to the previous stand-alone builder —
    both now call the same build_container() composition root.
    """

    container: AppContainer
    output: TextIO
    error_output: TextIO
    logger: logging.Logger

    # Convenience pass-throughs so existing command_handlers code keeps working
    # without touching every call-site in this PR.
    @property
    def settings(self) -> AppSettings:
        return self.container.settings

    @property
    def service(self) -> AccountTransactionService:
        return self.container.service

    @property
    def config_repository(self):  # type: ignore[return]
        return self.container.control_plane_store

    @property
    def configured_definition_service(self):  # type: ignore[return]
        return self.container.configured_definition_service

    @property
    def extension_registry(self) -> ExtensionRegistry:
        return self.container.extension_registry

    @property
    def function_registry(self):  # type: ignore[return]
        return self.container.function_registry

    @property
    def promotion_handler_registry(self):  # type: ignore[return]
        return self.container.promotion_handler_registry

    @property
    def transformation_domain_registry(self) -> TransformationDomainRegistry:
        return self.container.transformation_domain_registry

    @property
    def publication_refresh_registry(self) -> PublicationRefreshRegistry:
        return self.container.publication_refresh_registry


def build_worker_runtime(
    *,
    settings: AppSettings,
    output: TextIO,
    error_output: TextIO,
    logger: logging.Logger,
) -> WorkerRuntime:
    """Build the worker runtime via the shared platform container."""
    container = build_container(settings, capability_packs=[FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK])
    return WorkerRuntime(
        container=container,
        output=output,
        error_output=error_output,
        logger=logger,
    )


# ---------------------------------------------------------------------------
# Builder helpers — used by command_handlers.py, control_plane.py, main.py.
# These build on-demand services for specific worker commands.  They are
# wrappers around platform builder functions or direct storage factories.
# ---------------------------------------------------------------------------


def build_service(settings: AppSettings) -> AccountTransactionService:
    return _platform_build_service(settings)


def build_subscription_service(settings: AppSettings):
    return _platform_build_subscription_service(settings)


def build_contract_price_service(settings: AppSettings):
    return _platform_build_contract_price_service(settings)


def build_extension_registry(
    settings: AppSettings,
    *,
    config_repository=None,
) -> ExtensionRegistry:
    return _platform_build_extension_registry(settings, config_repository=config_repository)


def build_pipeline_registries(
    settings: AppSettings,
    *,
    config_repository=None,
) -> PipelineRegistries:
    return _platform_build_pipeline_registries(settings, config_repository=config_repository)


def build_transformation_service(
    settings: AppSettings,
    *,
    publication_refresh_registry: PublicationRefreshRegistry | None = None,
    domain_registry: TransformationDomainRegistry | None = None,
) -> TransformationService:
    return _platform_build_transformation_service(
        settings,
        publication_refresh_registry=publication_refresh_registry,
        domain_registry=domain_registry,
    )


def build_reporting_service(
    settings: AppSettings,
    transformation_service: TransformationService,
    extension_registry: ExtensionRegistry | None = None,
) -> ReportingService:
    return _platform_build_reporting_service(
        settings,
        transformation_service,
        extension_registry=extension_registry,
        access_mode=ReportingAccessMode.WAREHOUSE,
    )
