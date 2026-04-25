from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from apps.api.response_models import RunMutationResponseModel
from packages.application.use_cases.run_management import retry_ingest_run
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.finance.pipelines.contract_price_service import ContractPriceService
from packages.domains.finance.pipelines.subscription_service import SubscriptionService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.promotion import PromotionResult
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.pipelines.run_context import merge_run_context
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
    subscription_service: SubscriptionService | None,
    contract_price_service: ContractPriceService | None,
    registry: ExtensionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry | None,
    load_run_manifest_and_context: Callable[[IngestionRunRecord], tuple[Any, Any]],
    build_run_recovery: Callable[[IngestionRunRecord, Any], dict[str, Any]],
    serialize_run: Callable[..., dict[str, Any]],
    serialize_run_detail: Callable[[IngestionRunRecord], dict[str, Any]],
    build_run_response: Callable[..., JSONResponse],
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

        # Source asset validation for configured_csv stays in the route (raises HTTPException).
        source_asset = None
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

        retried_run, promotion = retry_ingest_run(
            original_run,
            retry_kind,
            source_bytes,
            retry_context,
            service=service,
            configured_ingestion_service=configured_ingestion_service,
            subscription_service=subscription_service,
            contract_price_service=contract_price_service,
            config_repository=resolved_config_repository,
            source_asset=source_asset,
            transformation_service=transformation_service,
            registry=registry,
            promotion_handler_registry=promotion_handler_registry,
            publish_reporting=publish_reporting,
        )
        return build_run_response(retried_run, promotion=promotion)
