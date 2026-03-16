from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.pipelines.builtin_promotion_handlers import (
    register_builtin_promotion_handlers,
)
from packages.pipelines.builtin_transformation_refresh import (
    register_builtin_publication_refresh_handlers,
)
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshRegistry,
)
from packages.shared.extensions import load_extension_modules


@dataclass(frozen=True)
class PipelineRegistries:
    promotion_handler_registry: PromotionHandlerRegistry
    publication_refresh_registry: PublicationRefreshRegistry


def build_builtin_pipeline_registries() -> PipelineRegistries:
    promotion_handler_registry = PromotionHandlerRegistry()
    publication_refresh_registry = PublicationRefreshRegistry()
    register_builtin_promotion_handlers(promotion_handler_registry)
    register_builtin_publication_refresh_handlers(publication_refresh_registry)
    return PipelineRegistries(
        promotion_handler_registry=promotion_handler_registry,
        publication_refresh_registry=publication_refresh_registry,
    )


def load_pipeline_registries(
    *,
    extension_paths: tuple[Path, ...] = (),
    extension_modules: tuple[str, ...] = (),
) -> PipelineRegistries:
    registries = build_builtin_pipeline_registries()
    loaded_modules = load_extension_modules(
        extension_paths=extension_paths,
        extension_modules=extension_modules,
    )

    for module_name, module in zip(extension_modules, loaded_modules, strict=True):
        register_pipeline_registries = getattr(
            module,
            "register_pipeline_registries",
            None,
        )
        if register_pipeline_registries is None:
            continue
        if not callable(register_pipeline_registries):
            raise ValueError(
                "Extension module "
                f"{module_name!r} defines register_pipeline_registries but it is not callable."
            )
        register_pipeline_registries(
            promotion_handler_registry=registries.promotion_handler_registry,
            publication_refresh_registry=registries.publication_refresh_registry,
        )

    return registries
