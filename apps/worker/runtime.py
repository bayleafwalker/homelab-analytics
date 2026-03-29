from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TextIO

from apps import runtime_support as _runtime_support
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.transformation_domain_registry import TransformationDomainRegistry
from packages.pipelines.transformation_refresh_registry import PublicationRefreshRegistry
from packages.platform.runtime.builder import (
    build_container,
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
    container = build_container(
        settings,
        capability_packs=[FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK],
    )
    return WorkerRuntime(
        container=container,
        output=output,
        error_output=error_output,
        logger=logger,
    )


build_contract_price_service = _runtime_support.build_contract_price_service
build_extension_registry = _runtime_support.build_extension_registry
build_function_registry = _runtime_support.build_function_registry
build_pipeline_registries = _runtime_support.build_pipeline_registries
build_reporting_service = _runtime_support.build_reporting_service
build_service = _runtime_support.build_service
build_subscription_service = _runtime_support.build_subscription_service
build_transformation_service = _runtime_support.build_transformation_service
