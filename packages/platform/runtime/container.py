from __future__ import annotations

from dataclasses import dataclass

from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.pipeline_catalog import PipelineCatalogRegistry
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
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

    Domain-specific services are intentionally composed by app entrypoints
    (API, worker, demo tooling) instead of being stored as typed fields on
    the platform container.
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
    configured_definition_service: ConfiguredIngestionDefinitionService
    # all registered capability packs (validated at build time)
    capability_packs: tuple[CapabilityPack, ...] = ()
