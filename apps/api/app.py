from __future__ import annotations

import logging
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.datastructures import UploadFile

from apps.api.models import (
    ColumnMappingRequest,
    ConfiguredCsvIngestRequest,
    DatasetContractRequest,
    ExecutionScheduleRequest,
    IngestionDefinitionRequest,
    LoginRequest,
    PublicationDefinitionRequest,
    SourceAssetRequest,
    SourceSystemRequest,
    TransformationPackageRequest,
)
from packages.analytics.cashflow import MonthlyCashflowSummary
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.promotion import (
    PromotionResult,
    promote_contract_price_run,
    promote_run,
    promote_source_asset_run,
    promote_subscription_run,
)
from packages.pipelines.reporting_service import (
    ReportingService,
    publish_promotion_reporting,
)
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.auth import (
    AuthenticatedPrincipal,
    SessionManager,
    has_required_role,
    serialize_principal,
    serialize_user,
    verify_password,
)
from packages.shared.extensions import (
    ExtensionRegistry,
    build_builtin_extension_registry,
    serialize_extension_registry,
)
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import AuthStore, UserRole
from packages.storage.control_plane import ControlPlaneStore, ExecutionScheduleCreate
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    IngestionDefinitionCreate,
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
    config_repository: ControlPlaneStore | None = None,
    transformation_service: TransformationService | None = None,
    reporting_service: ReportingService | None = None,
    subscription_service: SubscriptionService | None = None,
    contract_price_service: ContractPriceService | None = None,
    auth_store: AuthStore | None = None,
    auth_mode: str = "disabled",
    session_manager: SessionManager | None = None,
    enable_unsafe_admin: bool = False,
) -> FastAPI:
    registry = extension_registry or build_builtin_extension_registry()
    resolved_config_repository = config_repository or IngestionConfigRepository(
        service.landing_root.parent / "config.db"
    )
    resolved_auth_store_candidate = auth_store or resolved_config_repository
    resolved_auth_mode = auth_mode.lower()
    if resolved_auth_mode not in {"disabled", "local"}:
        raise ValueError(f"Unsupported auth mode: {auth_mode!r}")
    if resolved_auth_mode == "local" and session_manager is None:
        raise ValueError("Local auth requires a configured session manager.")
    if resolved_auth_mode == "local" and not isinstance(
        resolved_auth_store_candidate, AuthStore
    ):
        raise ValueError("Local auth requires an auth-capable control-plane store.")
    resolved_auth_store = cast(AuthStore, resolved_auth_store_candidate)
    resolved_session_manager = session_manager
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
    resolved_reporting_service = (
        reporting_service
        or (
            ReportingService(
                transformation_service,
                extension_registry=registry,
            )
            if transformation_service is not None
            else None
        )
    )
    app = FastAPI(title="Homelab Analytics API")
    logger = logging.getLogger("homelab_analytics.api")

    metrics_registry.inc(
        "ingestion_runs_total",
        0,
        help_text="Total ingestion runs observed by the API.",
    )
    metrics_registry.inc(
        "ingestion_failures_total",
        0,
        help_text="Total failed or rejected ingestion runs observed by the API.",
    )
    metrics_registry.inc(
        "ingestion_duration_seconds",
        0,
        help_text="Cumulative ingestion handling duration in seconds.",
    )
    metrics_registry.set(
        "worker_queue_depth",
        0,
        help_text="Current queued schedule-dispatch count.",
    )

    def require_unsafe_admin() -> None:
        if resolved_auth_mode == "local":
            return
        if not enable_unsafe_admin:
            raise HTTPException(
                status_code=404,
                detail="Unsafe admin routes are disabled until authentication is implemented.",
            )

    def publish_reporting(promotion: PromotionResult | None) -> None:
        publish_promotion_reporting(resolved_reporting_service, promotion)

    def required_role_for_path(path: str) -> UserRole | None:
        if path in {"/health", "/metrics", "/auth/login", "/auth/logout"}:
            return None
        if (
            path.startswith("/config/")
            or path.startswith("/control/")
            or path in {"/extensions", "/sources"}
            or path.startswith("/landing/")
            or path.startswith("/transformations/")
            or path.startswith("/ingest/ingestion-definitions/")
        ):
            return UserRole.ADMIN
        if path.startswith("/ingest"):
            return UserRole.OPERATOR
        if (
            path.startswith("/runs")
            or path.startswith("/reports")
            or path == "/transformation-audit"
            or path == "/auth/me"
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path == "/openapi.json"
        ):
            return UserRole.READER
        return None

    @app.middleware("http")
    async def authenticate_and_log_request(request: Request, call_next):
        started = time.perf_counter()
        request.state.principal = None
        if resolved_auth_mode == "local":
            assert resolved_session_manager is not None
            required_role = required_role_for_path(request.url.path)
            request.state.principal = resolved_session_manager.authenticate(
                request.cookies.get(resolved_session_manager.cookie_name),
                resolved_auth_store,
            )
            if required_role is not None:
                admin_bypass = enable_unsafe_admin and required_role == UserRole.ADMIN
                if request.state.principal is None and not admin_bypass:
                    response = JSONResponse(
                        status_code=401,
                        content={"detail": "Authentication required."},
                    )
                    _log_request(logger, request.method, request.url.path, 401, started)
                    return response
                if (
                    request.state.principal is not None
                    and not has_required_role(
                        request.state.principal.role,
                        required_role,
                    )
                ):
                    response = JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"{required_role.value} role required.",
                        },
                    )
                    _log_request(logger, request.method, request.url.path, 403, started)
                    return response
        response = await call_next(request)
        if request.url.path.startswith("/ingest"):
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            metrics_registry.inc(
                "ingestion_duration_seconds",
                duration_ms / 1000,
                help_text="Cumulative ingestion handling duration in seconds.",
            )
        _log_request(
            logger,
            request.method,
            request.url.path,
            response.status_code,
            started,
        )
        return response

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

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        metrics_registry.set(
            "worker_queue_depth",
            float(
                len(
                    resolved_config_repository.list_schedule_dispatches(
                        status="enqueued"
                    )
                )
            ),
            help_text="Current queued schedule-dispatch count.",
        )
        return PlainTextResponse(
            metrics_registry.render_prometheus_text(),
            media_type="text/plain; version=0.0.4",
        )

    @app.post("/auth/login")
    async def login(payload: LoginRequest) -> JSONResponse:
        if resolved_auth_mode != "local":
            raise HTTPException(
                status_code=400,
                detail="Local authentication is not enabled.",
            )
        try:
            user = resolved_auth_store.get_local_user_by_username(payload.username)
        except KeyError as exc:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password.",
            ) from exc
        if not user.enabled or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password.",
            )
        user = resolved_auth_store.record_local_user_login(user.user_id)
        assert resolved_session_manager is not None
        response = JSONResponse(
            {
                "auth_mode": "local",
                "authenticated": True,
                "user": serialize_user(user),
                "principal": serialize_principal(request_principal_from_user(user)),
            }
        )
        response.set_cookie(
            key=resolved_session_manager.cookie_name,
            value=resolved_session_manager.issue_session_cookie(user),
            httponly=True,
            max_age=resolved_session_manager.max_age_seconds,
            path="/",
            samesite="lax",
        )
        return response

    @app.post("/auth/logout")
    async def logout() -> JSONResponse:
        response = JSONResponse({"logged_out": True})
        if resolved_session_manager is not None:
            response.delete_cookie(
                resolved_session_manager.cookie_name,
                path="/",
                httponly=True,
                samesite="lax",
            )
        return response

    @app.get("/auth/me")
    async def auth_me(request: Request) -> dict[str, Any]:
        if resolved_auth_mode != "local":
            return {"auth_mode": "disabled", "authenticated": False}
        principal = getattr(request.state, "principal", None)
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        user = resolved_auth_store.get_local_user(principal.user_id)
        return {
            "auth_mode": "local",
            "authenticated": True,
            "user": serialize_user(user),
            "principal": serialize_principal(principal),
        }

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
        require_unsafe_admin()
        return {"extensions": serialize_extension_registry(registry)}

    @app.get("/sources")
    async def list_sources() -> dict[str, Any]:
        require_unsafe_admin()
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
        require_unsafe_admin()
        return {
            "source_systems": _to_jsonable(
                resolved_config_repository.list_source_systems()
            )
        }

    @app.post("/config/source-systems", status_code=201)
    async def create_source_system(payload: SourceSystemRequest) -> dict[str, Any]:
        require_unsafe_admin()
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
        require_unsafe_admin()
        return {
            "dataset_contracts": _to_jsonable(
                resolved_config_repository.list_dataset_contracts()
            )
        }

    @app.post("/config/dataset-contracts", status_code=201)
    async def create_dataset_contract(payload: DatasetContractRequest) -> dict[str, Any]:
        require_unsafe_admin()
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
        require_unsafe_admin()
        return {
            "column_mappings": _to_jsonable(
                resolved_config_repository.list_column_mappings()
            )
        }

    @app.post("/config/column-mappings", status_code=201)
    async def create_column_mapping(payload: ColumnMappingRequest) -> dict[str, Any]:
        require_unsafe_admin()
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
        require_unsafe_admin()
        return {
            "transformation_packages": _to_jsonable(
                resolved_config_repository.list_transformation_packages()
            )
        }

    @app.post("/config/transformation-packages", status_code=201)
    async def create_transformation_package(
        payload: TransformationPackageRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
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
        require_unsafe_admin()
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
        require_unsafe_admin()
        publication_definition = resolved_config_repository.create_publication_definition(
            PublicationDefinitionCreate(
                publication_definition_id=payload.publication_definition_id,
                transformation_package_id=payload.transformation_package_id,
                publication_key=payload.publication_key,
                name=payload.name,
                description=payload.description,
            ),
            extension_registry=registry,
        )
        return {"publication_definition": _to_jsonable(publication_definition)}

    @app.get("/config/source-assets")
    async def list_source_assets() -> dict[str, Any]:
        require_unsafe_admin()
        return {"source_assets": _to_jsonable(resolved_config_repository.list_source_assets())}

    @app.post("/config/source-assets", status_code=201)
    async def create_source_asset(payload: SourceAssetRequest) -> dict[str, Any]:
        require_unsafe_admin()
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
        require_unsafe_admin()
        return {
            "ingestion_definitions": _to_jsonable(
                resolved_config_repository.list_ingestion_definitions()
            )
        }

    @app.post("/config/ingestion-definitions", status_code=201)
    async def create_ingestion_definition(
        payload: IngestionDefinitionRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
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

    @app.get("/config/execution-schedules")
    async def list_execution_schedules() -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "execution_schedules": _to_jsonable(
                resolved_config_repository.list_execution_schedules()
            )
        }

    @app.post("/config/execution-schedules", status_code=201)
    async def create_execution_schedule(
        payload: ExecutionScheduleRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        schedule = resolved_config_repository.create_execution_schedule(
            ExecutionScheduleCreate(
                schedule_id=payload.schedule_id,
                target_kind=payload.target_kind,
                target_ref=payload.target_ref,
                cron_expression=payload.cron_expression,
                timezone=payload.timezone,
                enabled=payload.enabled,
                max_concurrency=payload.max_concurrency,
            )
        )
        return {"execution_schedule": _to_jsonable(schedule)}

    @app.get("/control/source-lineage")
    async def get_source_lineage(
        run_id: str | None = None,
        target_layer: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "lineage": _to_jsonable(
                resolved_config_repository.list_source_lineage(
                    input_run_id=run_id,
                    target_layer=target_layer,
                )
            )
        }

    @app.get("/control/publication-audit")
    async def get_publication_audit(
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "publication_audit": _to_jsonable(
                resolved_config_repository.list_publication_audit(
                    run_id=run_id,
                    publication_key=publication_key,
                )
            )
        }

    @app.get("/control/schedule-dispatches")
    async def list_schedule_dispatches(
        schedule_id: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "dispatches": _to_jsonable(
                resolved_config_repository.list_schedule_dispatches(
                    schedule_id=schedule_id,
                    status=status,
                )
            )
        }

    @app.post("/landing/{extension_key}", status_code=201)
    async def run_landing_extension(
        extension_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        require_unsafe_admin()
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
            request,
            service,
            transformation_service,
            resolved_reporting_service,
        )

    @app.post("/ingest/account-transactions", status_code=201)
    async def ingest_account_transactions_alias(request: Request) -> JSONResponse:
        return await _handle_account_transaction_ingest(
            request,
            service,
            transformation_service,
            resolved_reporting_service,
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
                    extension_registry=registry,
                )
                publish_reporting(promotion)
        return _build_run_response(run, promotion=promotion)

    @app.post("/ingest/subscriptions", status_code=201)
    async def ingest_subscriptions(request: Request) -> JSONResponse:
        if subscription_service is None:
            raise KeyError("subscription ingestion is not configured")
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = _require_upload(form.get("file"))
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
            publish_reporting(promotion)
        body: dict[str, Any] = {"run": serialize_run(run)}
        if promotion is not None:
            body["promotion"] = serialize_promotion(promotion)
        _observe_ingest_run(run)
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
            upload = _require_upload(form.get("file"))
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
            publish_reporting(promotion)
        body: dict[str, Any] = {"run": serialize_run(run)}
        if promotion is not None:
            body["promotion"] = serialize_promotion(promotion)
        _observe_ingest_run(run)
        status_code = 409 if any(i.code == "duplicate_file" for i in run.issues) else (
            201 if run.passed else 400
        )
        return JSONResponse(status_code=status_code, content=body)

    @app.post("/ingest/ingestion-definitions/{ingestion_definition_id}/process", status_code=201)
    async def process_ingestion_definition(ingestion_definition_id: str) -> dict[str, Any]:
        require_unsafe_admin()
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
            promotions = [
                promote_source_asset_run(
                    run_id,
                    source_asset=source_asset,
                    config_repository=resolved_config_repository,
                    landing_root=service.landing_root,
                    metadata_repository=service.metadata_repository,
                    transformation_service=transformation_service,
                    blob_store=service.blob_store,
                    extension_registry=registry,
                )
                for run_id in result.run_ids
            ]
            for promotion in promotions:
                publish_reporting(promotion)
            body["promotions"] = _to_jsonable(promotions)
        return body

    @app.get("/transformations/{extension_key}")
    async def run_transformation_extension(
        extension_key: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
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
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Monthly cashflow reporting requires a transformation service.",
            )
        rows = resolved_reporting_service.get_monthly_cashflow(
            from_month=from_month,
            to_month=to_month,
        )
        return {
            "rows": _to_jsonable(rows),
            "from_month": from_month,
            "to_month": to_month,
        }

    @app.get("/reports/utility-cost-summary")
    async def get_utility_cost_summary(
        utility_type: str | None = None,
        meter_id: str | None = None,
        from_period: date | None = None,
        to_period: date | None = None,
        granularity: str = "month",
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Utility cost reporting requires a transformation service.",
            )
        rows = resolved_reporting_service.get_utility_cost_summary(
            utility_type=utility_type,
            meter_id=meter_id,
            from_period=from_period,
            to_period=to_period,
            granularity=granularity,
        )
        return {
            "rows": _to_jsonable(rows),
            "utility_type": utility_type,
            "meter_id": meter_id,
            "from_period": from_period.isoformat() if from_period else None,
            "to_period": to_period.isoformat() if to_period else None,
            "granularity": granularity,
        }

    @app.get("/reports/current-dimensions/{dimension_name}")
    async def get_current_dimension_report(dimension_name: str) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Current-dimension reporting is not configured.",
            )
        return {
            "dimension": dimension_name,
            "rows": _to_jsonable(
                resolved_reporting_service.get_current_dimension_rows(dimension_name)
            ),
        }

    @app.get("/reports/monthly-cashflow-by-counterparty")
    async def get_monthly_cashflow_by_counterparty(
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Counterparty cashflow reporting requires a transformation service.",
            )
        rows = resolved_reporting_service.get_monthly_cashflow_by_counterparty(
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
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Subscription reporting requires a transformation service.",
            )
        return {
            "rows": _to_jsonable(
                resolved_reporting_service.get_subscription_summary(
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
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Contract-price reporting requires a transformation service.",
            )
        return {
            "rows": _to_jsonable(
                resolved_reporting_service.get_contract_price_current(
                    contract_type=contract_type,
                    status=status,
                )
            ),
            "contract_type": contract_type,
            "status": status,
        }

    @app.get("/reports/electricity-prices")
    async def get_electricity_price_current() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Electricity price reporting requires a transformation service.",
            )
        return {
            "rows": _to_jsonable(
                resolved_reporting_service.get_electricity_price_current()
            )
        }

    @app.get("/transformation-audit")
    async def get_transformation_audit(run_id: str | None = None) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Transformation audit requires a transformation service.",
            )
        records = resolved_reporting_service.get_transformation_audit(input_run_id=run_id)
        return {"audit": _to_jsonable(records)}

    @app.get("/reports/{extension_key}")
    async def run_reporting_extension(
        extension_key: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")
        extension = registry.get_extension("reporting", extension_key)
        if extension.data_access == "published" and resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Reporting extension requires a reporting service.",
            )
        if extension.data_access == "warehouse" and transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Reporting extension requires a transformation service.",
            )
        result = registry.execute(
            "reporting",
            extension_key,
            service=service,
            reporting_service=resolved_reporting_service,
            transformation_service=transformation_service,
            run_id=run_id,
        )
        return {"result": _to_jsonable(result)}

    return app


