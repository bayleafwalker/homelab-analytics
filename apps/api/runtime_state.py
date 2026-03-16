from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from apps.api.support import serialize_run, to_jsonable
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.metrics import metrics_registry
from packages.storage.control_plane import ControlPlaneStore, ScheduleDispatchRecord
from packages.storage.run_metadata import IngestionRunRecord

if TYPE_CHECKING:
    from packages.pipelines.run_context import RunControlContext


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


def build_operational_summary(
    *,
    service: AccountTransactionService,
    config_repository: ControlPlaneStore,
    load_run_manifest_and_context: Callable[
        [IngestionRunRecord],
        tuple[dict[str, Any] | None, RunControlContext | None],
    ],
    build_run_recovery: Callable[
        [IngestionRunRecord, RunControlContext | None],
        dict[str, Any],
    ],
) -> dict[str, Any]:
    source_assets = config_repository.list_source_assets(include_archived=True)
    dataset_contracts = config_repository.list_dataset_contracts(
        include_archived=True
    )
    column_mappings = config_repository.list_column_mappings(
        include_archived=True
    )
    ingestion_definitions = config_repository.list_ingestion_definitions(
        include_archived=True
    )
    execution_schedules = config_repository.list_execution_schedules(
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

    runtime_state = build_dispatch_runtime_state(config_repository)
    dispatches = runtime_state["dispatches"]
    for dispatch in dispatches:
        update_operational_dispatch_stats(
            execution_schedule_stats.setdefault(
                dispatch.schedule_id,
                make_operational_stats(),
            ),
            dispatch,
        )
    auth_runtime_summary = build_auth_runtime_summary(config_repository)

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
        "recent_failed_dispatches": to_jsonable(
            [dispatch for dispatch in dispatches if dispatch.status == "failed"][:10]
        ),
        "stale_running_dispatches": to_jsonable(
            runtime_state["stale_dispatches"][:10]
        ),
        "recent_recovered_dispatches": to_jsonable(
            runtime_state["recovered_dispatches"][:10]
        ),
        "workers": runtime_state["workers"],
        "queue": runtime_state["queue"],
        "auth": auth_runtime_summary,
    }


def build_auth_runtime_summary(
    config_repository: ControlPlaneStore,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    service_tokens = config_repository.list_service_tokens(
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
    recent_auth_events = config_repository.list_auth_audit_events(
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
            "recently_used": to_jsonable(
                sorted(
                    recently_used_tokens,
                    key=lambda token: token.last_used_at
                    or datetime.min.replace(tzinfo=UTC),
                    reverse=True,
                )[:10]
            ),
            "expiring_soon": to_jsonable(
                sorted(
                    expiring_soon_tokens,
                    key=lambda token: token.expires_at
                    or datetime.max.replace(tzinfo=UTC),
                )[:10]
            ),
        },
        "audit": {
            "recent_events_total": len(recent_auth_events),
            "service_token_events_last_7d": sum(service_token_event_counts.values()),
            "service_token_event_counts": dict(service_token_event_counts),
        },
    }


def is_recovered_dispatch(dispatch: ScheduleDispatchRecord) -> bool:
    failure_reason = dispatch.failure_reason or ""
    return failure_reason.startswith("Dispatch claim expired at ")


def build_dispatch_runtime_state(
    config_repository: ControlPlaneStore,
) -> dict[str, Any]:
    dispatches = config_repository.list_schedule_dispatches()
    dispatch_by_id = {dispatch.dispatch_id: dispatch for dispatch in dispatches}
    heartbeats = config_repository.list_worker_heartbeats()
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


def update_worker_runtime_metrics(config_repository: ControlPlaneStore) -> None:
    runtime_state = build_dispatch_runtime_state(config_repository)
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


def update_auth_runtime_metrics(config_repository: ControlPlaneStore) -> None:
    auth_summary = build_auth_runtime_summary(config_repository)
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
