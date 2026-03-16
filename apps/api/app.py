from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from apps.api.auth_runtime import (
    build_auth_event_recorder,
    build_lockout_checker,
    cookie_secure_for_request,
    register_auth_middleware,
)
from apps.api.routes.auth_routes import register_auth_routes
from apps.api.routes.config_routes import register_config_routes
from apps.api.routes.control_routes import register_control_routes
from apps.api.routes.ingest_routes import register_ingest_routes
from apps.api.routes.report_routes import register_report_routes
from apps.api.routes.run_routes import register_run_routes
from apps.api.runtime_state import (
    build_operational_summary as build_runtime_operational_summary,
)
from apps.api.runtime_state import (
    update_auth_runtime_metrics,
    update_worker_runtime_metrics,
)
from apps.api.support import (
    build_column_mapping_diff,
    build_dataset_contract_diff,
    build_ingest_response,
    build_run_response,
    request_principal_from_user,
    require_upload,
    resolve_configured_ingest_binding,
    serialize_promotion,
    serialize_run,
    to_jsonable,
)
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.promotion import (
    PromotionResult,
)
from packages.pipelines.promotion_registry import (
    PromotionHandlerRegistry,
    get_default_promotion_handler_registry,
)
from packages.pipelines.reporting_service import (
    ReportingService,
    publish_promotion_reporting,
)
from packages.pipelines.run_context import (
    RunControlContext,
    read_run_manifest,
    run_context_from_manifest,
)
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.auth import (
    OidcProvider,
    SessionManager,
)
from packages.shared.extensions import (
    ExtensionRegistry,
    build_builtin_extension_registry,
)
from packages.shared.function_registry import FunctionRegistry
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import (
    AuthStore,
)
from packages.storage.control_plane import ControlPlaneStore
from packages.storage.ingestion_config import (
    IngestionConfigRepository,
)
from packages.storage.run_metadata import IngestionRunRecord


