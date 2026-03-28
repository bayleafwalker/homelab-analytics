from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Union, cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from apps.api.auth_runtime import (
    build_auth_event_recorder,
    build_lockout_checker,
    cookie_secure_for_request,
    register_auth_middleware,
)
from apps.api.routes.auth_routes import register_auth_routes
from apps.api.routes.category_routes import register_category_routes
from apps.api.routes.config_routes import register_config_routes
from apps.api.routes.contract_routes import register_contract_routes
from apps.api.routes.control_routes import register_control_routes
from apps.api.routes.control_terminal_routes import register_control_terminal_routes
from apps.api.routes.ha_routes import register_ha_routes
from apps.api.routes.homelab_routes import register_homelab_routes
from apps.api.routes.ingest_routes import register_ingest_routes
from apps.api.routes.report_routes import register_report_routes
from apps.api.routes.run_routes import register_run_routes
from apps.api.routes.scenario_routes import register_scenario_routes
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
from packages.application.use_cases.run_recovery import build_run_recovery
from packages.domains.finance.manifest import FINANCE_PACK
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.ha_action_proposals import ApprovalActionRegistry
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
from packages.platform.auth.break_glass import BreakGlassController
from packages.platform.auth.machine_jwt_provider import MachineJwtProvider
from packages.platform.auth.oidc_provider import OidcProvider
from packages.platform.auth.proxy_provider import ProxyProvider
from packages.platform.auth.session_manager import SessionManager
from packages.platform.runtime.container import AppContainer
from packages.shared.auth_modes import (
    is_cookie_auth_mode,
    normalize_auth_mode,
    normalize_identity_mode,
)
from packages.shared.extensions import (
    ExtensionRegistry,
    build_builtin_extension_registry,
)
from packages.shared.function_registry import FunctionRegistry
from packages.shared.metrics import metrics_registry
from packages.shared.settings import AppSettings
from packages.storage.auth_store import AuthStore
from packages.storage.control_plane import ControlPlaneStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import IngestionRunRecord


def _initialize_metrics() -> None:
    """Pre-declare all Prometheus counters/gauges so /metrics renders at cold start."""
    metrics_registry.inc("ingestion_runs_total", 0, help_text="Total ingestion runs observed by the API.")
    metrics_registry.inc("ingestion_failures_total", 0, help_text="Total failed or rejected ingestion runs observed by the API.")
    metrics_registry.inc("ingestion_duration_seconds", 0, help_text="Cumulative ingestion handling duration in seconds.")
    metrics_registry.set("worker_queue_depth", 0, help_text="Current queued schedule-dispatch count.")
    metrics_registry.set("worker_running_dispatches", 0, help_text="Current running schedule-dispatch count.")
    metrics_registry.set("worker_failed_dispatches", 0, help_text="Current failed schedule-dispatch count.")
    metrics_registry.set("worker_stale_dispatches", 0, help_text="Current running schedule-dispatch count with expired claims.")
    metrics_registry.set("worker_recovered_dispatches", 0, help_text="Current recovered schedule-dispatch count in control-plane history.")
    metrics_registry.set("worker_active_workers", 0, help_text="Current worker heartbeat count.")
    metrics_registry.set("worker_oldest_heartbeat_age_seconds", 0, help_text="Age in seconds of the oldest recorded worker heartbeat.")
    metrics_registry.set("worker_failed_dispatch_ratio", 0, help_text="Failed dispatches divided by total terminal dispatches.")
    metrics_registry.inc("auth_failures_total", 0, help_text="Total failed login attempts observed by the API.")
    metrics_registry.inc("auth_lockouts_total", 0, help_text="Total login lockouts observed by the API.")
    metrics_registry.inc(
        "auth_legacy_mode_fallback_startups_total",
        0,
        help_text=(
            "Total startup validations that relied on legacy "
            "HOMELAB_ANALYTICS_AUTH_MODE fallback instead of explicit "
            "HOMELAB_ANALYTICS_IDENTITY_MODE."
        ),
    )
    metrics_registry.inc(
        "auth_machine_jwt_authenticated_requests_total",
        0,
        help_text=(
            "Total successfully authenticated machine-JWT bearer requests "
            "observed by this API process."
        ),
    )
    metrics_registry.inc(
        "auth_machine_jwt_failed_requests_total",
        0,
        help_text=(
            "Total rejected machine-JWT bearer requests observed by this API process."
        ),
    )


