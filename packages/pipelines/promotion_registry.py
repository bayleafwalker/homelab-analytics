from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from packages.pipelines.promotion_types import PromotionResult
from packages.shared.extensions import ExtensionRegistry
from packages.storage.blob import BlobStore
from packages.storage.control_plane import ContractCatalogStore
from packages.storage.run_metadata import RunMetadataStore

if TYPE_CHECKING:
    from packages.pipelines.transformation_service import TransformationService


PromotionRunner = Callable[["PromotionRuntime"], PromotionResult]


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
class PromotionHandler:
    handler_key: str
    default_publications: tuple[str, ...]
    supported_publications: tuple[str, ...]
    runner: PromotionRunner


class PromotionHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, PromotionHandler] = {}

    def register(self, handler: PromotionHandler) -> None:
        existing = self._handlers.get(handler.handler_key)
        if existing is not None and existing != handler:
            raise ValueError(f"Promotion handler already registered: {handler.handler_key}")
        self._handlers[handler.handler_key] = handler

    def get(self, handler_key: str) -> PromotionHandler:
        try:
            return self._handlers[handler_key]
        except KeyError as exc:
            raise ValueError(f"Unsupported transformation package handler: {handler_key}") from exc

    def list(self) -> list[PromotionHandler]:
        return [self._handlers[handler_key] for handler_key in sorted(self._handlers)]


_DEFAULT_PROMOTION_HANDLER_REGISTRY: PromotionHandlerRegistry | None = None


def get_default_promotion_handler_registry() -> PromotionHandlerRegistry:
    global _DEFAULT_PROMOTION_HANDLER_REGISTRY
    if _DEFAULT_PROMOTION_HANDLER_REGISTRY is None:
        from packages.pipelines.builtin_promotion_handlers import (
            register_builtin_promotion_handlers,
        )

        registry = PromotionHandlerRegistry()
        register_builtin_promotion_handlers(registry)
        _DEFAULT_PROMOTION_HANDLER_REGISTRY = registry
    return _DEFAULT_PROMOTION_HANDLER_REGISTRY
