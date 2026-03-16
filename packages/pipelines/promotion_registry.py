from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from packages.pipelines.builtin_packages import BuiltinTransformationPackageSpec
from packages.shared.extensions import ExtensionRegistry
from packages.storage.blob import BlobStore
from packages.storage.control_plane import ContractCatalogStore
from packages.storage.run_metadata import RunMetadataStore

if TYPE_CHECKING:
    from packages.pipelines.promotion import PromotionResult
    from packages.pipelines.transformation_service import TransformationService


@dataclass(frozen=True)
class PromotionRuntime:
    run_id: str
    landing_root: Path
    metadata_repository: RunMetadataStore
    config_repository: ContractCatalogStore
    transformation_service: TransformationService
    blob_store: BlobStore | None = None
    extension_registry: ExtensionRegistry | None = None


@dataclass(frozen=True)
class BuiltinPromotionHandler:
    package_spec: BuiltinTransformationPackageSpec
    runner: Callable[[PromotionRuntime], PromotionResult]

    @property
    def handler_key(self) -> str:
        return self.package_spec.handler_key

    @property
    def default_publications(self) -> tuple[str, ...]:
        return self.package_spec.publication_keys

    @property
    def supported_publications(self) -> tuple[str, ...]:
        return self.package_spec.publication_keys
