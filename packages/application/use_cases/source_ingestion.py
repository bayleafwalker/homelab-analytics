from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from packages.application.use_cases.ingest_promotion import (
    PublishReporting,
    promote_and_publish_configured_csv,
    promote_and_publish_configured_csv_batch,
    promote_and_publish_contract_prices,
    promote_and_publish_subscription,
)
from packages.pipelines.promotion import PromotionResult, promote_run

if TYPE_CHECKING:
    from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
    from packages.domains.finance.pipelines.contract_price_service import ContractPriceService
    from packages.domains.finance.pipelines.subscription_service import SubscriptionService
    from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
    from packages.pipelines.configured_ingestion_definition import (
        ConfiguredIngestionDefinitionService,
        ConfiguredIngestionProcessResult,
    )
    from packages.pipelines.promotion_registry import PromotionHandlerRegistry
    from packages.pipelines.transformation_service import TransformationService
    from packages.shared.extensions import ExtensionRegistry
    from packages.storage.control_plane import ConfigCatalogStore
    from packages.storage.ingestion_config import SourceAssetRecord
    from packages.storage.run_metadata import IngestionRunRecord


def ingest_account_transaction_bytes(
    source_bytes: bytes,
    file_name: str,
    source_name: str,
    *,
    service: "AccountTransactionService",
    transformation_service: "TransformationService | None",
    publish_reporting: PublishReporting,
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    run = service.ingest_bytes(
        source_bytes=source_bytes,
        file_name=file_name,
        source_name=source_name,
    )
    promotion: PromotionResult | None = None
    if transformation_service is not None and run.passed:
        promotion = promote_run(
            run.run_id,
            account_service=service,
            transformation_service=transformation_service,
        )
        publish_reporting(promotion)
    return run, promotion


def ingest_account_transaction_file(
    source_path: Path,
    source_name: str,
    *,
    service: "AccountTransactionService",
    transformation_service: "TransformationService | None",
    publish_reporting: PublishReporting,
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    run = service.ingest_file(source_path, source_name=source_name)
    promotion: PromotionResult | None = None
    if transformation_service is not None and run.passed:
        promotion = promote_run(
            run.run_id,
            account_service=service,
            transformation_service=transformation_service,
        )
        publish_reporting(promotion)
    return run, promotion


def ingest_configured_csv_bytes(
    source_bytes: bytes,
    file_name: str,
    *,
    service: "ConfiguredCsvIngestionService",
    source_system_id: str,
    dataset_contract_id: str,
    column_mapping_id: str,
    source_asset_id: "str | None",
    source_name: str,
    source_asset: "SourceAssetRecord | None",
    config_repository: "ConfigCatalogStore",
    transformation_service: "TransformationService | None",
    registry: "ExtensionRegistry | None",
    promotion_handler_registry: "PromotionHandlerRegistry | None",
    publish_reporting: PublishReporting,
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    run = service.ingest_bytes(
        source_bytes=source_bytes,
        file_name=file_name,
        source_system_id=source_system_id,
        dataset_contract_id=dataset_contract_id,
        column_mapping_id=column_mapping_id,
        source_asset_id=source_asset_id,
        source_name=source_name,
    )
    promotion: PromotionResult | None = None
    if run.passed:
        promotion = promote_and_publish_configured_csv(
            run.run_id,
            source_asset=source_asset,
            config_repository=config_repository,
            service=service,
            transformation_service=transformation_service,
            registry=registry,
            promotion_handler_registry=promotion_handler_registry,
            publish_reporting=publish_reporting,
            source_system_id=source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=column_mapping_id,
        )
    return run, promotion


def ingest_configured_csv_file(
    source_path: Path,
    *,
    service: "ConfiguredCsvIngestionService",
    source_system_id: str,
    dataset_contract_id: str,
    column_mapping_id: str,
    source_asset_id: "str | None",
    source_name: str,
    source_asset: "SourceAssetRecord | None",
    config_repository: "ConfigCatalogStore",
    transformation_service: "TransformationService | None",
    registry: "ExtensionRegistry | None",
    promotion_handler_registry: "PromotionHandlerRegistry | None",
    publish_reporting: PublishReporting,
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    run = service.ingest_file(
        source_path,
        source_system_id=source_system_id,
        dataset_contract_id=dataset_contract_id,
        column_mapping_id=column_mapping_id,
        source_asset_id=source_asset_id,
        source_name=source_name,
    )
    promotion: PromotionResult | None = None
    if run.passed:
        promotion = promote_and_publish_configured_csv(
            run.run_id,
            source_asset=source_asset,
            config_repository=config_repository,
            service=service,
            transformation_service=transformation_service,
            registry=registry,
            promotion_handler_registry=promotion_handler_registry,
            publish_reporting=publish_reporting,
            source_system_id=source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=column_mapping_id,
        )
    return run, promotion


def ingest_subscription_bytes(
    source_bytes: bytes,
    file_name: str,
    source_name: str,
    *,
    subscription_service: "SubscriptionService",
    transformation_service: "TransformationService | None",
    publish_reporting: PublishReporting,
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    run = subscription_service.ingest_bytes(
        source_bytes=source_bytes,
        file_name=file_name,
        source_name=source_name,
    )
    promotion: PromotionResult | None = None
    if run.passed:
        promotion = promote_and_publish_subscription(
            run.run_id,
            subscription_service=subscription_service,
            transformation_service=transformation_service,
            publish_reporting=publish_reporting,
        )
    return run, promotion


def ingest_subscription_file(
    source_path: Path,
    source_name: str,
    *,
    subscription_service: "SubscriptionService",
    transformation_service: "TransformationService | None",
    publish_reporting: PublishReporting,
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    run = subscription_service.ingest_file(source_path, source_name=source_name)
    promotion: PromotionResult | None = None
    if run.passed:
        promotion = promote_and_publish_subscription(
            run.run_id,
            subscription_service=subscription_service,
            transformation_service=transformation_service,
            publish_reporting=publish_reporting,
        )
    return run, promotion


def ingest_contract_prices_bytes(
    source_bytes: bytes,
    file_name: str,
    source_name: str,
    *,
    contract_price_service: "ContractPriceService",
    transformation_service: "TransformationService | None",
    publish_reporting: PublishReporting,
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    run = contract_price_service.ingest_bytes(
        source_bytes=source_bytes,
        file_name=file_name,
        source_name=source_name,
    )
    promotion: PromotionResult | None = None
    if run.passed:
        promotion = promote_and_publish_contract_prices(
            run.run_id,
            contract_price_service=contract_price_service,
            transformation_service=transformation_service,
            publish_reporting=publish_reporting,
        )
    return run, promotion


def ingest_contract_prices_file(
    source_path: Path,
    source_name: str,
    *,
    contract_price_service: "ContractPriceService",
    transformation_service: "TransformationService | None",
    publish_reporting: PublishReporting,
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    run = contract_price_service.ingest_file(source_path, source_name=source_name)
    promotion: PromotionResult | None = None
    if run.passed:
        promotion = promote_and_publish_contract_prices(
            run.run_id,
            contract_price_service=contract_price_service,
            transformation_service=transformation_service,
            publish_reporting=publish_reporting,
        )
    return run, promotion


def process_and_promote_ingestion_definition(
    ingestion_definition_id: str,
    *,
    configured_definition_service: "ConfiguredIngestionDefinitionService",
    configured_ingestion_service: "ConfiguredCsvIngestionService",
    config_repository: "ConfigCatalogStore",
    transformation_service: "TransformationService | None",
    registry: "ExtensionRegistry | None",
    promotion_handler_registry: "PromotionHandlerRegistry | None",
    publish_reporting: PublishReporting,
) -> "tuple[ConfiguredIngestionProcessResult, list[PromotionResult]]":
    result = configured_definition_service.process_ingestion_definition(ingestion_definition_id)
    promotions: list[PromotionResult] = []
    if transformation_service is not None:
        ingestion_definition = config_repository.get_ingestion_definition(ingestion_definition_id)
        source_asset = config_repository.get_source_asset(ingestion_definition.source_asset_id)
        promotions = promote_and_publish_configured_csv_batch(
            result.run_ids,
            source_asset=source_asset,
            config_repository=config_repository,
            service=configured_ingestion_service,
            transformation_service=transformation_service,
            registry=registry,
            promotion_handler_registry=promotion_handler_registry,
            publish_reporting=publish_reporting,
        )
    return result, promotions
