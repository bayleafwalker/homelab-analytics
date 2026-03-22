from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from apps.api.response_models import RunMutationResponseModel
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.promotion import (
    PromotionResult,
    promote_contract_price_run,
    promote_source_asset_run,
    promote_subscription_run,
)
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.run_context import merge_run_context
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionRegistry
from packages.storage.control_plane import ConfigCatalogStore
from packages.storage.run_metadata import IngestionRunRecord, IngestionRunStatus


def register_run_routes(
    app: FastAPI,
    *,
    service: AccountTransactionService,
    configured_ingestion_service: ConfiguredCsvIngestionService,
    resolved_config_repository: ConfigCatalogStore,
    transformation_service: TransformationService | None,
    resolved_reporting_service: ReportingService | None,
    subscription_service: SubscriptionService | None,
    contract_price_service: ContractPriceService | None,
    registry: ExtensionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry | None,
    load_run_manifest_and_context: Callable[[IngestionRunRecord], tuple[Any, Any]],
    build_run_recovery: Callable[[IngestionRunRecord, Any], dict[str, Any]],
    serialize_run: Callable[..., dict[str, Any]],
    serialize_run_detail: Callable[[IngestionRunRecord], dict[str, Any]],
    build_run_response: Callable[..., JSONResponse],
    build_ingest_response: Callable[..., JSONResponse],
    publish_reporting: Callable[[PromotionResult | None], None],
) -> None:
    @app.get("/runs")
    async def list_runs(
        dataset: str | None = None,
        status: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        try:
            run_status = IngestionRunStatus(status) if status else None
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status!r}")
        runs = service.metadata_repository.list_runs(
            dataset_name=dataset,
            status=run_status,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        total = service.metadata_repository.count_runs(
            dataset_name=dataset,
            status=run_status,
            from_date=from_date,
            to_date=to_date,
        )
        return {
            "runs": [serialize_run(run) for run in runs],
            "pagination": {"total": total, "limit": limit, "offset": offset},
        }

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        return {"run": serialize_run_detail(service.get_run(run_id))}

    @app.post("/runs/{run_id}/retry", response_model=RunMutationResponseModel)
    async def retry_run(run_id: str) -> JSONResponse:
        original_run = service.metadata_repository.get_run(run_id)
        _, context = load_run_manifest_and_context(original_run)
        recovery = build_run_recovery(original_run, context)
        if not recovery["retry_supported"]:
            raise HTTPException(
                status_code=400,
                detail=str(recovery["reason"] or "Run retry is not supported."),
            )
        try:
            source_bytes = service.blob_store.read_bytes(original_run.raw_path)
        except (KeyError, OSError) as exc:
            raise HTTPException(
                status_code=409,
                detail="Run payload is no longer available for retry.",
            ) from exc

        retry_context = merge_run_context(context, retry_of_run_id=original_run.run_id)
        retry_kind = recovery["retry_kind"]
        promotion: PromotionResult | None = None

        if retry_kind == "configured_csv":
            assert context is not None
            if (
                context.source_system_id is None
                or context.dataset_contract_id is None
                or context.column_mapping_id is None
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Configured retry is missing required binding context.",
                )
            source_asset = None
            if context.source_asset_id is not None:
                source_asset = resolved_config_repository.get_source_asset(context.source_asset_id)
                if source_asset.archived:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Source asset is archived: {source_asset.source_asset_id}",
                    )
                if not source_asset.enabled:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Source asset is disabled: {source_asset.source_asset_id}",
                    )

            retried_run = configured_ingestion_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=original_run.file_name,
                source_system_id=context.source_system_id,
                dataset_contract_id=context.dataset_contract_id,
                column_mapping_id=context.column_mapping_id,
                source_asset_id=context.source_asset_id,
                ingestion_definition_id=context.ingestion_definition_id,
                source_name=original_run.source_name,
                run_context=retry_context,
            )
            if transformation_service is not None and retried_run.passed:
                resolved_source_asset = (
                    source_asset
                    or resolved_config_repository.find_source_asset_by_binding(
                        source_system_id=context.source_system_id,
                        dataset_contract_id=context.dataset_contract_id,
                        column_mapping_id=context.column_mapping_id,
                    )
                )
                if resolved_source_asset is not None:
                    promotion = promote_source_asset_run(
                        retried_run.run_id,
                        source_asset=resolved_source_asset,
                        config_repository=resolved_config_repository,
                        landing_root=service.landing_root,
                        metadata_repository=service.metadata_repository,
                        transformation_service=transformation_service,
                        blob_store=service.blob_store,
                        extension_registry=registry,
                        promotion_handler_registry=promotion_handler_registry,
                    )
                    publish_reporting(promotion)
            return build_run_response(retried_run, promotion=promotion)

        if retry_kind == "account_transactions":
            retried_run = service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=original_run.file_name,
                source_name=original_run.source_name,
                run_context=retry_context,
            )
            return build_ingest_response(
                retried_run,
                service,
                transformation_service,
                resolved_reporting_service,
            )

        if retry_kind == "subscriptions":
            assert subscription_service is not None
            retried_run = subscription_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=original_run.file_name,
                source_name=original_run.source_name,
                run_context=retry_context,
            )
            if transformation_service is not None and retried_run.passed:
                promotion = promote_subscription_run(
                    retried_run.run_id,
                    subscription_service=subscription_service,
                    transformation_service=transformation_service,
                )
                publish_reporting(promotion)
            return build_run_response(retried_run, promotion=promotion)

        if retry_kind == "contract_prices":
            assert contract_price_service is not None
            retried_run = contract_price_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=original_run.file_name,
                source_name=original_run.source_name,
                run_context=retry_context,
            )
            if transformation_service is not None and retried_run.passed:
                promotion = promote_contract_price_run(
                    retried_run.run_id,
                    contract_price_service=contract_price_service,
                    transformation_service=transformation_service,
                )
                publish_reporting(promotion)
            return build_run_response(retried_run, promotion=promotion)

        raise HTTPException(status_code=400, detail="Run retry is not supported.")
