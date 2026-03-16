"""PLT-18: Run promotion orchestration.

Provides a single supported path to promote a successfully landed run from the
landing layer into the transformation (DuckDB) and reporting layers.

Usage::

    from packages.pipelines.promotion import promote_run, PromotionResult

    result = promote_run(
        run_id="run-abc123",
        account_service=...,
        transformation_service=...,
    )
    # result.facts_loaded, result.marts_refreshed
"""

from __future__ import annotations

from dataclasses import replace

from packages.pipelines.builtin_promotion_handlers import (
    promote_contract_price_run,
    promote_run,
    promote_subscription_run,
    promote_utility_bill_run,
    promote_utility_usage_run,
)
from packages.pipelines.promotion_registry import (
    PromotionHandler,
    PromotionHandlerRegistry,
    PromotionRuntime,
    get_default_promotion_handler_registry,
)
from packages.pipelines.promotion_types import PromotionResult
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionRegistry
from packages.storage.blob import BlobStore
from packages.storage.control_plane import ContractCatalogStore
from packages.storage.ingestion_config import SourceAssetRecord
from packages.storage.run_metadata import RunMetadataStore

__all__ = [
    "PromotionResult",
    "get_builtin_promotion_handler",
    "promote_contract_price_run",
    "promote_run",
    "promote_source_asset_run",
    "promote_subscription_run",
    "promote_utility_bill_run",
    "promote_utility_usage_run",
]


def get_builtin_promotion_handler(handler_key: str) -> PromotionHandler:
    return get_default_promotion_handler_registry().get(handler_key)


def promote_source_asset_run(
    run_id: str,
    *,
    source_asset: SourceAssetRecord,
    config_repository: ContractCatalogStore,
    landing_root,
    metadata_repository: RunMetadataStore,
    transformation_service: TransformationService,
    blob_store: BlobStore | None = None,
    extension_registry: ExtensionRegistry | None = None,
    promotion_handler_registry: PromotionHandlerRegistry | None = None,
) -> PromotionResult:
    if source_asset.transformation_package_id is None:
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=[],
            publication_keys=[],
            skipped=True,
            skip_reason="source asset does not define a transformation package",
        )

    transformation_package = config_repository.get_transformation_package(
        source_asset.transformation_package_id
    )
    configured_publications = [
        publication.publication_key
        for publication in config_repository.list_publication_definitions(
            transformation_package_id=transformation_package.transformation_package_id
        )
    ]
    extension_publications = (
        [
            publication.relation_name
            for publication in extension_registry.list_reporting_publications()
        ]
        if extension_registry is not None
        else []
    )
    resolved_promotion_handler_registry = (
        promotion_handler_registry or get_default_promotion_handler_registry()
    )
    handler = resolved_promotion_handler_registry.get(transformation_package.handler_key)
    result = handler.runner(
        PromotionRuntime(
            run_id=run_id,
            landing_root=landing_root,
            metadata_repository=metadata_repository,
            config_repository=config_repository,
            transformation_service=transformation_service,
            blob_store=blob_store,
            extension_registry=extension_registry,
        )
    )
    return _apply_publication_selection(
        result,
        supported_publications=list(handler.supported_publications),
        configured_publications=configured_publications,
        additional_publications=extension_publications,
    )


def _apply_publication_selection(
    result: PromotionResult,
    *,
    supported_publications: list[str],
    configured_publications: list[str],
    additional_publications: list[str] | None = None,
) -> PromotionResult:
    if not configured_publications:
        return replace(result, publication_keys=supported_publications.copy())

    allowed_publications = set(supported_publications)
    if additional_publications:
        allowed_publications.update(additional_publications)

    unsupported = sorted(set(configured_publications) - allowed_publications)
    if unsupported:
        raise ValueError(
            "Configured publication definitions are not supported by the selected transformation package: "
            f"{unsupported}"
        )
    return replace(result, publication_keys=list(configured_publications))
