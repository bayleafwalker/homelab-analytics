from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TYPE_CHECKING

from packages.application.use_cases.run_recovery import build_run_recovery
from packages.application.use_cases.source_ingestion import (
    ingest_account_transaction_bytes,
    ingest_configured_csv_bytes,
    ingest_contract_prices_bytes,
    ingest_subscription_bytes,
)
from packages.pipelines.promotion import PromotionResult
from packages.pipelines.run_context import read_run_manifest, run_context_from_manifest

if TYPE_CHECKING:
    from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
    from packages.domains.finance.pipelines.contract_price_service import ContractPriceService
    from packages.domains.finance.pipelines.subscription_service import SubscriptionService
    from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
    from packages.pipelines.promotion_registry import PromotionHandlerRegistry
    from packages.pipelines.run_context import RunControlContext
    from packages.pipelines.transformation_service import TransformationService
    from packages.shared.extensions import ExtensionRegistry
    from packages.storage.blob import BlobStore
    from packages.storage.control_plane import ConfigCatalogStore
    from packages.storage.ingestion_config import SourceAssetRecord
    from packages.storage.run_metadata import IngestionRunRecord


def load_run_manifest_and_context(
    run: "IngestionRunRecord",
    *,
    blob_store: "BlobStore",
    logger: logging.Logger | None = None,
) -> "tuple[dict[str, Any] | None, RunControlContext | None]":
    """Load a run's manifest from blob storage and parse its control context."""
    try:
        manifest = read_run_manifest(blob_store, run.manifest_path)
    except (KeyError, OSError, ValueError) as exc:
        if logger is not None:
            logger.warning(
                "run manifest unavailable",
                extra={
                    "run_id": run.run_id,
                    "manifest_path": run.manifest_path,
                    "error": str(exc),
                },
            )
        return None, None
    return manifest, run_context_from_manifest(manifest)


def build_run_detail(
    run: "IngestionRunRecord",
    *,
    blob_store: "BlobStore",
    has_subscription_service: bool,
    has_contract_price_service: bool,
    serialize_run_fn: "Callable[..., dict[str, Any]]",
    build_run_remediation_fn: "Callable[..., dict[str, str]]",
    logger: logging.Logger | None = None,
) -> "dict[str, Any]":
    """Build the detailed run payload including context, recovery, and remediation."""
    _, context = load_run_manifest_and_context(run, blob_store=blob_store, logger=logger)
    recovery = build_run_recovery(
        run,
        context,
        has_subscription_service=has_subscription_service,
        has_contract_price_service=has_contract_price_service,
    )
    has_binding = context is not None and (
        context.source_asset_id is not None
        or (
            context.source_system_id is not None
            and context.dataset_contract_id is not None
            and context.column_mapping_id is not None
        )
    )
    return serialize_run_fn(
        run,
        context=context,
        recovery=recovery,
        remediation=build_run_remediation_fn(
            run,
            recovery=recovery,
            has_source_asset_binding=has_binding,
        ),
    )


def retry_ingest_run(
    original_run: "IngestionRunRecord",
    retry_kind: str,
    source_bytes: bytes,
    retry_context: "RunControlContext",
    *,
    service: "AccountTransactionService",
    configured_ingestion_service: "ConfiguredCsvIngestionService | None" = None,
    subscription_service: "SubscriptionService | None" = None,
    contract_price_service: "ContractPriceService | None" = None,
    config_repository: "ConfigCatalogStore | None" = None,
    source_asset: "SourceAssetRecord | None" = None,
    transformation_service: "TransformationService | None",
    registry: "ExtensionRegistry | None" = None,
    promotion_handler_registry: "PromotionHandlerRegistry | None" = None,
    publish_reporting: "Callable[[PromotionResult | None], None]",
) -> "tuple[IngestionRunRecord, PromotionResult | None]":
    """Orchestrate a retry ingest+promote for the given retry_kind.

    Validation (archived source asset, missing binding context) stays in the
    route layer. Raises ValueError for an unrecognised retry_kind.
    """
    if retry_kind == "configured_csv":
        assert configured_ingestion_service is not None and config_repository is not None
        return ingest_configured_csv_bytes(
            source_bytes,
            original_run.file_name,
            service=configured_ingestion_service,
            source_system_id=retry_context.source_system_id,  # type: ignore[arg-type]
            dataset_contract_id=retry_context.dataset_contract_id,  # type: ignore[arg-type]
            column_mapping_id=retry_context.column_mapping_id,  # type: ignore[arg-type]
            source_asset_id=retry_context.source_asset_id,
            source_name=original_run.source_name,
            source_asset=source_asset,
            config_repository=config_repository,
            transformation_service=transformation_service,
            registry=registry,
            promotion_handler_registry=promotion_handler_registry,
            publish_reporting=publish_reporting,
            ingestion_definition_id=retry_context.ingestion_definition_id,
            run_context=retry_context,
        )

    if retry_kind == "account_transactions":
        return ingest_account_transaction_bytes(
            source_bytes,
            original_run.file_name,
            original_run.source_name,
            service=service,
            transformation_service=transformation_service,
            publish_reporting=publish_reporting,
            run_context=retry_context,
        )

    if retry_kind == "subscriptions":
        assert subscription_service is not None
        return ingest_subscription_bytes(
            source_bytes,
            original_run.file_name,
            original_run.source_name,
            subscription_service=subscription_service,
            transformation_service=transformation_service,
            publish_reporting=publish_reporting,
            run_context=retry_context,
        )

    if retry_kind == "contract_prices":
        assert contract_price_service is not None
        return ingest_contract_prices_bytes(
            source_bytes,
            original_run.file_name,
            original_run.source_name,
            contract_price_service=contract_price_service,
            transformation_service=transformation_service,
            publish_reporting=publish_reporting,
            run_context=retry_context,
        )

    raise ValueError(f"Unknown retry_kind: {retry_kind!r}")