async def _handle_account_transaction_ingest(
    request: Request,
    service: AccountTransactionService,
    transformation_service: TransformationService | None = None,
    reporting_service: ReportingService | None = None,
) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = _require_upload(form.get("file"))
        source_name = str(form.get("source_name") or "manual-upload")
        source_bytes = await upload.read()
        await upload.close()
        run = service.ingest_bytes(
            source_bytes=source_bytes,
            file_name=upload.filename or "upload.csv",
            source_name=source_name,
        )
        return _build_ingest_response(
            run,
            service,
            transformation_service,
            reporting_service,
        )

    payload = await request.json()
    run = service.ingest_file(
        Path(payload["source_path"]),
        source_name=payload.get("source_name", "manual-upload"),
    )
    return _build_ingest_response(
        run,
        service,
        transformation_service,
        reporting_service,
    )


def _build_ingest_response(
    run: IngestionRunRecord,
    service: AccountTransactionService,
    transformation_service: TransformationService | None,
    reporting_service: ReportingService | None,
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
        publish_promotion_reporting(reporting_service, promotion)
    return _build_run_response(run, promotion=promotion)


def _build_run_response(
    run: IngestionRunRecord,
    *,
    promotion: PromotionResult | None = None,
) -> JSONResponse:
    _observe_ingest_run(run)
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


def _observe_ingest_run(run: IngestionRunRecord) -> None:
    metrics_registry.inc(
        "ingestion_runs_total",
        1,
        help_text="Total ingestion runs observed by the API.",
    )
    if not run.passed:
        metrics_registry.inc(
            "ingestion_failures_total",
            1,
            help_text="Total failed or rejected ingestion runs observed by the API.",
        )


def request_principal_from_user(user) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
    )


def _log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    started: float,
) -> None:
    logger.info(
        "request handled",
        extra={
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )


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


def _require_upload(value: object) -> UploadFile:
    if not isinstance(value, UploadFile):
        raise ValueError("multipart request must include file")
    return value


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
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
