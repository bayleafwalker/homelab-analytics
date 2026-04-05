"""Schedule dispatch worker command handlers."""
from __future__ import annotations

from argparse import Namespace
from datetime import UTC, datetime

from apps.worker.control_plane import (
    _process_schedule_dispatch,
    _resolved_worker_id,
    _set_worker_queue_depth,
    _watch_schedule_dispatches,
)
from apps.worker.runtime import WorkerRuntime
from apps.worker.serialization import _write_json


def handle_list_schedule_dispatches(args: Namespace, runtime: WorkerRuntime) -> int:
    dispatches = runtime.config_repository.list_schedule_dispatches(
        schedule_id=getattr(args, "schedule_id", None) or None,
        status=getattr(args, "status", None) or None,
    )
    _set_worker_queue_depth(runtime.config_repository)
    _write_json(runtime.output, {"dispatches": dispatches})
    return 0


def handle_list_worker_heartbeats(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"workers": runtime.config_repository.list_worker_heartbeats()},
    )
    return 0


def handle_enqueue_due_schedules(args: Namespace, runtime: WorkerRuntime) -> int:
    as_of = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", "") else None
    dispatches = runtime.config_repository.enqueue_due_execution_schedules(
        as_of=as_of,
        limit=getattr(args, "limit", None),
    )
    _set_worker_queue_depth(runtime.config_repository)
    _write_json(runtime.output, {"dispatches": dispatches})
    return 0


def handle_recover_stale_schedule_dispatches(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    as_of = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", "") else None
    worker_id = _resolved_worker_id(
        runtime.settings,
        getattr(args, "worker_id", "") or None,
    )
    recoveries = runtime.config_repository.requeue_expired_schedule_dispatches(
        as_of=as_of,
        limit=getattr(args, "limit", None),
        recovered_by_worker_id=worker_id,
    )
    _set_worker_queue_depth(runtime.config_repository)
    _write_json(runtime.output, {"worker_id": worker_id, "recoveries": recoveries})
    return 0


def handle_mark_schedule_dispatch(args: Namespace, runtime: WorkerRuntime) -> int:
    dispatch = runtime.config_repository.mark_schedule_dispatch_status(
        args.dispatch_id,
        status=args.status,
        completed_at=datetime.now(UTC),
    )
    _set_worker_queue_depth(runtime.config_repository)
    _write_json(runtime.output, {"dispatch": dispatch})
    return 0


def handle_process_schedule_dispatch(args: Namespace, runtime: WorkerRuntime) -> int:
    worker_id = _resolved_worker_id(
        runtime.settings,
        getattr(args, "worker_id", "") or None,
    )
    exit_code, payload = _process_schedule_dispatch(
        args.dispatch_id,
        settings=runtime.settings,
        service=runtime.service,
        config_repository=runtime.config_repository,
        configured_definition_service=runtime.configured_definition_service,
        extension_registry=runtime.extension_registry,
        promotion_handler_registry=runtime.promotion_handler_registry,
        transformation_domain_registry=runtime.transformation_domain_registry,
        publication_refresh_registry=runtime.publication_refresh_registry,
        logger=runtime.logger,
        worker_id=worker_id,
        lease_seconds=getattr(args, "lease_seconds", None)
        or runtime.settings.dispatch_lease_seconds,
    )
    _write_json(runtime.output, payload)
    return exit_code


def handle_watch_schedule_dispatches(args: Namespace, runtime: WorkerRuntime) -> int:
    worker_id = _resolved_worker_id(
        runtime.settings,
        getattr(args, "worker_id", "") or None,
    )
    return _watch_schedule_dispatches(
        output=runtime.output,
        settings=runtime.settings,
        config_repository=runtime.config_repository,
        service=runtime.service,
        configured_definition_service=runtime.configured_definition_service,
        extension_registry=runtime.extension_registry,
        promotion_handler_registry=runtime.promotion_handler_registry,
        transformation_domain_registry=runtime.transformation_domain_registry,
        publication_refresh_registry=runtime.publication_refresh_registry,
        logger=runtime.logger,
        worker_id=worker_id,
        lease_seconds=getattr(args, "lease_seconds", None)
        or runtime.settings.dispatch_lease_seconds,
        max_iterations=getattr(args, "max_iterations", None),
        enqueue_limit=getattr(args, "enqueue_limit", None),
        recover_limit=getattr(args, "recover_limit", None),
    )