def create_app(
    service: AccountTransactionService,
    extension_registry: ExtensionRegistry | None = None,
    config_repository: ControlPlaneStore | None = None,
    external_registry_cache_root: Path | None = None,
    function_registry: FunctionRegistry | None = None,
    transformation_service: TransformationService | None = None,
    reporting_service: ReportingService | None = None,
    promotion_handler_registry: PromotionHandlerRegistry | None = None,
    subscription_service: SubscriptionService | None = None,
    contract_price_service: ContractPriceService | None = None,
    auth_store: AuthStore | None = None,
    auth_mode: str = "disabled",
    session_manager: SessionManager | None = None,
    oidc_provider: OidcProvider | None = None,
    auth_failure_window_seconds: int = 900,
    auth_failure_threshold: int = 5,
    auth_lockout_seconds: int = 900,
    enable_unsafe_admin: bool = False,
) -> FastAPI:
    registry = extension_registry or build_builtin_extension_registry()
    resolved_function_registry = function_registry or FunctionRegistry()
    resolved_promotion_handler_registry = (
        promotion_handler_registry or get_default_promotion_handler_registry()
    )
    resolved_config_repository = config_repository or IngestionConfigRepository(
        service.landing_root.parent / "config.db"
    )
    resolved_auth_store_candidate = auth_store or resolved_config_repository
    resolved_auth_mode = auth_mode.lower()
    if resolved_auth_mode not in {"disabled", "local", "oidc"}:
        raise ValueError(f"Unsupported auth mode: {auth_mode!r}")
    if resolved_auth_mode in {"local", "oidc"} and session_manager is None:
        raise ValueError("Cookie-backed auth requires a configured session manager.")
    if resolved_auth_mode == "oidc" and oidc_provider is None:
        raise ValueError("OIDC auth requires a configured OIDC provider.")
    if resolved_auth_mode in {"local", "oidc"} and not isinstance(
        resolved_auth_store_candidate, AuthStore
    ):
        raise ValueError("Configured auth requires an auth-capable control-plane store.")
    resolved_auth_store = cast(AuthStore, resolved_auth_store_candidate)
    resolved_session_manager = session_manager
    resolved_oidc_provider = oidc_provider
    configured_ingestion_service = ConfiguredCsvIngestionService(
        landing_root=service.landing_root,
        metadata_repository=service.metadata_repository,
        config_repository=resolved_config_repository,
        blob_store=service.blob_store,
        function_registry=resolved_function_registry,
    )
    configured_definition_service = ConfiguredIngestionDefinitionService(
        landing_root=service.landing_root,
        metadata_repository=service.metadata_repository,
        config_repository=resolved_config_repository,
        blob_store=service.blob_store,
        function_registry=resolved_function_registry,
    )
    resolved_reporting_service = reporting_service or (
        ReportingService(
            transformation_service,
            extension_registry=registry,
        )
        if transformation_service is not None
        else None
    )
    app = FastAPI(title="Homelab Analytics API")
    logger = logging.getLogger("homelab_analytics.api")
    record_auth_event = build_auth_event_recorder(resolved_config_repository)
    locked_out_until = build_lockout_checker(
        resolved_config_repository,
        auth_failure_window_seconds=auth_failure_window_seconds,
        auth_failure_threshold=auth_failure_threshold,
        auth_lockout_seconds=auth_lockout_seconds,
    )

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
    metrics_registry.set(
        "worker_running_dispatches",
        0,
        help_text="Current running schedule-dispatch count.",
    )
    metrics_registry.set(
        "worker_failed_dispatches",
        0,
        help_text="Current failed schedule-dispatch count.",
    )
    metrics_registry.set(
        "worker_stale_dispatches",
        0,
        help_text="Current running schedule-dispatch count with expired claims.",
    )
    metrics_registry.set(
        "worker_recovered_dispatches",
        0,
        help_text="Current recovered schedule-dispatch count in control-plane history.",
    )
    metrics_registry.set(
        "worker_active_workers",
        0,
        help_text="Current worker heartbeat count.",
    )
    metrics_registry.set(
        "worker_oldest_heartbeat_age_seconds",
        0,
        help_text="Age in seconds of the oldest recorded worker heartbeat.",
    )
    metrics_registry.set(
        "worker_failed_dispatch_ratio",
        0,
        help_text="Failed dispatches divided by total terminal dispatches.",
    )
    metrics_registry.inc(
        "auth_failures_total",
        0,
        help_text="Total failed login attempts observed by the API.",
    )
    metrics_registry.inc(
        "auth_lockouts_total",
        0,
        help_text="Total login lockouts observed by the API.",
    )

    def require_unsafe_admin() -> None:
        if resolved_auth_mode in {"local", "oidc"}:
            return
        if not enable_unsafe_admin:
            raise HTTPException(
                status_code=404,
                detail="Unsafe admin routes are disabled until authentication is implemented.",
            )

    def ensure_matching_identifier(
        resource_name: str,
        path_value: str,
        body_value: str,
    ) -> None:
        if path_value != body_value:
            raise HTTPException(
                status_code=400,
                detail=f"{resource_name} in the request body must match the path.",
            )

    def publish_reporting(promotion: PromotionResult | None) -> None:
        publish_promotion_reporting(resolved_reporting_service, promotion)

    def load_run_manifest_and_context(
        run: IngestionRunRecord,
    ) -> tuple[dict[str, Any] | None, RunControlContext | None]:
        try:
            manifest = read_run_manifest(service.blob_store, run.manifest_path)
        except (KeyError, OSError, ValueError) as exc:
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

    def build_run_recovery(
        run: IngestionRunRecord,
        context: RunControlContext | None,
    ) -> dict[str, Any]:
        if (
            context is not None
            and context.source_system_id
            and context.dataset_contract_id
            and context.column_mapping_id
        ):
            return {
                "retry_supported": True,
                "retry_kind": "configured_csv",
                "reason": None,
            }
        if run.dataset_name == "account_transactions":
            return {
                "retry_supported": True,
                "retry_kind": "account_transactions",
                "reason": None,
            }
        if run.dataset_name == "subscriptions":
            return {
                "retry_supported": subscription_service is not None,
                "retry_kind": "subscriptions" if subscription_service is not None else None,
                "reason": (
                    None
                    if subscription_service is not None
                    else "Subscription retry is not configured in this API runtime."
                ),
            }
        if run.dataset_name == "contract_prices":
            return {
                "retry_supported": contract_price_service is not None,
                "retry_kind": "contract_prices" if contract_price_service is not None else None,
                "reason": (
                    None
                    if contract_price_service is not None
                    else "Contract-price retry is not configured in this API runtime."
                ),
            }
        return {
            "retry_supported": False,
            "retry_kind": None,
            "reason": (
                "Retry requires either a built-in dataset handler or saved configured-ingest"
                " binding context in the landing manifest."
            ),
        }

    def serialize_run_detail(run: IngestionRunRecord) -> dict[str, Any]:
        _, context = load_run_manifest_and_context(run)
        return serialize_run(
            run,
            context=context,
            recovery=build_run_recovery(run, context),
        )

    register_auth_middleware(
        app,
        logger=logger,
        resolved_auth_mode=resolved_auth_mode,
        resolved_auth_store=resolved_auth_store,
        resolved_session_manager=resolved_session_manager,
        resolved_oidc_provider=resolved_oidc_provider,
        enable_unsafe_admin=enable_unsafe_admin,
        record_auth_event=record_auth_event,
    )

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

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready", "auth_mode": resolved_auth_mode}

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        update_worker_runtime_metrics(resolved_config_repository)
        update_auth_runtime_metrics(resolved_config_repository)
        return PlainTextResponse(
            metrics_registry.render_prometheus_text(),
            media_type="text/plain; version=0.0.4",
        )

    register_auth_routes(
        app,
        resolved_auth_mode=resolved_auth_mode,
        resolved_auth_store=resolved_auth_store,
        resolved_config_repository=resolved_config_repository,
        resolved_session_manager=resolved_session_manager,
        resolved_oidc_provider=resolved_oidc_provider,
        require_unsafe_admin=require_unsafe_admin,
        cookie_secure_for_request=cookie_secure_for_request,
        record_auth_event=record_auth_event,
        locked_out_until=locked_out_until,
        request_principal_from_user=request_principal_from_user,
        to_jsonable=to_jsonable,
    )

    register_run_routes(
        app,
        service=service,
        configured_ingestion_service=configured_ingestion_service,
        resolved_config_repository=resolved_config_repository,
        transformation_service=transformation_service,
        resolved_reporting_service=resolved_reporting_service,
        subscription_service=subscription_service,
        contract_price_service=contract_price_service,
        registry=registry,
        promotion_handler_registry=resolved_promotion_handler_registry,
        load_run_manifest_and_context=load_run_manifest_and_context,
        build_run_recovery=build_run_recovery,
        serialize_run=serialize_run,
        serialize_run_detail=serialize_run_detail,
        build_run_response=build_run_response,
        build_ingest_response=build_ingest_response,
        publish_reporting=publish_reporting,
    )
    register_config_routes(
        app,
        registry=registry,
        function_registry=resolved_function_registry,
        promotion_handler_registry=resolved_promotion_handler_registry,
        resolved_config_repository=resolved_config_repository,
        external_registry_cache_root=(
            external_registry_cache_root
            or (service.landing_root.parent / "external-registry-cache")
        ),
        configured_ingestion_service=configured_ingestion_service,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=to_jsonable,
        build_dataset_contract_diff=build_dataset_contract_diff,
        build_column_mapping_diff=build_column_mapping_diff,
    )
    register_control_routes(
        app,
        service=service,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        serialize_run_detail=serialize_run_detail,
        build_operational_summary=lambda: build_runtime_operational_summary(
            service=service,
            config_repository=resolved_config_repository,
            load_run_manifest_and_context=load_run_manifest_and_context,
            build_run_recovery=build_run_recovery,
        ),
        to_jsonable=to_jsonable,
    )
    register_report_routes(
        app,
        service=service,
        registry=registry,
        transformation_service=transformation_service,
        resolved_reporting_service=resolved_reporting_service,
        to_jsonable=to_jsonable,
    )
    register_ingest_routes(
        app,
        service=service,
        registry=registry,
        configured_ingestion_service=configured_ingestion_service,
        configured_definition_service=configured_definition_service,
        resolved_config_repository=resolved_config_repository,
        transformation_service=transformation_service,
        resolved_reporting_service=resolved_reporting_service,
        subscription_service=subscription_service,
        contract_price_service=contract_price_service,
        require_unsafe_admin=require_unsafe_admin,
        promotion_handler_registry=resolved_promotion_handler_registry,
        publish_reporting=publish_reporting,
        resolve_configured_ingest_binding=lambda payload: resolve_configured_ingest_binding(
            payload,
            config_repository=resolved_config_repository,
        ),
        build_run_response=build_run_response,
        build_ingest_response=build_ingest_response,
        require_upload=require_upload,
        serialize_run=serialize_run,
        serialize_promotion=serialize_promotion,
        to_jsonable=to_jsonable,
    )

    return app
