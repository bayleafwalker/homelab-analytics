from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from apps.api.models import (
    ColumnMappingRequest,
    ConfiguredCsvIngestRequest,
    DatasetContractRequest,
    IngestionDefinitionRequest,
    PublicationDefinitionRequest,
    SourceAssetRequest,
    SourceSystemRequest,
    TransformationPackageRequest,
)
from packages.analytics.cashflow import MonthlyCashflowSummary
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.promotion import (
    PromotionResult,
    promote_contract_price_run,
    promote_run,
    promote_source_asset_run,
    promote_subscription_run,
)
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import (
    ExtensionRegistry,
    build_builtin_extension_registry,
    serialize_extension_registry,
)
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionDefinitionCreate,
    IngestionConfigRepository,
    PublicationDefinitionCreate,
    RequestHeaderSecretRef,
    SourceAssetCreate,
    SourceSystemCreate,
    TransformationPackageCreate,
)
from packages.storage.run_metadata import IngestionRunRecord, IngestionRunStatus


def create_app(
    service: AccountTransactionService,
    extension_registry: ExtensionRegistry | None = None,
    config_repository: IngestionConfigRepository | None = None,
    transformation_service: TransformationService | None = None,
    subscription_service: SubscriptionService | None = None,
    contract_price_service: ContractPriceService | None = None,
) -> FastAPI:
    registry = extension_registry or build_builtin_extension_registry()
    resolved_config_repository = config_repository or IngestionConfigRepository(
        service.landing_root.parent / "config.db"
    )
    configured_ingestion_service = ConfiguredCsvIngestionService(
        landing_root=service.landing_root,
        metadata_repository=service.metadata_repository,
        config_repository=resolved_config_repository,
        blob_store=service.blob_store,
    )
    configured_definition_service = ConfiguredIngestionDefinitionService(
        landing_root=service.landing_root,
        metadata_repository=service.metadata_repository,
        config_repository=resolved_config_repository,
        blob_store=service.blob_store,
    )
    app = FastAPI(title="Homelab Analytics API")

    @app.exception_handler(FileNotFoundError)
    async def handle_missing_file(_, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": str(exc)})

    @app.exception_handler(KeyError)
    async def handle_missing_key(_, exc: KeyError) -> JSONResponse:
        message = exc.args[0] if exc.args else str(exc)
        return JSONResponse(status_code=404, content={"error": message})

    @app.exception_handler(ValueError)
    async def handle_value_error(_, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
        return {"run": serialize_run(service.get_run(run_id))}

    @app.get("/extensions")
    async def list_extensions() -> dict[str, Any]:
        return {"extensions": serialize_extension_registry(registry)}

    @app.get("/sources")
    async def list_sources() -> dict[str, Any]:
        return {
            "source_systems": _to_jsonable(
                resolved_config_repository.list_source_systems()
            ),
            "source_assets": _to_jsonable(
                resolved_config_repository.list_source_assets()
            ),
        }

    @app.get("/config/source-systems")
    async def list_source_systems() -> dict[str, Any]:
        return {
            "source_systems": _to_jsonable(
                resolved_config_repository.list_source_systems()
            )
        }

    @app.post("/config/source-systems", status_code=201)
    async def create_source_system(payload: SourceSystemRequest) -> dict[str, Any]:
        source_system = resolved_config_repository.create_source_system(
            SourceSystemCreate(
                source_system_id=payload.source_system_id,
                name=payload.name,
                source_type=payload.source_type,
                transport=payload.transport,
                schedule_mode=payload.schedule_mode,
                description=payload.description,
            )
        )
        return {"source_system": _to_jsonable(source_system)}

    @app.get("/config/dataset-contracts")
    async def list_dataset_contracts() -> dict[str, Any]:
        return {
            "dataset_contracts": _to_jsonable(
                resolved_config_repository.list_dataset_contracts()
            )
        }

    @app.post("/config/dataset-contracts", status_code=201)
    async def create_dataset_contract(payload: DatasetContractRequest) -> dict[str, Any]:
        dataset_contract = resolved_config_repository.create_dataset_contract(
            DatasetContractConfigCreate(
                dataset_contract_id=payload.dataset_contract_id,
                dataset_name=payload.dataset_name,
                version=payload.version,
                allow_extra_columns=payload.allow_extra_columns,
                columns=tuple(
                    DatasetColumnConfig(
                        name=column.name,
                        type=column.type,
                        required=column.required,
                    )
                    for column in payload.columns
                ),
            )
        )
        return {"dataset_contract": _to_jsonable(dataset_contract)}

    @app.get("/config/column-mappings")
    async def list_column_mappings() -> dict[str, Any]:
        return {
            "column_mappings": _to_jsonable(
                resolved_config_repository.list_column_mappings()
            )
        }

    @app.post("/config/column-mappings", status_code=201)
    async def create_column_mapping(payload: ColumnMappingRequest) -> dict[str, Any]:
        column_mapping = resolved_config_repository.create_column_mapping(
            ColumnMappingCreate(
                column_mapping_id=payload.column_mapping_id,
                source_system_id=payload.source_system_id,
                dataset_contract_id=payload.dataset_contract_id,
                version=payload.version,
                rules=tuple(
                    ColumnMappingRule(
                        target_column=rule.target_column,
                        source_column=rule.source_column,
                        default_value=rule.default_value,
                    )
                    for rule in payload.rules
                ),
            )
        )
        return {"column_mapping": _to_jsonable(column_mapping)}

    @app.get("/config/transformation-packages")
    async def list_transformation_packages() -> dict[str, Any]:
        return {
            "transformation_packages": _to_jsonable(
                resolved_config_repository.list_transformation_packages()
            )
        }

    @app.post("/config/transformation-packages", status_code=201)
    async def create_transformation_package(
        payload: TransformationPackageRequest,
    ) -> dict[str, Any]:
        transformation_package = resolved_config_repository.create_transformation_package(
            TransformationPackageCreate(
                transformation_package_id=payload.transformation_package_id,
                name=payload.name,
                handler_key=payload.handler_key,
                version=payload.version,
                description=payload.description,
            )
        )
        return {"transformation_package": _to_jsonable(transformation_package)}

    @app.get("/config/publication-definitions")
    async def list_publication_definitions(
        transformation_package_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "publication_definitions": _to_jsonable(
                resolved_config_repository.list_publication_definitions(
                    transformation_package_id=transformation_package_id
                )
            )
        }

    @app.post("/config/publication-definitions", status_code=201)
    async def create_publication_definition(
        payload: PublicationDefinitionRequest,
    ) -> dict[str, Any]:
        publication_definition = resolved_config_repository.create_publication_definition(
            PublicationDefinitionCreate(
                publication_definition_id=payload.publication_definition_id,
                transformation_package_id=payload.transformation_package_id,
                publication_key=payload.publication_key,
                name=payload.name,
                description=payload.description,
            )
        )
        return {"publication_definition": _to_jsonable(publication_definition)}

    @app.get("/config/source-assets")
    async def list_source_assets() -> dict[str, Any]:
        return {"source_assets": _to_jsonable(resolved_config_repository.list_source_assets())}

    @app.post("/config/source-assets", status_code=201)
    async def create_source_asset(payload: SourceAssetRequest) -> dict[str, Any]:
        source_asset = resolved_config_repository.create_source_asset(
            SourceAssetCreate(
                source_asset_id=payload.source_asset_id,
                source_system_id=payload.source_system_id,
                dataset_contract_id=payload.dataset_contract_id,
                column_mapping_id=payload.column_mapping_id,
                name=payload.name,
                asset_type=payload.asset_type,
                transformation_package_id=payload.transformation_package_id,
                description=payload.description,
            )
        )
        return {"source_asset": _to_jsonable(source_asset)}

    @app.get("/config/ingestion-definitions")
    async def list_ingestion_definitions() -> dict[str, Any]:
        return {
            "ingestion_definitions": _to_jsonable(
                resolved_config_repository.list_ingestion_definitions()
            )
        }

    @app.post("/config/ingestion-definitions", status_code=201)
    async def create_ingestion_definition(
        payload: IngestionDefinitionRequest,
    ) -> dict[str, Any]:
        ingestion_definition = resolved_config_repository.create_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id=payload.ingestion_definition_id,
                source_asset_id=payload.source_asset_id,
                transport=payload.transport,
                schedule_mode=payload.schedule_mode,
                source_path=payload.source_path,
                file_pattern=payload.file_pattern,
                processed_path=payload.processed_path,
                failed_path=payload.failed_path,
                poll_interval_seconds=payload.poll_interval_seconds,
                request_url=payload.request_url,
                request_method=payload.request_method,
                request_headers=tuple(
                    RequestHeaderSecretRef(
                        name=header.name,
                        secret_name=header.secret_name,
                        secret_key=header.secret_key,
                    )
                    for header in payload.request_headers
                ),
                request_timeout_seconds=payload.request_timeout_seconds,
                response_format=payload.response_format,
                output_file_name=payload.output_file_name,
                enabled=payload.enabled,
                source_name=payload.source_name,
            )
        )
        return {"ingestion_definition": _to_jsonable(ingestion_definition)}

    @app.post("/landing/{extension_key}", status_code=201)
    async def run_landing_extension(
        extension_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        result = registry.execute(
            "landing",
            extension_key,
            service=service,
            **payload,
        )
        return {"result": _to_jsonable(result)}

    @app.post("/ingest", status_code=201)
    async def ingest_account_transactions(request: Request) -> JSONResponse:
        return await _handle_account_transaction_ingest(
            request, service, transformation_service
        )

    @app.post("/ingest/account-transactions", status_code=201)
    async def ingest_account_transactions_alias(request: Request) -> JSONResponse:
        return await _handle_account_transaction_ingest(
            request, service, transformation_service
        )

    @app.post("/ingest/configured-csv", status_code=201)
    async def ingest_configured_csv(
        payload: ConfiguredCsvIngestRequest,
    ) -> JSONResponse:
        source_asset = (
            resolved_config_repository.get_source_asset(payload.source_asset_id)
            if payload.source_asset_id
            else None
        )
        source_system_id = (
            source_asset.source_system_id if source_asset else payload.source_system_id
        )
        dataset_contract_id = (
            source_asset.dataset_contract_id
            if source_asset
            else payload.dataset_contract_id
        )
        column_mapping_id = (
            source_asset.column_mapping_id if source_asset else payload.column_mapping_id
        )
        run = configured_ingestion_service.ingest_file(
            source_path=Path(payload.source_path),
            source_system_id=source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=column_mapping_id,
            source_name=payload.source_name,
        )
        promotion: PromotionResult | None = None
        if transformation_service is not None and run.passed:
            resolved_source_asset = source_asset or resolved_config_repository.find_source_asset_by_binding(
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
            )
            if resolved_source_asset is not None:
                promotion = promote_source_asset_run(
                    run.run_id,
                    source_asset=resolved_source_asset,
                    config_repository=resolved_config_repository,
                    landing_root=service.landing_root,
                    metadata_repository=service.metadata_repository,
                    transformation_service=transformation_service,
                    blob_store=service.blob_store,
                )
        return _build_run_response(run, promotion=promotion)

    @app.post("/ingest/subscriptions", status_code=201)
    async def ingest_subscriptions(request: Request) -> JSONResponse:
        if subscription_service is None:
            raise KeyError("subscription ingestion is not configured")
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "read"):
                raise ValueError("multipart request must include file")
            source_name = str(form.get("source_name") or "manual-upload")
            source_bytes = await upload.read()
            await upload.close()
            run = subscription_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=getattr(upload, "filename", None) or "subscriptions.csv",
                source_name=source_name,
            )
        else:
            payload = await request.json()
            run = subscription_service.ingest_file(
                Path(payload["source_path"]),
                source_name=payload.get("source_name", "manual-upload"),
            )
        promotion: PromotionResult | None = None
        if transformation_service is not None and run.passed:
            promotion = promote_subscription_run(
                run.run_id,
                subscription_service=subscription_service,
                transformation_service=transformation_service,
            )
        body: dict[str, Any] = {"run": serialize_run(run)}
        if promotion is not None:
            body["promotion"] = serialize_promotion(promotion)
        status_code = 409 if any(i.code == "duplicate_file" for i in run.issues) else (
            201 if run.passed else 400
        )
        return JSONResponse(status_code=status_code, content=body)

    @app.post("/ingest/contract-prices", status_code=201)
    async def ingest_contract_prices(request: Request) -> JSONResponse:
        if contract_price_service is None:
            raise KeyError("contract-price ingestion is not configured")
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "read"):
                raise ValueError("multipart request must include file")
            source_name = str(form.get("source_name") or "manual-upload")
            source_bytes = await upload.read()
            await upload.close()
            run = contract_price_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=getattr(upload, "filename", None) or "contract-prices.csv",
                source_name=source_name,
            )
        else:
            payload = await request.json()
            run = contract_price_service.ingest_file(
                Path(payload["source_path"]),
                source_name=payload.get("source_name", "manual-upload"),
            )
        promotion: PromotionResult | None = None
        if transformation_service is not None and run.passed:
            promotion = promote_contract_price_run(
                run.run_id,
                contract_price_service=contract_price_service,
                transformation_service=transformation_service,
            )
        body: dict[str, Any] = {"run": serialize_run(run)}
        if promotion is not None:
            body["promotion"] = serialize_promotion(promotion)
        status_code = 409 if any(i.code == "duplicate_file" for i in run.issues) else (
            201 if run.passed else 400
        )
        return JSONResponse(status_code=status_code, content=body)

    @app.post("/ingest/ingestion-definitions/{ingestion_definition_id}/process", status_code=201)
    async def process_ingestion_definition(ingestion_definition_id: str) -> dict[str, Any]:
        result = configured_definition_service.process_ingestion_definition(
            ingestion_definition_id
        )
        body: dict[str, Any] = {"result": _to_jsonable(result)}
        if transformation_service is not None:
            ingestion_definition = resolved_config_repository.get_ingestion_definition(
                ingestion_definition_id
            )
            source_asset = resolved_config_repository.get_source_asset(
                ingestion_definition.source_asset_id
            )
            body["promotions"] = _to_jsonable(
                [
                    promote_source_asset_run(
                        run_id,
                        source_asset=source_asset,
                        config_repository=resolved_config_repository,
                        landing_root=service.landing_root,
                        metadata_repository=service.metadata_repository,
                        transformation_service=transformation_service,
                        blob_store=service.blob_store,
                    )
                    for run_id in result.run_ids
                ]
            )
        return body

    @app.get("/transformations/{extension_key}")
    async def run_transformation_extension(
        extension_key: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")
        result = registry.execute(
            "transformation",
            extension_key,
            service=service,
            run_id=run_id,
        )
        return {"result": _to_jsonable(result)}

    @app.get("/reports/monthly-cashflow")
    async def get_monthly_cashflow(
        run_id: str | None = None,
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> dict[str, Any]:
        # Mart path: serve from the persisted DuckDB mart when transformation
        # service is wired in and no run-scoped override is requested.
        if transformation_service is not None and run_id is None:
            rows = transformation_service.get_monthly_cashflow(
                from_month=from_month,
                to_month=to_month,
            )
            return {
                "rows": _to_jsonable(rows),
                "from_month": from_month,
                "to_month": to_month,
            }
        # Legacy path: per-run on-the-fly computation from landing data.
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")
        summaries = [serialize_summary(summary) for summary in service.get_monthly_cashflow(run_id)]
        return {"summaries": summaries}

    @app.get("/reports/current-dimensions/{dimension_name}")
    async def get_current_dimension_report(dimension_name: str) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Current-dimension reporting is not configured.",
            )
        return {
            "dimension": dimension_name,
            "rows": _to_jsonable(
                transformation_service.get_current_dimension_rows(dimension_name)
            ),
        }

    @app.get("/reports/monthly-cashflow-by-counterparty")
    async def get_monthly_cashflow_by_counterparty(
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty: str | None = None,
    ) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Counterparty cashflow reporting requires a transformation service.",
            )
        rows = transformation_service.get_monthly_cashflow_by_counterparty(
            from_month=from_month,
            to_month=to_month,
            counterparty_name=counterparty,
        )
        return {
            "rows": _to_jsonable(rows),
            "from_month": from_month,
            "to_month": to_month,
            "counterparty": counterparty,
        }

    @app.get("/reports/subscription-summary")
    async def get_subscription_summary(
        status: str | None = None,
        currency: str | None = None,
    ) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Subscription reporting requires a transformation service.",
            )
        return {
            "rows": _to_jsonable(
                transformation_service.get_subscription_summary(
                    status=status,
                    currency=currency,
                )
            ),
            "status": status,
            "currency": currency,
        }

    @app.get("/reports/contract-prices")
    async def get_contract_price_current(
        contract_type: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Contract-price reporting requires a transformation service.",
            )
        return {
            "rows": _to_jsonable(
                transformation_service.get_contract_price_current(
                    contract_type=contract_type,
                    status=status,
                )
            ),
            "contract_type": contract_type,
            "status": status,
        }

    @app.get("/reports/electricity-prices")
    async def get_electricity_price_current() -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Electricity price reporting requires a transformation service.",
            )
        return {
            "rows": _to_jsonable(
                transformation_service.get_electricity_price_current()
            )
        }

    @app.get("/transformation-audit")
    async def get_transformation_audit(run_id: str | None = None) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Transformation audit requires a transformation service.",
            )
        records = transformation_service.get_transformation_audit(
            input_run_id=run_id,
        )
        return {"audit": _to_jsonable(records)}

    @app.get("/reports/{extension_key}")
    async def run_reporting_extension(
        extension_key: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")
        result = registry.execute(
            "reporting",
            extension_key,
            service=service,
            run_id=run_id,
        )
        return {"result": _to_jsonable(result)}

    return app


async def _handle_account_transaction_ingest(
    request: Request,
    service: AccountTransactionService,
    transformation_service: TransformationService | None = None,
) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read") or not hasattr(upload, "filename"):
            raise ValueError("multipart request must include file")
        source_name = str(form.get("source_name") or "manual-upload")
        source_bytes = await upload.read()
        await upload.close()
        run = service.ingest_bytes(
            source_bytes=source_bytes,
            file_name=upload.filename or "upload.csv",
            source_name=source_name,
        )
        return _build_ingest_response(run, service, transformation_service)

    payload = await request.json()
    run = service.ingest_file(
        Path(payload["source_path"]),
        source_name=payload.get("source_name", "manual-upload"),
    )
    return _build_ingest_response(run, service, transformation_service)


def _build_ingest_response(
    run: IngestionRunRecord,
    service: AccountTransactionService,
    transformation_service: TransformationService | None,
) -> JSONResponse:
    """Build an ingest response, auto-promoting into DuckDB if a transformation
    service is wired in and the run passed validation."""
    promotion: PromotionResult | None = None
    if transformation_service is not None and run.passed:
        promotion = promote_run(
            run.run_id,
            account_service=service,
            transformation_service=transformation_service,
        )
    return _build_run_response(run, promotion=promotion)


def _build_run_response(
    run: IngestionRunRecord,
    *,
    promotion: PromotionResult | None = None,
) -> JSONResponse:
    if any(issue.code == "duplicate_file" for issue in run.issues):
        status_code = 409
    elif run.passed:
        status_code = 201
    else:
        status_code = 400
    body: dict[str, Any] = {"run": serialize_run(run)}
    if promotion is not None:
        body["promotion"] = serialize_promotion(promotion)
    return JSONResponse(status_code=status_code, content=body)


def serialize_promotion(promotion: PromotionResult) -> dict[str, Any]:
    return {
        "facts_loaded": promotion.facts_loaded,
        "marts_refreshed": promotion.marts_refreshed,
        "publication_keys": promotion.publication_keys,
        "skipped": promotion.skipped,
        "skip_reason": promotion.skip_reason,
    }


def serialize_run(run: IngestionRunRecord) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "source_name": run.source_name,
        "dataset_name": run.dataset_name,
        "file_name": run.file_name,
        "raw_path": run.raw_path,
        "manifest_path": run.manifest_path,
        "sha256": run.sha256,
        "row_count": run.row_count,
        "header": list(run.header),
        "status": run.status.value,
        "passed": run.passed,
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "column": issue.column,
                "row_number": issue.row_number,
            }
            for issue in run.issues
        ],
        "created_at": run.created_at.isoformat(),
    }


def serialize_summary(summary: MonthlyCashflowSummary) -> dict[str, Any]:
    return {
        "booking_month": summary.booking_month,
        "income": str(summary.income),
        "expense": str(summary.expense),
        "net": str(summary.net),
        "transaction_count": summary.transaction_count,
    }

def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _to_jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(inner) for inner in value]
    return value
