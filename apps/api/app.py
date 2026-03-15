from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from apps.api.models import (
    ArchivedStateRequest,
    ColumnMappingPreviewRequest,
    ColumnMappingRequest,
    ConfiguredCsvIngestRequest,
    DatasetContractRequest,
    ExecutionScheduleRequest,
    IngestionDefinitionRequest,
    LocalUserCreateRequest,
    LocalUserPasswordResetRequest,
    LocalUserUpdateRequest,
    LoginRequest,
    PublicationDefinitionRequest,
    ScheduleDispatchRequest,
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
from packages.pipelines.run_context import (
    RunControlContext,
    merge_run_context,
    read_run_manifest,
    run_context_from_manifest,
)
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.auth import (
    AuthenticatedPrincipal,
    SessionManager,
    has_required_role,
    hash_password,
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
from packages.storage.auth_store import (
    AuthStore,
    LocalUserCreate,
    UserRole,
    normalize_username,
)
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    ControlPlaneStore,
    ExecutionScheduleCreate,
    ScheduleDispatchRecord,
)
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
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
    auth_failure_window_seconds: int = 900,
    auth_failure_threshold: int = 5,
    auth_lockout_seconds: int = 900,
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
        if resolved_auth_mode == "local":
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
                "retry_kind": "contract_prices"
                if contract_price_service is not None
                else None,
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

    def make_operational_stats() -> dict[str, Any]:
        return {
            "run_count": 0,
            "failed_run_count": 0,
            "last_run_id": None,
            "last_run_at": None,
            "last_run_status": None,
            "last_success_run_id": None,
            "last_success_at": None,
            "last_failure_run_id": None,
            "last_failure_at": None,
            "dispatch_count": 0,
            "enqueued_dispatch_count": 0,
            "running_dispatch_count": 0,
            "failed_dispatch_count": 0,
            "completed_dispatch_count": 0,
            "last_dispatch_id": None,
            "last_dispatch_at": None,
            "last_dispatch_status": None,
            "last_failed_dispatch_id": None,
            "last_failed_dispatch_at": None,
            "_last_run_at_dt": None,
            "_last_success_at_dt": None,
            "_last_failure_at_dt": None,
            "_last_dispatch_at_dt": None,
            "_last_failed_dispatch_at_dt": None,
        }

    def update_latest_timestamp(
        stats: dict[str, Any],
        *,
        marker_key: str,
        value: datetime,
        updates: dict[str, Any],
    ) -> None:
        current = stats.get(marker_key)
        if current is None or not isinstance(current, datetime) or value >= current:
            stats[marker_key] = value
            for key, update_value in updates.items():
                stats[key] = update_value

    def update_operational_run_stats(
        stats: dict[str, Any],
        run: IngestionRunRecord,
    ) -> None:
        stats["run_count"] += 1
        update_latest_timestamp(
            stats,
            marker_key="_last_run_at_dt",
            value=run.created_at,
            updates={
                "last_run_id": run.run_id,
                "last_run_at": run.created_at.isoformat(),
                "last_run_status": run.status.value,
            },
        )
        if run.passed:
            update_latest_timestamp(
                stats,
                marker_key="_last_success_at_dt",
                value=run.created_at,
                updates={
                    "last_success_run_id": run.run_id,
                    "last_success_at": run.created_at.isoformat(),
                },
            )
            return
        stats["failed_run_count"] += 1
        update_latest_timestamp(
            stats,
            marker_key="_last_failure_at_dt",
            value=run.created_at,
            updates={
                "last_failure_run_id": run.run_id,
                "last_failure_at": run.created_at.isoformat(),
            },
        )

    def update_operational_dispatch_stats(
        stats: dict[str, Any],
        dispatch: ScheduleDispatchRecord,
    ) -> None:
        stats["dispatch_count"] += 1
        dispatch_status_key = f"{dispatch.status}_dispatch_count"
        if dispatch_status_key in stats:
            stats[dispatch_status_key] += 1
        update_latest_timestamp(
            stats,
            marker_key="_last_dispatch_at_dt",
            value=dispatch.enqueued_at,
            updates={
                "last_dispatch_id": dispatch.dispatch_id,
                "last_dispatch_at": dispatch.enqueued_at.isoformat(),
                "last_dispatch_status": dispatch.status,
            },
        )
        if dispatch.status == "failed":
            failed_at = dispatch.completed_at or dispatch.enqueued_at
            update_latest_timestamp(
                stats,
                marker_key="_last_failed_dispatch_at_dt",
                value=failed_at,
                updates={
                    "last_failed_dispatch_id": dispatch.dispatch_id,
                    "last_failed_dispatch_at": failed_at.isoformat(),
                },
            )

    def finalize_operational_stats(
        stats_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        finalized: dict[str, dict[str, Any]] = {}
        for key, stats in stats_by_id.items():
            finalized[key] = {
                stat_key: value
                for stat_key, value in stats.items()
                if not stat_key.startswith("_")
            }
        return finalized

    def build_operational_summary() -> dict[str, Any]:
        source_assets = resolved_config_repository.list_source_assets(include_archived=True)
        dataset_contracts = resolved_config_repository.list_dataset_contracts(
            include_archived=True
        )
        column_mappings = resolved_config_repository.list_column_mappings(
            include_archived=True
        )
        ingestion_definitions = resolved_config_repository.list_ingestion_definitions(
            include_archived=True
        )
        execution_schedules = resolved_config_repository.list_execution_schedules(
            include_archived=True
        )
        source_asset_stats = {
            record.source_asset_id: make_operational_stats() for record in source_assets
        }
        dataset_contract_stats = {
            record.dataset_contract_id: make_operational_stats()
            for record in dataset_contracts
        }
        column_mapping_stats = {
            record.column_mapping_id: make_operational_stats()
            for record in column_mappings
        }
        ingestion_definition_stats = {
            record.ingestion_definition_id: make_operational_stats()
            for record in ingestion_definitions
        }
        execution_schedule_stats = {
            record.schedule_id: make_operational_stats() for record in execution_schedules
        }
        schedule_ids_by_target_ref: dict[str, list[str]] = {}
        for schedule in execution_schedules:
            if schedule.target_kind != "ingestion_definition":
                continue
            schedule_ids_by_target_ref.setdefault(schedule.target_ref, []).append(
                schedule.schedule_id
            )

        failed_runs: list[dict[str, Any]] = []
        for run in service.metadata_repository.list_runs(limit=None):
            _, context = load_run_manifest_and_context(run)
            if context is not None:
                if context.source_asset_id:
                    update_operational_run_stats(
                        source_asset_stats.setdefault(
                            context.source_asset_id,
                            make_operational_stats(),
                        ),
                        run,
                    )
                if context.dataset_contract_id:
                    update_operational_run_stats(
                        dataset_contract_stats.setdefault(
                            context.dataset_contract_id,
                            make_operational_stats(),
                        ),
                        run,
                    )
                if context.column_mapping_id:
                    update_operational_run_stats(
                        column_mapping_stats.setdefault(
                            context.column_mapping_id,
                            make_operational_stats(),
                        ),
                        run,
                    )
                if context.ingestion_definition_id:
                    update_operational_run_stats(
                        ingestion_definition_stats.setdefault(
                            context.ingestion_definition_id,
                            make_operational_stats(),
                        ),
                        run,
                    )
                    for schedule_id in schedule_ids_by_target_ref.get(
                        context.ingestion_definition_id,
                        [],
                    ):
                        update_operational_run_stats(
                            execution_schedule_stats.setdefault(
                                schedule_id,
                                make_operational_stats(),
                            ),
                            run,
                        )
            if not run.passed:
                failed_runs.append(
                    serialize_run(
                        run,
                        context=context,
                        recovery=build_run_recovery(run, context),
                    )
                )

        runtime_state = build_dispatch_runtime_state()
        dispatches = runtime_state["dispatches"]
        for dispatch in dispatches:
            update_operational_dispatch_stats(
                execution_schedule_stats.setdefault(
                    dispatch.schedule_id,
                    make_operational_stats(),
                ),
                dispatch,
            )

        return {
            "source_assets": finalize_operational_stats(source_asset_stats),
            "dataset_contracts": finalize_operational_stats(dataset_contract_stats),
            "column_mappings": finalize_operational_stats(column_mapping_stats),
            "ingestion_definitions": finalize_operational_stats(
                ingestion_definition_stats
            ),
            "execution_schedules": finalize_operational_stats(
                execution_schedule_stats
            ),
            "recent_failed_runs": failed_runs[:10],
            "recent_failed_dispatches": _to_jsonable(
                [
                    dispatch
                    for dispatch in dispatches
                    if dispatch.status == "failed"
                ][:10]
            ),
            "stale_running_dispatches": _to_jsonable(
                runtime_state["stale_dispatches"][:10]
            ),
            "recent_recovered_dispatches": _to_jsonable(
                runtime_state["recovered_dispatches"][:10]
            ),
            "workers": runtime_state["workers"],
            "queue": runtime_state["queue"],
        }

    def is_recovered_dispatch(dispatch) -> bool:
        failure_reason = getattr(dispatch, "failure_reason", None) or ""
        return failure_reason.startswith("Dispatch claim expired at ")

    def build_dispatch_runtime_state() -> dict[str, Any]:
        dispatches = resolved_config_repository.list_schedule_dispatches()
        dispatch_by_id = {dispatch.dispatch_id: dispatch for dispatch in dispatches}
        heartbeats = resolved_config_repository.list_worker_heartbeats()
        now = datetime.now(UTC)
        stale_dispatches = [
            dispatch
            for dispatch in dispatches
            if dispatch.status == "running"
            and dispatch.claim_expires_at is not None
            and dispatch.claim_expires_at < now
        ]
        recovered_dispatches = [
            dispatch for dispatch in dispatches if is_recovered_dispatch(dispatch)
        ]
        heartbeat_stale_after_seconds = 300
        workers: list[dict[str, Any]] = []
        for heartbeat in heartbeats:
            active_dispatch = (
                dispatch_by_id.get(heartbeat.active_dispatch_id)
                if heartbeat.active_dispatch_id is not None
                else None
            )
            heartbeat_age_seconds = max(
                0.0,
                (now - heartbeat.observed_at).total_seconds(),
            )
            workers.append(
                {
                    "worker_id": heartbeat.worker_id,
                    "status": heartbeat.status,
                    "active_dispatch_id": heartbeat.active_dispatch_id,
                    "active_dispatch_status": active_dispatch.status if active_dispatch else None,
                    "claim_expires_at": (
                        active_dispatch.claim_expires_at.isoformat()
                        if active_dispatch is not None
                        and active_dispatch.claim_expires_at is not None
                        else None
                    ),
                    "stale": bool(
                        active_dispatch is not None
                        and active_dispatch.claim_expires_at is not None
                        and active_dispatch.claim_expires_at < now
                    ),
                    "heartbeat_age_seconds": heartbeat_age_seconds,
                    "heartbeat_stale": heartbeat_age_seconds > heartbeat_stale_after_seconds,
                    "detail": heartbeat.detail,
                    "observed_at": heartbeat.observed_at.isoformat(),
                }
            )
        completed_dispatches = len(
            [dispatch for dispatch in dispatches if dispatch.status == "completed"]
        )
        failed_dispatches = len(
            [dispatch for dispatch in dispatches if dispatch.status == "failed"]
        )
        terminal_dispatches = completed_dispatches + failed_dispatches
        return {
            "dispatches": dispatches,
            "stale_dispatches": stale_dispatches,
            "recovered_dispatches": recovered_dispatches,
            "workers": workers,
            "queue": {
                "total_dispatches": len(dispatches),
                "enqueued_dispatches": len(
                    [dispatch for dispatch in dispatches if dispatch.status == "enqueued"]
                ),
                "running_dispatches": len(
                    [dispatch for dispatch in dispatches if dispatch.status == "running"]
                ),
                "completed_dispatches": completed_dispatches,
                "failed_dispatches": failed_dispatches,
                "stale_running_dispatches": len(stale_dispatches),
                "recovered_dispatches": len(recovered_dispatches),
                "active_workers": len(workers),
                "oldest_worker_heartbeat_age_seconds": max(
                    (worker["heartbeat_age_seconds"] for worker in workers),
                    default=0.0,
                ),
                "failed_dispatch_ratio": (
                    failed_dispatches / terminal_dispatches
                    if terminal_dispatches > 0
                    else 0.0
                ),
            },
        }

    def update_worker_runtime_metrics() -> None:
        runtime_state = build_dispatch_runtime_state()
        queue = runtime_state["queue"]
        metrics_registry.set(
            "worker_queue_depth",
            float(queue["enqueued_dispatches"]),
            help_text="Current queued schedule-dispatch count.",
        )
        metrics_registry.set(
            "worker_running_dispatches",
            float(queue["running_dispatches"]),
            help_text="Current running schedule-dispatch count.",
        )
        metrics_registry.set(
            "worker_failed_dispatches",
            float(queue["failed_dispatches"]),
            help_text="Current failed schedule-dispatch count.",
        )
        metrics_registry.set(
            "worker_stale_dispatches",
            float(queue["stale_running_dispatches"]),
            help_text="Current running schedule-dispatch count with expired claims.",
        )
        metrics_registry.set(
            "worker_recovered_dispatches",
            float(queue["recovered_dispatches"]),
            help_text="Current recovered schedule-dispatch count in control-plane history.",
        )
        metrics_registry.set(
            "worker_active_workers",
            float(queue["active_workers"]),
            help_text="Current worker heartbeat count.",
        )
        metrics_registry.set(
            "worker_oldest_heartbeat_age_seconds",
            float(queue["oldest_worker_heartbeat_age_seconds"]),
            help_text="Age in seconds of the oldest recorded worker heartbeat.",
        )
        metrics_registry.set(
            "worker_failed_dispatch_ratio",
            float(queue["failed_dispatch_ratio"]),
            help_text="Failed dispatches divided by total terminal dispatches.",
        )

    def request_remote_addr(request: Request) -> str | None:
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for:
            return forwarded_for.split(",")[0].strip() or None
        if request.client is None:
            return None
        return request.client.host

    def cookie_secure_for_request(request: Request) -> bool:
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if forwarded_proto:
            return forwarded_proto.split(",")[0].strip().lower() == "https"
        return request.url.scheme.lower() == "https"

    def record_auth_event(
        request: Request,
        *,
        event_type: str,
        success: bool,
        actor: AuthenticatedPrincipal | None = None,
        subject_user_id: str | None = None,
        subject_username: str | None = None,
        detail: str | None = None,
    ) -> None:
        resolved_config_repository.record_auth_audit_events(
            (
                AuthAuditEventCreate(
                    event_id=uuid.uuid4().hex,
                    event_type=event_type,
                    success=success,
                    actor_user_id=actor.user_id if actor else None,
                    actor_username=actor.username if actor else None,
                    subject_user_id=subject_user_id,
                    subject_username=subject_username,
                    remote_addr=request_remote_addr(request),
                    user_agent=request.headers.get("user-agent"),
                    detail=detail,
                ),
            )
        )

    def locked_out_until(username: str, now: datetime) -> datetime | None:
        recent_events = resolved_config_repository.list_auth_audit_events(
            subject_username=username,
            since=now - timedelta(seconds=auth_failure_window_seconds),
            limit=max(auth_failure_threshold * 4, 20),
        )
        consecutive_failures = 0
        latest_failure_at: datetime | None = None
        for event in recent_events:
            if event.event_type == "login_succeeded" and event.success:
                break
            if event.event_type not in {"login_failed", "login_blocked"}:
                continue
            if event.success:
                continue
            consecutive_failures += 1
            if latest_failure_at is None:
                latest_failure_at = event.occurred_at
        if (
            latest_failure_at is None
            or consecutive_failures < auth_failure_threshold
        ):
            return None
        candidate = latest_failure_at + timedelta(seconds=auth_lockout_seconds)
        if candidate <= now:
            return None
        return candidate

    def required_role_for_path(path: str) -> UserRole | None:
        if path in {"/health", "/metrics", "/auth/login", "/auth/logout"}:
            return None
        if path.startswith("/runs/") and path.endswith("/retry"):
            return UserRole.OPERATOR
        if path in {
            "/control/source-lineage",
            "/control/publication-audit",
            "/transformation-audit",
        }:
            return UserRole.READER
        if (
            path.startswith("/auth/users")
            or path == "/control/auth-audit"
            or path == "/control/schedule-dispatches"
            or path.startswith("/config/")
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
            if (
                request.state.principal is not None
                and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
            ):
                csrf_header = request.headers.get("x-csrf-token")
                csrf_cookie = request.cookies.get(resolved_session_manager.csrf_cookie_name)
                if (
                    request.state.principal.csrf_token is None
                    or csrf_cookie != request.state.principal.csrf_token
                    or csrf_header != request.state.principal.csrf_token
                ):
                    response = JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF validation failed."},
                    )
                    _log_request(logger, request.method, request.url.path, 403, started)
                    return response
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
        update_worker_runtime_metrics()
        return PlainTextResponse(
            metrics_registry.render_prometheus_text(),
            media_type="text/plain; version=0.0.4",
        )

    @app.post("/auth/login")
    async def login(request: Request, payload: LoginRequest) -> JSONResponse:
        if resolved_auth_mode != "local":
            raise HTTPException(
                status_code=400,
                detail="Local authentication is not enabled.",
            )
        normalized_username = normalize_username(payload.username)
        now = datetime.now(UTC)
        locked_until = locked_out_until(normalized_username, now)
        if locked_until is not None:
            metrics_registry.inc(
                "auth_lockouts_total",
                1,
                help_text="Total login lockouts observed by the API.",
            )
            record_auth_event(
                request,
                event_type="login_blocked",
                success=False,
                subject_username=normalized_username,
                detail=f"Locked out until {locked_until.isoformat()}",
            )
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Try again later.",
            )
        try:
            user = resolved_auth_store.get_local_user_by_username(normalized_username)
        except KeyError as exc:
            metrics_registry.inc(
                "auth_failures_total",
                1,
                help_text="Total failed login attempts observed by the API.",
            )
            record_auth_event(
                request,
                event_type="login_failed",
                success=False,
                subject_username=normalized_username,
                detail="Unknown username.",
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password.",
            ) from exc
        if not user.enabled or not verify_password(payload.password, user.password_hash):
            metrics_registry.inc(
                "auth_failures_total",
                1,
                help_text="Total failed login attempts observed by the API.",
            )
            record_auth_event(
                request,
                event_type="login_failed",
                success=False,
                subject_user_id=user.user_id,
                subject_username=user.username,
                detail="Invalid password or disabled user.",
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password.",
            )
        user = resolved_auth_store.record_local_user_login(user.user_id)
        assert resolved_session_manager is not None
        record_auth_event(
            request,
            event_type="login_succeeded",
            success=True,
            subject_user_id=user.user_id,
            subject_username=user.username,
        )
        issued_session = resolved_session_manager.issue_session(user)
        secure_cookie = cookie_secure_for_request(request)
        response = JSONResponse(
            {
                "auth_mode": "local",
                "authenticated": True,
                "user": serialize_user(user),
                "principal": serialize_principal(
                    request_principal_from_user(
                        user,
                        csrf_token=issued_session.csrf_token,
                    )
                ),
            }
        )
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(
            key=resolved_session_manager.cookie_name,
            value=issued_session.cookie_value,
            httponly=True,
            max_age=resolved_session_manager.max_age_seconds,
            expires=resolved_session_manager.max_age_seconds,
            path="/",
            samesite=resolved_session_manager.same_site,
            secure=secure_cookie,
        )
        response.set_cookie(
            key=resolved_session_manager.csrf_cookie_name,
            value=issued_session.csrf_token,
            httponly=False,
            max_age=resolved_session_manager.max_age_seconds,
            expires=resolved_session_manager.max_age_seconds,
            path="/",
            samesite=resolved_session_manager.same_site,
            secure=secure_cookie,
        )
        return response

    @app.post("/auth/logout")
    async def logout(request: Request) -> JSONResponse:
        response = JSONResponse({"logged_out": True})
        if resolved_session_manager is not None:
            principal = cast(
                AuthenticatedPrincipal | None,
                getattr(request.state, "principal", None),
            )
            if principal is not None:
                record_auth_event(
                    request,
                    event_type="logout",
                    success=True,
                    actor=principal,
                    subject_user_id=principal.user_id,
                    subject_username=principal.username,
                )
            secure_cookie = cookie_secure_for_request(request)
            response.delete_cookie(
                resolved_session_manager.cookie_name,
                path="/",
                httponly=True,
                samesite=resolved_session_manager.same_site,
                secure=secure_cookie,
            )
            response.delete_cookie(
                resolved_session_manager.csrf_cookie_name,
                path="/",
                httponly=False,
                samesite=resolved_session_manager.same_site,
                secure=secure_cookie,
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

    @app.get("/auth/users")
    async def list_auth_users() -> dict[str, Any]:
        require_unsafe_admin()
        return {"users": _to_jsonable(resolved_auth_store.list_local_users())}

    @app.post("/auth/users", status_code=201)
    async def create_auth_user(
        request: Request,
        payload: LocalUserCreateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        try:
            resolved_auth_store.get_local_user_by_username(payload.username)
        except KeyError:
            pass
        else:
            raise HTTPException(status_code=400, detail="Username already exists.")
        user = resolved_auth_store.create_local_user(
            LocalUserCreate(
                user_id=f"user-{uuid.uuid4().hex}",
                username=payload.username,
                password_hash=hash_password(payload.password),
                role=payload.role,
            )
        )
        record_auth_event(
            request,
            event_type="user_created",
            success=True,
            actor=principal,
            subject_user_id=user.user_id,
            subject_username=user.username,
            detail=f"Created role={user.role.value}",
        )
        return {"user": serialize_user(user)}

    @app.patch("/auth/users/{user_id}")
    async def update_auth_user(
        user_id: str,
        payload: LocalUserUpdateRequest,
        request: Request,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        if principal is not None and principal.user_id == user_id:
            if payload.enabled is False:
                raise HTTPException(
                    status_code=400,
                    detail="You cannot disable your current session user.",
                )
            if payload.role is not None and payload.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=400,
                    detail="You cannot remove the admin role from your current session user.",
                )
        user = resolved_auth_store.update_local_user(
            user_id,
            role=payload.role,
            enabled=payload.enabled,
        )
        record_auth_event(
            request,
            event_type="user_updated",
            success=True,
            actor=principal,
            subject_user_id=user.user_id,
            subject_username=user.username,
            detail=(
                f"Updated role={user.role.value} enabled={str(user.enabled).lower()}"
            ),
        )
        return {"user": serialize_user(user)}

    @app.post("/auth/users/{user_id}/password")
    async def reset_auth_user_password(
        user_id: str,
        payload: LocalUserPasswordResetRequest,
        request: Request,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        user = resolved_auth_store.update_local_user_password(
            user_id,
            password_hash=hash_password(payload.password),
        )
        record_auth_event(
            request,
            event_type="password_reset",
            success=True,
            actor=principal,
            subject_user_id=user.user_id,
            subject_username=user.username,
        )
        return {"user": serialize_user(user)}

    @app.get("/control/auth-audit")
    async def list_auth_audit(
        event_type: str | None = None,
        success: bool | None = None,
        subject_username: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "auth_audit_events": _to_jsonable(
                resolved_config_repository.list_auth_audit_events(
                    event_type=event_type,
                    success=success,
                    subject_username=subject_username,
                    limit=limit,
                )
            )
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
        return {"run": serialize_run_detail(service.get_run(run_id))}

    @app.post("/runs/{run_id}/retry")
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
                source_asset = resolved_config_repository.get_source_asset(
                    context.source_asset_id
                )
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
                resolved_source_asset = source_asset or resolved_config_repository.find_source_asset_by_binding(
                    source_system_id=context.source_system_id,
                    dataset_contract_id=context.dataset_contract_id,
                    column_mapping_id=context.column_mapping_id,
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
                    )
                    publish_reporting(promotion)
            return _build_run_response(retried_run, promotion=promotion)

        if retry_kind == "account_transactions":
            retried_run = service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=original_run.file_name,
                source_name=original_run.source_name,
                run_context=retry_context,
            )
            return _build_ingest_response(
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
            return _build_run_response(retried_run, promotion=promotion)

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
            return _build_run_response(retried_run, promotion=promotion)

        raise HTTPException(status_code=400, detail="Run retry is not supported.")

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
                enabled=payload.enabled,
            )
        )
        return {"source_system": _to_jsonable(source_system)}

    @app.patch("/config/source-systems/{source_system_id}")
    async def update_source_system(
        source_system_id: str,
        payload: SourceSystemRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier(
            "source_system_id",
            source_system_id,
            payload.source_system_id,
        )
        existing = resolved_config_repository.get_source_system(source_system_id)
        source_system = resolved_config_repository.update_source_system(
            SourceSystemCreate(
                source_system_id=payload.source_system_id,
                name=payload.name,
                source_type=payload.source_type,
                transport=payload.transport,
                schedule_mode=payload.schedule_mode,
                description=payload.description,
                enabled=payload.enabled,
                created_at=existing.created_at,
            )
        )
        return {"source_system": _to_jsonable(source_system)}

    @app.get("/config/dataset-contracts")
    async def list_dataset_contracts(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "dataset_contracts": _to_jsonable(
                resolved_config_repository.list_dataset_contracts(
                    include_archived=include_archived
                )
            )
        }

    @app.get("/config/dataset-contracts/{dataset_contract_id}")
    async def get_dataset_contract(dataset_contract_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "dataset_contract": _to_jsonable(
                resolved_config_repository.get_dataset_contract(dataset_contract_id)
            )
        }

    @app.get("/config/dataset-contracts/{dataset_contract_id}/diff")
    async def get_dataset_contract_diff(
        dataset_contract_id: str,
        other_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        left = resolved_config_repository.get_dataset_contract(dataset_contract_id)
        right = resolved_config_repository.get_dataset_contract(other_id)
        return {
            "diff": _build_dataset_contract_diff(
                left,
                right,
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

    @app.patch("/config/dataset-contracts/{dataset_contract_id}/archive")
    async def set_dataset_contract_archived_state(
        dataset_contract_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        dataset_contract = resolved_config_repository.set_dataset_contract_archived_state(
            dataset_contract_id,
            archived=payload.archived,
        )
        return {"dataset_contract": _to_jsonable(dataset_contract)}

    @app.get("/config/column-mappings")
    async def list_column_mappings(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "column_mappings": _to_jsonable(
                resolved_config_repository.list_column_mappings(
                    include_archived=include_archived
                )
            )
        }

    @app.get("/config/column-mappings/{column_mapping_id}")
    async def get_column_mapping(column_mapping_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "column_mapping": _to_jsonable(
                resolved_config_repository.get_column_mapping(column_mapping_id)
            )
        }

    @app.get("/config/column-mappings/{column_mapping_id}/diff")
    async def get_column_mapping_diff(
        column_mapping_id: str,
        other_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        left = resolved_config_repository.get_column_mapping(column_mapping_id)
        right = resolved_config_repository.get_column_mapping(other_id)
        return {"diff": _build_column_mapping_diff(left, right)}

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

    @app.patch("/config/column-mappings/{column_mapping_id}/archive")
    async def set_column_mapping_archived_state(
        column_mapping_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        column_mapping = resolved_config_repository.set_column_mapping_archived_state(
            column_mapping_id,
            archived=payload.archived,
        )
        return {"column_mapping": _to_jsonable(column_mapping)}

    @app.post("/config/column-mappings/preview")
    async def preview_column_mapping(
        payload: ColumnMappingPreviewRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        column_mapping = resolved_config_repository.get_column_mapping(
            payload.column_mapping_id
        )
        if column_mapping.dataset_contract_id != payload.dataset_contract_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Column mapping dataset contract does not match the requested preview contract."
                ),
            )
        preview = configured_ingestion_service.preview_mapping(
            source_bytes=payload.sample_csv.encode("utf-8"),
            source_system_id=column_mapping.source_system_id,
            dataset_contract_id=payload.dataset_contract_id,
            column_mapping_id=payload.column_mapping_id,
            preview_limit=payload.preview_limit,
        )
        return {"preview": _to_jsonable(preview)}

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
    async def list_source_assets(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "source_assets": _to_jsonable(
                resolved_config_repository.list_source_assets(
                    include_archived=include_archived
                )
            )
        }

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
                enabled=payload.enabled,
            )
        )
        return {"source_asset": _to_jsonable(source_asset)}

    @app.patch("/config/source-assets/{source_asset_id}")
    async def update_source_asset(
        source_asset_id: str,
        payload: SourceAssetRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier("source_asset_id", source_asset_id, payload.source_asset_id)
        existing = resolved_config_repository.get_source_asset(source_asset_id)
        source_asset = resolved_config_repository.update_source_asset(
            SourceAssetCreate(
                source_asset_id=payload.source_asset_id,
                source_system_id=payload.source_system_id,
                dataset_contract_id=payload.dataset_contract_id,
                column_mapping_id=payload.column_mapping_id,
                transformation_package_id=payload.transformation_package_id,
                name=payload.name,
                asset_type=payload.asset_type,
                description=payload.description,
                enabled=payload.enabled,
                archived=existing.archived,
                created_at=existing.created_at,
            )
        )
        return {"source_asset": _to_jsonable(source_asset)}

    @app.patch("/config/source-assets/{source_asset_id}/archive")
    async def set_source_asset_archived_state(
        source_asset_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        source_asset = resolved_config_repository.set_source_asset_archived_state(
            source_asset_id,
            archived=payload.archived,
        )
        return {"source_asset": _to_jsonable(source_asset)}

    @app.delete("/config/source-assets/{source_asset_id}", status_code=204)
    async def delete_source_asset(source_asset_id: str) -> None:
        require_unsafe_admin()
        resolved_config_repository.delete_source_asset(source_asset_id)

    @app.get("/config/ingestion-definitions")
    async def list_ingestion_definitions(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "ingestion_definitions": _to_jsonable(
                resolved_config_repository.list_ingestion_definitions(
                    include_archived=include_archived
                )
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

    @app.patch("/config/ingestion-definitions/{ingestion_definition_id}")
    async def update_ingestion_definition(
        ingestion_definition_id: str,
        payload: IngestionDefinitionRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier(
            "ingestion_definition_id",
            ingestion_definition_id,
            payload.ingestion_definition_id,
        )
        existing = resolved_config_repository.get_ingestion_definition(
            ingestion_definition_id
        )
        ingestion_definition = resolved_config_repository.update_ingestion_definition(
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
                archived=existing.archived,
                source_name=payload.source_name,
                created_at=existing.created_at,
            )
        )
        return {"ingestion_definition": _to_jsonable(ingestion_definition)}

    @app.patch("/config/ingestion-definitions/{ingestion_definition_id}/archive")
    async def set_ingestion_definition_archived_state(
        ingestion_definition_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ingestion_definition = (
            resolved_config_repository.set_ingestion_definition_archived_state(
                ingestion_definition_id,
                archived=payload.archived,
            )
        )
        return {"ingestion_definition": _to_jsonable(ingestion_definition)}

    @app.delete("/config/ingestion-definitions/{ingestion_definition_id}", status_code=204)
    async def delete_ingestion_definition(ingestion_definition_id: str) -> None:
        require_unsafe_admin()
        resolved_config_repository.delete_ingestion_definition(ingestion_definition_id)

    @app.get("/config/execution-schedules")
    async def list_execution_schedules(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "execution_schedules": _to_jsonable(
                resolved_config_repository.list_execution_schedules(
                    include_archived=include_archived
                )
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

    @app.patch("/config/execution-schedules/{schedule_id}")
    async def update_execution_schedule(
        schedule_id: str,
        payload: ExecutionScheduleRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        ensure_matching_identifier("schedule_id", schedule_id, payload.schedule_id)
        existing = resolved_config_repository.get_execution_schedule(schedule_id)
        schedule = resolved_config_repository.update_execution_schedule(
            ExecutionScheduleCreate(
                schedule_id=payload.schedule_id,
                target_kind=payload.target_kind,
                target_ref=payload.target_ref,
                cron_expression=payload.cron_expression,
                timezone=payload.timezone,
                enabled=payload.enabled,
                archived=existing.archived,
                max_concurrency=payload.max_concurrency,
                next_due_at=existing.next_due_at,
                last_enqueued_at=existing.last_enqueued_at,
                created_at=existing.created_at,
            )
        )
        return {"execution_schedule": _to_jsonable(schedule)}

    @app.patch("/config/execution-schedules/{schedule_id}/archive")
    async def set_execution_schedule_archived_state(
        schedule_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        schedule = resolved_config_repository.set_execution_schedule_archived_state(
            schedule_id,
            archived=payload.archived,
        )
        return {"execution_schedule": _to_jsonable(schedule)}

    @app.delete("/config/execution-schedules/{schedule_id}", status_code=204)
    async def delete_execution_schedule(schedule_id: str) -> None:
        require_unsafe_admin()
        resolved_config_repository.delete_execution_schedule(schedule_id)

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

    @app.get("/control/operational-summary")
    async def get_operational_summary() -> dict[str, Any]:
        require_unsafe_admin()
        return build_operational_summary()

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

    @app.get("/control/schedule-dispatches/{dispatch_id}")
    async def get_schedule_dispatch(dispatch_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        try:
            dispatch = resolved_config_repository.get_schedule_dispatch(dispatch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown schedule dispatch.") from exc
        schedule = resolved_config_repository.get_execution_schedule(dispatch.schedule_id)
        ingestion_definition = (
            resolved_config_repository.get_ingestion_definition(schedule.target_ref)
            if schedule.target_kind == "ingestion_definition"
            else None
        )
        source_asset = (
            resolved_config_repository.get_source_asset(ingestion_definition.source_asset_id)
            if ingestion_definition is not None
            else None
        )
        runs = []
        for run_id in dispatch.run_ids:
            try:
                runs.append(serialize_run_detail(service.metadata_repository.get_run(run_id)))
            except KeyError:
                continue
        return {
            "dispatch": _to_jsonable(dispatch),
            "schedule": _to_jsonable(schedule),
            "ingestion_definition": _to_jsonable(ingestion_definition),
            "source_asset": _to_jsonable(source_asset),
            "runs": runs,
        }

    @app.post("/control/schedule-dispatches/{dispatch_id}/retry", status_code=201)
    async def retry_schedule_dispatch(dispatch_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        try:
            dispatch = resolved_config_repository.get_schedule_dispatch(dispatch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown schedule dispatch.") from exc
        if dispatch.status not in {"completed", "failed"}:
            raise HTTPException(
                status_code=409,
                detail="Only completed or failed schedule dispatches can be retried.",
            )
        try:
            retried_dispatch = resolved_config_repository.create_schedule_dispatch(
                dispatch.schedule_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        return {"dispatch": _to_jsonable(retried_dispatch)}

    @app.post("/control/schedule-dispatches", status_code=201)
    async def create_schedule_dispatch(
        payload: ScheduleDispatchRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        if payload.schedule_id:
            dispatch = resolved_config_repository.create_schedule_dispatch(
                payload.schedule_id
            )
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
            return {"dispatch": _to_jsonable(dispatch)}
        dispatches = resolved_config_repository.enqueue_due_execution_schedules(
            limit=payload.limit
        )
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
        return {"dispatches": _to_jsonable(dispatches)}

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
    async def ingest_configured_csv(request: Request) -> JSONResponse:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = _require_upload(form.get("file"))
            payload = ConfiguredCsvIngestRequest(
                source_path="",
                source_asset_id=str(form.get("source_asset_id") or "") or None,
                source_system_id=str(form.get("source_system_id") or "") or None,
                dataset_contract_id=str(form.get("dataset_contract_id") or "") or None,
                column_mapping_id=str(form.get("column_mapping_id") or "") or None,
                source_name=str(form.get("source_name") or "configured-upload"),
            )
            source_asset, source_system_id, dataset_contract_id, column_mapping_id = (
                _resolve_configured_ingest_binding(
                    payload,
                    config_repository=resolved_config_repository,
                )
            )
            source_bytes = await upload.read()
            await upload.close()
            run = configured_ingestion_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=getattr(upload, "filename", None) or "configured-upload.csv",
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
                source_asset_id=source_asset.source_asset_id if source_asset else None,
                source_name=payload.source_name,
            )
        else:
            try:
                payload = ConfiguredCsvIngestRequest(**(await request.json()))
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail=exc.errors()) from exc
            source_asset, source_system_id, dataset_contract_id, column_mapping_id = (
                _resolve_configured_ingest_binding(
                    payload,
                    config_repository=resolved_config_repository,
                )
            )
            run = configured_ingestion_service.ingest_file(
                source_path=Path(payload.source_path),
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
                source_asset_id=source_asset.source_asset_id if source_asset else None,
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


def _resolve_configured_ingest_binding(
    payload: ConfiguredCsvIngestRequest,
    *,
    config_repository: ControlPlaneStore,
):
    source_asset = (
        config_repository.get_source_asset(payload.source_asset_id)
        if payload.source_asset_id
        else None
    )
    if source_asset is not None:
        if getattr(source_asset, "archived", False):
            raise HTTPException(
                status_code=400,
                detail=f"Source asset is archived: {source_asset.source_asset_id}",
            )
        if not source_asset.enabled:
            raise HTTPException(
                status_code=400,
                detail=f"Source asset is disabled: {source_asset.source_asset_id}",
            )
        if (
            payload.source_system_id
            and payload.source_system_id != source_asset.source_system_id
        ):
            raise HTTPException(
                status_code=400,
                detail="source_system_id does not match the selected source asset.",
            )
        if (
            payload.dataset_contract_id
            and payload.dataset_contract_id != source_asset.dataset_contract_id
        ):
            raise HTTPException(
                status_code=400,
                detail="dataset_contract_id does not match the selected source asset.",
            )
        if (
            payload.column_mapping_id
            and payload.column_mapping_id != source_asset.column_mapping_id
        ):
            raise HTTPException(
                status_code=400,
                detail="column_mapping_id does not match the selected source asset.",
            )
        source_system_id = source_asset.source_system_id
        dataset_contract_id = source_asset.dataset_contract_id
        column_mapping_id = source_asset.column_mapping_id
    else:
        missing_fields = [
            field_name
            for field_name, value in (
                ("source_system_id", payload.source_system_id),
                ("dataset_contract_id", payload.dataset_contract_id),
                ("column_mapping_id", payload.column_mapping_id),
            )
            if not value
        ]
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=(
                    "source_asset_id or explicit configured-ingest binding is required; "
                    f"missing {', '.join(missing_fields)}."
                ),
            )
        source_system_id = str(payload.source_system_id)
        dataset_contract_id = str(payload.dataset_contract_id)
        column_mapping_id = str(payload.column_mapping_id)

    source_system = config_repository.get_source_system(source_system_id)
    if not source_system.enabled:
        raise HTTPException(
            status_code=400,
            detail=f"Source system is disabled: {source_system_id}",
        )
    return source_asset, source_system_id, dataset_contract_id, column_mapping_id


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


def request_principal_from_user(
    user,
    *,
    csrf_token: str | None = None,
) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        csrf_token=csrf_token,
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


def _build_dataset_contract_diff(
    left: DatasetContractConfigRecord,
    right: DatasetContractConfigRecord,
) -> dict[str, Any]:
    field_changes = []
    for field_name, left_value, right_value in (
        ("dataset_name", left.dataset_name, right.dataset_name),
        ("version", left.version, right.version),
        ("allow_extra_columns", left.allow_extra_columns, right.allow_extra_columns),
        ("archived", left.archived, right.archived),
    ):
        if left_value != right_value:
            field_changes.append(
                {
                    "field": field_name,
                    "left": _to_jsonable(left_value),
                    "right": _to_jsonable(right_value),
                }
            )
    left_columns = {column.name: column for column in left.columns}
    right_columns = {column.name: column for column in right.columns}
    changed_columns = []
    for column_name in sorted(set(left_columns) & set(right_columns)):
        if left_columns[column_name] == right_columns[column_name]:
            continue
        changed_columns.append(
            {
                "name": column_name,
                "left": _to_jsonable(left_columns[column_name]),
                "right": _to_jsonable(right_columns[column_name]),
            }
        )
    return {
        "left_id": left.dataset_contract_id,
        "right_id": right.dataset_contract_id,
        "left_version": left.version,
        "right_version": right.version,
        "field_changes": field_changes,
        "column_changes": {
            "added": _to_jsonable(
                [right_columns[name] for name in sorted(set(right_columns) - set(left_columns))]
            ),
            "removed": _to_jsonable(
                [left_columns[name] for name in sorted(set(left_columns) - set(right_columns))]
            ),
            "changed": changed_columns,
        },
    }


def _build_column_mapping_diff(
    left: ColumnMappingRecord,
    right: ColumnMappingRecord,
) -> dict[str, Any]:
    field_changes = []
    for field_name, left_value, right_value in (
        ("source_system_id", left.source_system_id, right.source_system_id),
        ("dataset_contract_id", left.dataset_contract_id, right.dataset_contract_id),
        ("version", left.version, right.version),
        ("archived", left.archived, right.archived),
    ):
        if left_value != right_value:
            field_changes.append(
                {
                    "field": field_name,
                    "left": _to_jsonable(left_value),
                    "right": _to_jsonable(right_value),
                }
            )
    left_rules = {rule.target_column: rule for rule in left.rules}
    right_rules = {rule.target_column: rule for rule in right.rules}
    changed_rules = []
    for target_column in sorted(set(left_rules) & set(right_rules)):
        if left_rules[target_column] == right_rules[target_column]:
            continue
        changed_rules.append(
            {
                "target_column": target_column,
                "left": _to_jsonable(left_rules[target_column]),
                "right": _to_jsonable(right_rules[target_column]),
            }
        )
    return {
        "left_id": left.column_mapping_id,
        "right_id": right.column_mapping_id,
        "left_version": left.version,
        "right_version": right.version,
        "field_changes": field_changes,
        "rule_changes": {
            "added": _to_jsonable(
                [right_rules[name] for name in sorted(set(right_rules) - set(left_rules))]
            ),
            "removed": _to_jsonable(
                [left_rules[name] for name in sorted(set(left_rules) - set(right_rules))]
            ),
            "changed": changed_rules,
        },
    }


def serialize_promotion(promotion: PromotionResult) -> dict[str, Any]:
    return {
        "facts_loaded": promotion.facts_loaded,
        "marts_refreshed": promotion.marts_refreshed,
        "publication_keys": promotion.publication_keys,
        "skipped": promotion.skipped,
        "skip_reason": promotion.skip_reason,
    }


def serialize_run(
    run: IngestionRunRecord,
    *,
    context: RunControlContext | None = None,
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
    if context is not None:
        payload["context"] = context.as_manifest_dict()
    if recovery is not None:
        payload["recovery"] = recovery
    return payload


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
