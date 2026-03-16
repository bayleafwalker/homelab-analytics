from __future__ import annotations

import logging
import time
import uuid
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.datastructures import UploadFile

from apps.api.models import ConfiguredCsvIngestRequest
from apps.api.routes.auth_routes import register_auth_routes
from apps.api.routes.config_routes import register_config_routes
from apps.api.routes.control_routes import register_control_routes
from apps.api.routes.ingest_routes import register_ingest_routes
from apps.api.routes.report_routes import register_report_routes
from apps.api.routes.run_routes import register_run_routes
from packages.analytics.cashflow import MonthlyCashflowSummary
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.promotion import (
    PromotionResult,
    promote_run,
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
    AuthenticatedPrincipal,
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcProvider,
    SessionManager,
    authenticate_service_token,
    has_required_role,
    has_required_service_token_scope,
    parse_service_token,
)
from packages.shared.extensions import (
    ExtensionRegistry,
    build_builtin_extension_registry,
)
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    SERVICE_TOKEN_SCOPE_RUNS_READ,
    AuthStore,
    UserRole,
)
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    ControlPlaneStore,
    IngestionCatalogStore,
    ScheduleDispatchRecord,
)
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
    IngestionConfigRepository,
)
from packages.storage.run_metadata import IngestionRunRecord


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
    oidc_provider: OidcProvider | None = None,
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
        auth_runtime_summary = build_auth_runtime_summary()

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
            "auth": auth_runtime_summary,
        }

    def build_auth_runtime_summary() -> dict[str, Any]:
        now = datetime.now(UTC)
        service_tokens = resolved_config_repository.list_service_tokens(
            include_revoked=True
        )
        active_tokens = [
            token
            for token in service_tokens
            if token.revoked_at is None
            and (token.expires_at is None or token.expires_at > now)
        ]
        expired_tokens = [
            token
            for token in service_tokens
            if token.revoked_at is None
            and token.expires_at is not None
            and token.expires_at <= now
        ]
        expiring_soon_tokens = [
            token
            for token in active_tokens
            if token.expires_at is not None
            and token.expires_at <= now + timedelta(days=7)
        ]
        never_used_tokens = [
            token for token in active_tokens if token.last_used_at is None
        ]
        recently_used_tokens = [
            token
            for token in active_tokens
            if token.last_used_at is not None
            and token.last_used_at >= now - timedelta(days=1)
        ]
        recent_auth_events = resolved_config_repository.list_auth_audit_events(
            since=now - timedelta(days=7),
            limit=250,
        )
        service_token_event_counts = Counter(
            event.event_type
            for event in recent_auth_events
            if event.event_type.startswith("service_token_")
        )
        return {
            "service_tokens": {
                "total": len(service_tokens),
                "active": len(active_tokens),
                "revoked": len(
                    [token for token in service_tokens if token.revoked_at is not None]
                ),
                "expired": len(expired_tokens),
                "expiring_within_7d": len(expiring_soon_tokens),
                "used_within_24h": len(recently_used_tokens),
                "never_used": len(never_used_tokens),
                "recently_used": _to_jsonable(
                    sorted(
                        recently_used_tokens,
                        key=lambda token: token.last_used_at or datetime.min.replace(tzinfo=UTC),
                        reverse=True,
                    )[:10]
                ),
                "expiring_soon": _to_jsonable(
                    sorted(
                        expiring_soon_tokens,
                        key=lambda token: token.expires_at or datetime.max.replace(tzinfo=UTC),
                    )[:10]
                ),
            },
            "audit": {
                "recent_events_total": len(recent_auth_events),
                "service_token_events_last_7d": sum(service_token_event_counts.values()),
                "service_token_event_counts": dict(service_token_event_counts),
            },
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

    def update_auth_runtime_metrics() -> None:
        auth_summary = build_auth_runtime_summary()
        service_token_summary = auth_summary["service_tokens"]
        audit_summary = auth_summary["audit"]
        metrics_registry.set(
            "auth_service_tokens_total",
            float(service_token_summary["total"]),
            help_text="Current total service-token count including revoked tokens.",
        )
        metrics_registry.set(
            "auth_service_tokens_active",
            float(service_token_summary["active"]),
            help_text="Current active service-token count.",
        )
        metrics_registry.set(
            "auth_service_tokens_expired",
            float(service_token_summary["expired"]),
            help_text="Current expired service-token count.",
        )
        metrics_registry.set(
            "auth_service_tokens_expiring_7d",
            float(service_token_summary["expiring_within_7d"]),
            help_text="Current active service-token count expiring within seven days.",
        )
        metrics_registry.set(
            "auth_service_tokens_never_used",
            float(service_token_summary["never_used"]),
            help_text="Current active service-token count that has never been used.",
        )
        metrics_registry.set(
            "auth_service_tokens_used_24h",
            float(service_token_summary["used_within_24h"]),
            help_text="Current active service-token count used within the last twenty-four hours.",
        )
        metrics_registry.set(
            "auth_service_token_audit_events_7d",
            float(audit_summary["service_token_events_last_7d"]),
            help_text="Service-token auth-audit events recorded in the last seven days.",
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
        if path in {"/health", "/ready", "/metrics", "/auth/login", "/auth/logout", "/auth/callback"}:
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
            or path.startswith("/auth/service-tokens")
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

    def required_service_token_scope_for_path(path: str) -> str | None:
        if path in {"/health", "/ready", "/metrics", "/auth/login", "/auth/logout", "/auth/callback"}:
            return None
        if path.startswith("/ingest") or (path.startswith("/runs/") and path.endswith("/retry")):
            return SERVICE_TOKEN_SCOPE_INGEST_WRITE
        if (
            path.startswith("/runs")
            or path == "/control/source-lineage"
            or path == "/control/publication-audit"
            or path == "/transformation-audit"
        ):
            return SERVICE_TOKEN_SCOPE_RUNS_READ
        if path.startswith("/reports"):
            return SERVICE_TOKEN_SCOPE_REPORTS_READ
        if (
            path.startswith("/auth/users")
            or path.startswith("/auth/service-tokens")
            or path == "/control/auth-audit"
            or path == "/control/schedule-dispatches"
            or path.startswith("/config/")
            or path.startswith("/control/")
            or path in {"/extensions", "/sources"}
            or path.startswith("/landing/")
            or path.startswith("/transformations/")
            or path.startswith("/ingest/ingestion-definitions/")
        ):
            return SERVICE_TOKEN_SCOPE_ADMIN_WRITE
        return None

    def bearer_token_from_request(request: Request) -> str | None:
        header_value = request.headers.get("authorization", "").strip()
        if not header_value:
            return None
        scheme, _, token = header_value.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        return token.strip()

    @app.middleware("http")
    async def authenticate_and_log_request(request: Request, call_next):
        started = time.perf_counter()
        request.state.principal = None
        request.state.auth_via_cookie = False
        if resolved_auth_mode in {"local", "oidc"}:
            assert resolved_session_manager is not None
            required_role = required_role_for_path(request.url.path)
            required_scope = required_service_token_scope_for_path(request.url.path)
            auth_error_response: JSONResponse | None = None
            bearer_token = bearer_token_from_request(request)
            if bearer_token is not None:
                parsed_service_token = parse_service_token(bearer_token)
                request.state.principal = authenticate_service_token(
                    bearer_token,
                    resolved_auth_store,
                )
                if (
                    request.state.principal is not None
                    and request.state.principal.auth_provider == "service_token"
                ):
                    metrics_registry.inc(
                        "auth_service_token_authenticated_requests_total",
                        1,
                        help_text="Total successfully authenticated service-token requests observed by this API process.",
                    )
                if request.state.principal is None and parsed_service_token is not None:
                    metrics_registry.inc(
                        "auth_service_token_failed_requests_total",
                        1,
                        help_text="Total rejected service-token bearer requests observed by this API process.",
                    )
                    record_auth_event(
                        request,
                        event_type="service_token_auth_failed",
                        success=False,
                        subject_user_id=parsed_service_token[0],
                        subject_username=parsed_service_token[0],
                        detail="Invalid, expired, or revoked service token.",
                    )
                    auth_error_response = JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid service token."},
                    )
                elif request.state.principal is None and resolved_auth_mode == "oidc":
                    assert resolved_oidc_provider is not None
                    try:
                        request.state.principal = resolved_oidc_provider.authenticate_bearer_token(
                            bearer_token
                        )
                    except OidcAuthorizationError as exc:
                        auth_error_response = JSONResponse(
                            status_code=403,
                            content={"detail": str(exc)},
                        )
                    except OidcAuthenticationError:
                        auth_error_response = JSONResponse(
                            status_code=401,
                            content={"detail": "Invalid bearer token."},
                        )
            else:
                request.state.principal = resolved_session_manager.authenticate(
                    request.cookies.get(resolved_session_manager.cookie_name),
                    resolved_auth_store,
                )
                request.state.auth_via_cookie = request.state.principal is not None
            if auth_error_response is not None:
                _log_request(
                    logger,
                    request.method,
                    request.url.path,
                    auth_error_response.status_code,
                    started,
                )
                return auth_error_response
            if (
                request.state.principal is not None
                and bool(getattr(request.state, "auth_via_cookie", False))
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
                if (
                    request.state.principal is not None
                    and request.state.principal.auth_provider == "service_token"
                    and not has_required_service_token_scope(
                        request.state.principal.scopes,
                        required_scope,
                    )
                ):
                    response = JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"{required_scope or 'required'} scope required.",
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

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready", "auth_mode": resolved_auth_mode}

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        update_worker_runtime_metrics()
        update_auth_runtime_metrics()
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
        to_jsonable=_to_jsonable,
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
        load_run_manifest_and_context=load_run_manifest_and_context,
        build_run_recovery=build_run_recovery,
        serialize_run=serialize_run,
        serialize_run_detail=serialize_run_detail,
        build_run_response=_build_run_response,
        build_ingest_response=_build_ingest_response,
        publish_reporting=publish_reporting,
    )
    register_config_routes(
        app,
        registry=registry,
        resolved_config_repository=resolved_config_repository,
        configured_ingestion_service=configured_ingestion_service,
        require_unsafe_admin=require_unsafe_admin,
        ensure_matching_identifier=ensure_matching_identifier,
        to_jsonable=_to_jsonable,
        build_dataset_contract_diff=_build_dataset_contract_diff,
        build_column_mapping_diff=_build_column_mapping_diff,
    )
    register_control_routes(
        app,
        service=service,
        resolved_config_repository=resolved_config_repository,
        require_unsafe_admin=require_unsafe_admin,
        serialize_run_detail=serialize_run_detail,
        build_operational_summary=build_operational_summary,
        to_jsonable=_to_jsonable,
    )
    register_report_routes(
        app,
        service=service,
        registry=registry,
        transformation_service=transformation_service,
        resolved_reporting_service=resolved_reporting_service,
        to_jsonable=_to_jsonable,
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
        publish_reporting=publish_reporting,
        resolve_configured_ingest_binding=lambda payload: _resolve_configured_ingest_binding(
            payload,
            config_repository=resolved_config_repository,
        ),
        build_run_response=_build_run_response,
        build_ingest_response=_build_ingest_response,
        require_upload=_require_upload,
        serialize_run=serialize_run,
        serialize_promotion=serialize_promotion,
        to_jsonable=_to_jsonable,
    )

    return app


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
    config_repository: IngestionCatalogStore,
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
