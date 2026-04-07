from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from packages.pipelines.promotion import (
    PromotionResult,
    promote_contract_price_run,
    promote_source_asset_run,
    promote_subscription_run,
)

if TYPE_CHECKING:
    from packages.domains.finance.pipelines.contract_price_service import ContractPriceService
    from packages.domains.finance.pipelines.subscription_service import SubscriptionService
    from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
    from packages.pipelines.promotion_registry import PromotionHandlerRegistry
    from packages.pipelines.transformation_service import TransformationService
    from packages.shared.extensions import ExtensionRegistry
    from packages.storage.control_plane import ConfigCatalogStore
    from packages.storage.ingestion_config import SourceAssetRecord

PublishReporting = Callable[[PromotionResult | None], None]


def promote_and_publish_configured_csv(
    run_id: str,
    *,
    source_asset: "SourceAssetRecord | None",
    config_repository: "ConfigCatalogStore",
    service: "ConfiguredCsvIngestionService",
    transformation_service: "TransformationService | None",
    registry: "ExtensionRegistry | None",
    promotion_handler_registry: "PromotionHandlerRegistry | None",
    publish_reporting: PublishReporting,
    source_system_id: str | None = None,
    dataset_contract_id: str | None = None,
    column_mapping_id: str | None = None,
) -> "PromotionResult | None":
    """Promote a successful configured-CSV run and publish reporting.

    Extracted from apps/api/routes/ingest_routes.py so that route handlers
    delegate workflow order to the application layer rather than encoding it
    inline.
    """
    if transformation_service is None:
        return None
    resolved_source_asset = source_asset
    if (
        resolved_source_asset is None
        and source_system_id
        and dataset_contract_id
        and column_mapping_id
    ):
        resolved_source_asset = config_repository.find_source_asset_by_binding(
            source_system_id=source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=column_mapping_id,
        )
    if resolved_source_asset is None:
        return None
    promotion = promote_source_asset_run(
        run_id,
        source_asset=resolved_source_asset,
        config_repository=config_repository,
        landing_root=service.landing_root,
        metadata_repository=service.metadata_repository,
        transformation_service=transformation_service,
        blob_store=service.blob_store,
        extension_registry=registry,
        promotion_handler_registry=promotion_handler_registry,
    )
    publish_reporting(promotion)
    return promotion


def promote_and_publish_subscription(
    run_id: str,
    *,
    subscription_service: "SubscriptionService",
    transformation_service: "TransformationService | None",
    publish_reporting: PublishReporting,
) -> "PromotionResult | None":
    """Promote a successful subscription run and publish reporting."""
    if transformation_service is None:
        return None
    promotion = promote_subscription_run(
        run_id,
        subscription_service=subscription_service,
        transformation_service=transformation_service,
    )
    publish_reporting(promotion)
    return promotion


def promote_and_publish_configured_csv_batch(
    run_ids: Sequence[str],
    *,
    source_asset: "SourceAssetRecord",
    config_repository: "ConfigCatalogStore",
    service: "ConfiguredCsvIngestionService",
    transformation_service: "TransformationService | None",
    registry: "ExtensionRegistry | None",
    promotion_handler_registry: "PromotionHandlerRegistry | None",
    publish_reporting: PublishReporting,
) -> "list[PromotionResult]":
    """Promote and publish a batch of configured-CSV runs for one source asset.

    Used by the ingestion-definition batch processing handler.
    """
    if transformation_service is None:
        return []
    promotions = [
        promote_source_asset_run(
            run_id,
            source_asset=source_asset,
            config_repository=config_repository,
            landing_root=service.landing_root,
            metadata_repository=service.metadata_repository,
            transformation_service=transformation_service,
            blob_store=service.blob_store,
            extension_registry=registry,
            promotion_handler_registry=promotion_handler_registry,
        )
        for run_id in run_ids
    ]
    for promotion in promotions:
        publish_reporting(promotion)
    return promotions


def promote_and_publish_contract_prices(
    run_id: str,
    *,
    contract_price_service: "ContractPriceService",
    transformation_service: "TransformationService | None",
    publish_reporting: PublishReporting,
) -> "PromotionResult | None":
    """Promote a successful contract-price run and publish reporting."""
    if transformation_service is None:
        return None
    promotion = promote_contract_price_run(
        run_id,
        contract_price_service=contract_price_service,
        transformation_service=transformation_service,
    )
    publish_reporting(promotion)
    return promotion
