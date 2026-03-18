from __future__ import annotations

from dataclasses import dataclass

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.pipeline_catalog import PipelineCatalogRegistry
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_domain_registry import TransformationDomainRegistry
from packages.pipelines.transformation_refresh_registry import PublicationRefreshRegistry
from packages.platform.capability_types import CapabilityPack
from packages.shared.extensions import ExtensionRegistry
from packages.shared.function_registry import FunctionRegistry
from packages.shared.settings import AppSettings
from packages.storage.blob import BlobStore
from packages.storage.control_plane import ControlPlaneStore
from packages.storage.run_metadata import RunMetadataStore


@dataclass(frozen=True)
class AppContainer:
    """Shared composition root for API and worker runtimes.

    Both entrypoints build this container via build_container() in
    packages.platform.runtime.builder and then select the capabilities
    they need (API adds auth/web; worker adds CLI dispatch).

    Fields marked "transitional" will migrate into domain capability pack
    registrations once the finance domain pack is introduced (Phase 3).
    """

    settings: AppSettings
    blob_store: BlobStore
    control_plane_store: ControlPlaneStore
    run_metadata_store: RunMetadataStore
    extension_registry: ExtensionRegistry
    function_registry: FunctionRegistry
    promotion_handler_registry: PromotionHandlerRegistry
    transformation_domain_registry: TransformationDomainRegistry
    publication_refresh_registry: PublicationRefreshRegistry
    pipeline_catalog_registry: PipelineCatalogRegistry
    # transitional — will move into finance domain capability pack
    service: AccountTransactionService
    subscription_service: SubscriptionService | None
    contract_price_service: ContractPriceService | None
    configured_definition_service: ConfiguredIngestionDefinitionService
    # finance domain capability pack (validated at build time; None if no packs registered)
    finance_pack: CapabilityPack | None