def ensure_matching_identifier(
    resource_name: str,
    path_value: str,
    body_value: str,
) -> None:
    """Raise 400 if a request body identifier does not match its URL path segment."""
    if path_value != body_value:
        raise HTTPException(
            status_code=400,
            detail=f"{resource_name} in the request body must match the path.",
        )


def _load_run_manifest_and_context(
    run: IngestionRunRecord,
    *,
    blob_store: Any,
    logger: logging.Logger,
) -> tuple[dict[str, Any] | None, RunControlContext | None]:
    """Read a run's manifest from blob storage and parse its control context."""
    try:
        manifest = read_run_manifest(blob_store, run.manifest_path)
    except (KeyError, OSError, ValueError) as exc:
        logger.warning(
            "run manifest unavailable",
            extra={"run_id": run.run_id, "manifest_path": run.manifest_path, "error": str(exc)},
        )
        return None, None
    return manifest, run_context_from_manifest(manifest)


def _build_run_recovery_payload(
    run: IngestionRunRecord,
    context: RunControlContext | None,
) -> dict[str, Any]:
    return build_run_recovery(
        run,
        context,
        has_subscription_service=True,
        has_contract_price_service=True,
    )


def _register_exception_handlers(app: FastAPI) -> None:
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


def _register_base_routes(
    app: FastAPI,
    *,
    identity_mode: str,
    break_glass_controller: BreakGlassController | None,
    config_repository: ControlPlaneStore,
) -> None:
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ready",
            "identity_mode": identity_mode,
        }
        if break_glass_controller is not None:
            status = break_glass_controller.status()
            payload["break_glass"] = {
                "enabled": status.enabled,
                "internal_only": status.internal_only,
                "ttl_minutes": status.ttl_minutes,
                "allowed_cidrs": list(status.allowed_cidrs),
                "active": status.active,
                "active_until": status.active_until,
            }
        return payload

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        update_worker_runtime_metrics(config_repository)
        update_auth_runtime_metrics(config_repository)
        return PlainTextResponse(
            metrics_registry.render_prometheus_text(),
            media_type="text/plain; version=0.0.4",
        )


def _build_container_from_legacy_args(
    service: AccountTransactionService,
    *,
    extension_registry: ExtensionRegistry | None,
    config_repository: ControlPlaneStore | None,
    function_registry: FunctionRegistry | None,
    promotion_handler_registry: PromotionHandlerRegistry | None,
    subscription_service: SubscriptionService | None,
    contract_price_service: ContractPriceService | None,
) -> AppContainer:
    """Build a minimal AppContainer from the old-style create_app() positional/keyword args.

    Used for test compatibility — tests that call create_app() with the legacy
    AccountTransactionService + keyword args signature will continue to work
    without changes.
    """
    from packages.pipelines.configured_ingestion_definition import (
        ConfiguredIngestionDefinitionService,
    )
    from packages.pipelines.extension_registries import load_pipeline_registries

    resolved_config_repository = config_repository or IngestionConfigRepository(
        service.landing_root.parent / "config.db"
    )
    resolved_extension_registry = extension_registry or build_builtin_extension_registry()
    resolved_function_registry = function_registry or FunctionRegistry()
    resolved_promotion_handler_registry = (
        promotion_handler_registry or get_default_promotion_handler_registry()
    )
    # Preserve None to keep the old behaviour of returning 404 when these
    # services were not explicitly configured.
    resolved_subscription_service = subscription_service
    resolved_contract_price_service = contract_price_service
    resolved_configured_definition_service = ConfiguredIngestionDefinitionService(
        landing_root=service.landing_root,
        metadata_repository=service.metadata_repository,
        config_repository=resolved_config_repository,
        blob_store=service.blob_store,
        function_registry=resolved_function_registry,
    )
    # Minimal registries for legacy call paths (no extension loading from paths)
    pipeline_registries = load_pipeline_registries()
    data_dir = service.landing_root.parent
    settings = AppSettings(
        data_dir=data_dir,
        landing_root=service.landing_root,
        metadata_database_path=data_dir / "metadata" / "runs.db",
        account_transactions_inbox_dir=data_dir / "inbox",
        processed_files_dir=data_dir / "processed",
        failed_files_dir=data_dir / "failed",
        api_host="localhost",
        api_port=8080,
        web_host="localhost",
        web_port=8081,
        worker_poll_interval_seconds=60,
    )
    return AppContainer(
        settings=settings,
        blob_store=service.blob_store,
        control_plane_store=resolved_config_repository,
        run_metadata_store=service.metadata_repository,
        extension_registry=resolved_extension_registry,
        function_registry=resolved_function_registry,
        promotion_handler_registry=resolved_promotion_handler_registry,
        transformation_domain_registry=pipeline_registries.transformation_domain_registry,
        publication_refresh_registry=pipeline_registries.publication_refresh_registry,
        pipeline_catalog_registry=pipeline_registries.pipeline_catalog_registry,
        service=service,
        subscription_service=resolved_subscription_service,
        contract_price_service=resolved_contract_price_service,
        configured_definition_service=resolved_configured_definition_service,
        capability_packs=(FINANCE_PACK,),
        finance_pack=FINANCE_PACK,
    )


def create_app(
    service_or_container: Union[AppContainer, AccountTransactionService],
    extension_registry: ExtensionRegistry | None = None,
    config_repository: ControlPlaneStore | None = None,
    external_registry_cache_root: Path | None = None,
    function_registry: FunctionRegistry | None = None,
    transformation_service=None,
    reporting_service: ReportingService | None = None,
    promotion_handler_registry: PromotionHandlerRegistry | None = None,
    subscription_service: SubscriptionService | None = None,
    contract_price_service: ContractPriceService | None = None,
    auth_store: AuthStore | None = None,
    auth_mode: str = "disabled",
    identity_mode: str | None = None,
    session_manager: SessionManager | None = None,
    oidc_provider: OidcProvider | None = None,
    machine_jwt_provider: MachineJwtProvider | None = None,
    proxy_provider: ProxyProvider | None = None,
    auth_failure_window_seconds: int = 900,
    auth_failure_threshold: int = 5,
    auth_lockout_seconds: int = 900,
    enable_unsafe_admin: bool = False,
    ha_bridge: Any = None,
    ha_mqtt_publisher: Any = None,
    ha_policy_evaluator: Any = None,
    ha_action_dispatcher: Any = None,
    ha_action_proposal_registry: ApprovalActionRegistry | None = None,
) -> FastAPI:
    # Support both the new AppContainer-first call and the legacy
    # AccountTransactionService-first call from existing tests.
    if isinstance(service_or_container, AppContainer):
        container = service_or_container
        resolved_identity_mode = container.settings.resolved_identity_mode
        resolved_auth_mode = container.settings.resolved_auth_mode
    else:
        service = service_or_container
        container = _build_container_from_legacy_args(
            service,
            extension_registry=extension_registry,
            config_repository=config_repository,
            function_registry=function_registry,
            promotion_handler_registry=promotion_handler_registry,
            subscription_service=subscription_service,
            contract_price_service=contract_price_service,
        )
        resolved_identity_mode = normalize_identity_mode(
            identity_mode or auth_mode
        )
        resolved_auth_mode = normalize_auth_mode(resolved_identity_mode)

    # Auto-build a reporting service from transformation_service when reporting_service
    # was not explicitly provided — preserves the behaviour of the original create_app().
    if reporting_service is None and transformation_service is not None:
        reporting_service = ReportingService(
            transformation_service,
            extension_registry=container.extension_registry,
        )

    resolved_config_repository = container.control_plane_store
    resolved_external_registry_cache_root = external_registry_cache_root or (
        container.settings.landing_root.parent / "external-registry-cache"
    )

    if is_cookie_auth_mode(resolved_auth_mode) and session_manager is None:
        raise ValueError("Cookie-backed auth requires a configured session manager.")
    if resolved_auth_mode == "oidc" and oidc_provider is None:
        raise ValueError("OIDC auth requires a configured OIDC provider.")
    if resolved_auth_mode == "proxy" and proxy_provider is None:
        raise ValueError("Proxy auth requires a configured proxy provider.")

    resolved_auth_store_candidate = auth_store or resolved_config_repository
    if is_cookie_auth_mode(resolved_auth_mode) and not isinstance(
        resolved_auth_store_candidate, AuthStore
    ):
        raise ValueError("Configured auth requires an auth-capable control-plane store.")
    resolved_auth_store = cast(AuthStore, resolved_auth_store_candidate)
    break_glass_controller = (
        BreakGlassController.from_settings(container.settings)
        if (
            resolved_identity_mode == "local_single_user"
            and isinstance(service_or_container, AppContainer)
        )
        else None
    )

    configured_ingestion_service = ConfiguredCsvIngestionService(
        landing_root=container.settings.landing_root,
        metadata_repository=container.run_metadata_store,
        config_repository=resolved_config_repository,
        blob_store=container.blob_store,
        function_registry=container.function_registry,
    )

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        if ha_bridge is not None:
            ha_bridge.start()
        if ha_mqtt_publisher is not None:
            ha_mqtt_publisher.start()
        yield
        if ha_bridge is not None:
            await ha_bridge.stop()
        if ha_mqtt_publisher is not None:
            await ha_mqtt_publisher.stop()

    app = FastAPI(title="Homelab Analytics API", lifespan=_lifespan)
    logger = logging.getLogger("homelab_analytics.api")
    record_auth_event = build_auth_event_recorder(resolved_config_repository)
    locked_out_until = build_lockout_checker(
        resolved_config_repository,
        auth_failure_window_seconds=auth_failure_window_seconds,
        auth_failure_threshold=auth_failure_threshold,
        auth_lockout_seconds=auth_lockout_seconds,
    )

    _initialize_metrics()

    def require_unsafe_admin() -> None:
        if resolved_auth_mode != "disabled":
            return
        if not enable_unsafe_admin:
            raise HTTPException(
                status_code=404,
                detail="Unsafe admin routes are disabled until authentication is implemented.",
            )

    def publish_reporting(promotion: PromotionResult | None) -> None:
        publish_promotion_reporting(reporting_service, promotion)

    def load_run_manifest_and_context(
        run: IngestionRunRecord,
    ) -> tuple[dict[str, Any] | None, RunControlContext | None]:
        return _load_run_manifest_and_context(run, blob_store=container.blob_store, logger=logger)

    def serialize_run_detail(run: IngestionRunRecord) -> dict[str, Any]:
        _, context = load_run_manifest_and_context(run)
        return serialize_run(run, context=context, recovery=_build_run_recovery_payload(run, context))

    register_auth_middleware(
        app,
        logger=logger,
        resolved_auth_mode=resolved_auth_mode,
        resolved_identity_mode=resolved_identity_mode,
        resolved_auth_store=resolved_auth_store,
        resolved_session_manager=session_manager,
        resolved_oidc_provider=oidc_provider,
        resolved_machine_jwt_provider=machine_jwt_provider,
        resolved_proxy_provider=proxy_provider,
        enable_unsafe_admin=enable_unsafe_admin,
        break_glass_controller=break_glass_controller,
        record_auth_event=record_auth_event,
    )
    _register_exception_handlers(app)
    _register_base_routes(
        app,
        identity_mode=resolved_identity_mode,
        break_glass_controller=break_glass_controller,
        config_repository=resolved_config_repository,
    )

    register_auth_routes(
        app,
        resolved_auth_mode=resolved_auth_mode,
        resolved_identity_mode=resolved_identity_mode,
        resolved_auth_store=resolved_auth_store,
        resolved_config_repository=resolved_config_repository,
        resolved_session_manager=session_manager,
        resolved_oidc_provider=oidc_provider,
        require_unsafe_admin=require_unsafe_admin,
        cookie_secure_for_request=cookie_secure_for_request,
        break_glass_controller=break_glass_controller,
        record_auth_event=record_auth_event,
        locked_out_until=locked_out_until,
        request_principal_from_user=request_principal_from_user,
        to_jsonable=to_jsonable,
    )

    register_run_routes(
        app,
        service=container.service,
        configured_ingestion_service=configured_ingestion_service,
        resolved_config_repository=resolved_config_repository,
        transformation_service=transformation_service,
        resolved_reporting_service=reporting_service,
        subscription_service=container.subscription_service,
        contract_price_service=container.contract_price_service,
        registry=container.extension_registry,
        promotion_handler_registry=container.promotion_handler_registry,
        load_run_manifest_and_context=load_run_manifest_and_context,
        build_run_recovery=_build_run_recovery_payload,
        serialize_run=serialize_run,
        serialize_run_detail=serialize_run_detail,
        build_run_response=build_run_response,
        build_ingest_response=build_ingest_response,
        publish_reporting=publish_reporting,
    )
    register_config_routes(
        app,
        registry=container.extension_registry,
        function_registry=container.function_registry,
        promotion_handler_registry=container.promotion_handler_registry,
        resolved_config_repository=resolved_config_repository,
        external_registry_cache_root=resolved_external_registry_cache_root,
        configured_ingestion_service=configured_ingestion_service,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=to_jsonable,
        build_dataset_contract_diff=build_dataset_contract_diff,
        build_column_mapping_diff=build_column_mapping_diff,
    )
    register_contract_routes(
        app,
        capability_packs=container.capability_packs,
        extension_registry=container.extension_registry,
    )
    register_control_routes(
        app,
        service=container.service,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        serialize_run_detail=serialize_run_detail,
        build_operational_summary=lambda: build_runtime_operational_summary(
            service=container.service,
            config_repository=resolved_config_repository,
            load_run_manifest_and_context=load_run_manifest_and_context,
            build_run_recovery=_build_run_recovery_payload,
        ),
        to_jsonable=to_jsonable,
    )
    register_control_terminal_routes(
        app,
        service=container.service,
        resolved_config_repository=resolved_config_repository,
        extension_registry=container.extension_registry,
        function_registry=container.function_registry,
        promotion_handler_registry=container.promotion_handler_registry,
        require_unsafe_admin=require_unsafe_admin,
        build_operational_summary=lambda: build_runtime_operational_summary(
            service=container.service,
            config_repository=resolved_config_repository,
            load_run_manifest_and_context=load_run_manifest_and_context,
            build_run_recovery=_build_run_recovery_payload,
        ),
        record_auth_event=record_auth_event,
        to_jsonable=to_jsonable,
    )
    register_report_routes(
        app,
        service=container.service,
        registry=container.extension_registry,
        transformation_service=transformation_service,
        resolved_reporting_service=reporting_service,
        to_jsonable=to_jsonable,
    )
    register_homelab_routes(
        app,
        transformation_service=transformation_service,
        resolved_reporting_service=reporting_service,
        to_jsonable=to_jsonable,
    )
    register_category_routes(
        app,
        transformation_service=transformation_service,
        to_jsonable=to_jsonable,
    )
    register_ingest_routes(
        app,
        service=container.service,
        registry=container.extension_registry,
        configured_ingestion_service=configured_ingestion_service,
        configured_definition_service=container.configured_definition_service,
        resolved_config_repository=resolved_config_repository,
        transformation_service=transformation_service,
        resolved_reporting_service=reporting_service,
        subscription_service=container.subscription_service,
        contract_price_service=container.contract_price_service,
        require_unsafe_admin=require_unsafe_admin,
        promotion_handler_registry=container.promotion_handler_registry,
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
    register_scenario_routes(
        app,
        transformation_service=transformation_service,
        to_jsonable=to_jsonable,
    )
    register_ha_routes(
        app,
        transformation_service=transformation_service,
        ha_bridge=ha_bridge,
        ha_mqtt_publisher=ha_mqtt_publisher,
        ha_policy_evaluator=ha_policy_evaluator,
        ha_action_dispatcher=ha_action_dispatcher,
        ha_action_proposal_registry=ha_action_proposal_registry,
        to_jsonable=to_jsonable,
    )

    return app
