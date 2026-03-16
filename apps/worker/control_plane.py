from __future__ import annotations

import json
import logging
import os
import signal
import socket
import threading
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, TextIO

from apps.worker.runtime import build_reporting_service, build_transformation_service
from apps.worker.serialization import _json_default, _write_json
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.bootstrap_account_transaction_watch import (
    ensure_account_transaction_watch_definition,
)
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
    ConfiguredIngestionProcessResult,
)
from packages.pipelines.promotion import PromotionResult
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.pipelines.reporting_service import publish_promotion_reporting
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshRegistry,
)
from packages.shared.extensions import ExtensionRegistry
from packages.shared.metrics import metrics_registry
from packages.shared.settings import AppSettings
from packages.storage.control_plane import (
    ScheduleDispatchRecord,
    WorkerHeartbeatCreate,
    WorkerHeartbeatRecord,
)


def _set_worker_queue_depth(config_repository) -> None:
    metrics_registry.set(
        "worker_queue_depth",
        float(len(config_repository.list_schedule_dispatches(status="enqueued"))),
        help_text="Current queued schedule-dispatch count.",
    )


def _resolved_worker_id(
    settings: AppSettings,
    explicit_worker_id: str | None = None,
) -> str:
    if explicit_worker_id:
        return explicit_worker_id
    if settings.worker_id:
        return settings.worker_id
    return f"{socket.gethostname()}-{os.getpid()}"


def _record_worker_heartbeat(
    config_repository,
    *,
    worker_id: str,
    status: str,
    active_dispatch_id: str | None = None,
    detail: str | None = None,
    observed_at: datetime | None = None,
) -> WorkerHeartbeatRecord:
    return config_repository.record_worker_heartbeat(
        WorkerHeartbeatCreate(
            worker_id=worker_id,
            status=status,
            active_dispatch_id=active_dispatch_id,
            detail=detail,
            observed_at=observed_at or datetime.now(UTC),
        )
    )


def _install_shutdown_signal_handlers(
    shutdown_event: threading.Event,
    *,
    logger: logging.Logger,
) -> Callable[[], None]:
    if threading.current_thread() is not threading.main_thread():
        return lambda: None
    previous_handlers: dict[int, Any] = {}

    def _handle_signal(signum, _frame) -> None:
        logger.info(
            "worker shutdown requested",
            extra={"signal": signum},
        )
        shutdown_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, _handle_signal)
        except (AttributeError, ValueError):
            continue

    def _restore() -> None:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

    return _restore


class _ScheduleDispatchLeaseRenewer:
    def __init__(
        self,
        *,
        dispatch: ScheduleDispatchRecord,
        config_repository,
        worker_id: str,
        lease_seconds: int,
        logger: logging.Logger,
    ) -> None:
        self._dispatch = dispatch
        self._config_repository = config_repository
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._logger = logger
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: Exception | None = None
        self._renewal_count = 0

    @property
    def renewal_count(self) -> int:
        return self._renewal_count

    def start(self) -> None:
        if self._lease_seconds <= 0:
            return
        self._thread = threading.Thread(
            target=self._run,
            name=f"dispatch-lease-renewer-{self._dispatch.dispatch_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def raise_if_failed(self) -> None:
        if self._error is not None:
            raise RuntimeError("Schedule dispatch lease renewal failed.") from self._error

    def _run(self) -> None:
        interval_seconds = max(0.5, self._lease_seconds / 3)
        while not self._stop_event.wait(interval_seconds):
            try:
                renewed_at = datetime.now(UTC)
                renewed_expires_at = renewed_at + timedelta(seconds=self._lease_seconds)
                renewed_dispatch = self._config_repository.renew_schedule_dispatch_claim(
                    self._dispatch.dispatch_id,
                    worker_id=self._worker_id,
                    claimed_at=renewed_at,
                    lease_seconds=self._lease_seconds,
                    worker_detail=_build_schedule_dispatch_worker_detail(
                        self._dispatch,
                        state="running",
                        worker_id=self._worker_id,
                        claimed_at=renewed_at,
                        claim_expires_at=renewed_expires_at,
                    ),
                )
                self._renewal_count += 1
                _record_worker_heartbeat(
                    self._config_repository,
                    worker_id=self._worker_id,
                    status="running",
                    active_dispatch_id=renewed_dispatch.dispatch_id,
                    detail=f"Renewed lease for schedule dispatch {renewed_dispatch.dispatch_id}.",
                    observed_at=renewed_at,
                )
            except Exception as exc:  # pragma: no cover - exercised through caller behavior
                self._error = exc
                self._logger.warning(
                    "schedule dispatch lease renewal failed",
                    extra={
                        "dispatch_id": self._dispatch.dispatch_id,
                        "worker_id": self._worker_id,
                    },
                    exc_info=True,
                )
                self._stop_event.set()
                return


def _promote_configured_ingestion_runs(
    process_result: ConfiguredIngestionProcessResult,
    *,
    settings: AppSettings,
    service: AccountTransactionService,
    config_repository,
    extension_registry: ExtensionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry,
    publication_refresh_registry: PublicationRefreshRegistry,
) -> list[PromotionResult]:
    from packages.pipelines.promotion import promote_source_asset_run

    if not process_result.run_ids:
        return []
    transformation_service = build_transformation_service(
        settings,
        publication_refresh_registry=publication_refresh_registry,
    )
    reporting_service = build_reporting_service(
        settings,
        transformation_service,
        extension_registry,
    )
    ingestion_definition = config_repository.get_ingestion_definition(
        process_result.ingestion_definition_id
    )
    source_asset = config_repository.get_source_asset(ingestion_definition.source_asset_id)
    promotions: list[PromotionResult] = [
        promote_source_asset_run(
            run_id,
            source_asset=source_asset,
            config_repository=config_repository,
            landing_root=settings.landing_root,
            metadata_repository=service.metadata_repository,
            transformation_service=transformation_service,
            blob_store=service.blob_store,
            extension_registry=extension_registry,
            promotion_handler_registry=promotion_handler_registry,
        )
        for run_id in process_result.run_ids
    ]
    for promotion in promotions:
        publish_promotion_reporting(reporting_service, promotion)
    return promotions


def _process_configured_ingestion_definition(
    ingestion_definition_id: str,
    *,
    settings: AppSettings,
    service: AccountTransactionService,
    config_repository,
    configured_definition_service: ConfiguredIngestionDefinitionService,
    extension_registry: ExtensionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry,
    publication_refresh_registry: PublicationRefreshRegistry,
) -> dict[str, object]:
    process_result = configured_definition_service.process_ingestion_definition(
        ingestion_definition_id
    )
    return {
        "result": process_result,
        "promotions": _promote_configured_ingestion_runs(
            process_result,
            settings=settings,
            service=service,
            config_repository=config_repository,
            extension_registry=extension_registry,
            promotion_handler_registry=promotion_handler_registry,
            publication_refresh_registry=publication_refresh_registry,
        ),
    }


def _process_account_transaction_watch_folder(
    *,
    settings: AppSettings,
    config_repository,
    configured_definition_service: ConfiguredIngestionDefinitionService,
    source_name: str,
) -> ConfiguredIngestionProcessResult:
    ingestion_definition_id = ensure_account_transaction_watch_definition(
        config_repository,
        source_path=str(settings.account_transactions_inbox_dir),
        processed_path=str(settings.processed_files_dir),
        failed_path=str(settings.failed_files_dir),
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        source_name=source_name,
    )
    return configured_definition_service.process_ingestion_definition(ingestion_definition_id)


def _build_schedule_dispatch_worker_detail(
    dispatch: ScheduleDispatchRecord,
    *,
    process_result: ConfiguredIngestionProcessResult | None = None,
    promotions: list[PromotionResult] | None = None,
    state: str | None = None,
    error_type: str | None = None,
    worker_id: str | None = None,
    claimed_at: datetime | None = None,
    claim_expires_at: datetime | None = None,
    lease_renewals: int | None = None,
) -> str:
    payload: dict[str, object] = {
        "dispatch_id": dispatch.dispatch_id,
        "schedule_id": dispatch.schedule_id,
        "target_kind": dispatch.target_kind,
        "target_ref": dispatch.target_ref,
    }
    if state:
        payload["state"] = state
    if worker_id is not None:
        payload["worker_id"] = worker_id
    if claimed_at is not None:
        payload["claimed_at"] = claimed_at
    if claim_expires_at is not None:
        payload["claim_expires_at"] = claim_expires_at
    if process_result is not None:
        payload["discovered_files"] = process_result.discovered_files
        payload["processed_files"] = process_result.processed_files
        payload["rejected_files"] = process_result.rejected_files
        payload["run_ids"] = list(process_result.run_ids)
    if promotions is not None:
        payload["promotion_run_ids"] = [
            getattr(promotion, "run_id", None) for promotion in promotions
        ]
    if error_type is not None:
        payload["error_type"] = error_type
    if lease_renewals is not None:
        payload["lease_renewals"] = lease_renewals
    return json.dumps(payload, default=_json_default, sort_keys=True)


def _process_schedule_dispatch(
    dispatch_id: str,
    *,
    settings: AppSettings,
    service: AccountTransactionService,
    config_repository,
    configured_definition_service: ConfiguredIngestionDefinitionService,
    extension_registry: ExtensionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry,
    publication_refresh_registry: PublicationRefreshRegistry,
    logger: logging.Logger,
    worker_id: str,
    lease_seconds: int,
    claimed_dispatch: ScheduleDispatchRecord | None = None,
) -> tuple[int, dict[str, object]]:
    dispatch = claimed_dispatch or config_repository.get_schedule_dispatch(dispatch_id)
    if claimed_dispatch is None:
        if dispatch.status != "enqueued":
            raise ValueError(f"Schedule dispatch must be enqueued before processing: {dispatch_id}")
        dispatch = config_repository.claim_schedule_dispatch(
            dispatch_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            worker_detail=_build_schedule_dispatch_worker_detail(
                dispatch,
                state="running",
                worker_id=worker_id,
                claimed_at=datetime.now(UTC),
                claim_expires_at=datetime.now(UTC) + timedelta(seconds=lease_seconds),
            ),
        )
    elif dispatch.status != "running" or dispatch.claimed_by_worker_id != worker_id:
        raise ValueError(f"Schedule dispatch must be claimed by worker {worker_id}: {dispatch_id}")
    _set_worker_queue_depth(config_repository)
    _record_worker_heartbeat(
        config_repository,
        worker_id=worker_id,
        status="running",
        active_dispatch_id=dispatch.dispatch_id,
        detail=f"Processing schedule dispatch {dispatch.dispatch_id}.",
    )

    renewer = _ScheduleDispatchLeaseRenewer(
        dispatch=dispatch,
        config_repository=config_repository,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        logger=logger,
    )
    process_result: ConfiguredIngestionProcessResult | None = None
    promotions: list[PromotionResult] = []
    processing_error: Exception | None = None
    try:
        renewer.start()
        if dispatch.target_kind != "ingestion_definition":
            raise ValueError(
                "Only ingestion-definition schedule dispatches are currently supported."
            )
        process_result = configured_definition_service.process_ingestion_definition(
            dispatch.target_ref
        )
        promotions = _promote_configured_ingestion_runs(
            process_result,
            settings=settings,
            service=service,
            config_repository=config_repository,
            extension_registry=extension_registry,
            promotion_handler_registry=promotion_handler_registry,
            publication_refresh_registry=publication_refresh_registry,
        )
    except Exception as exc:
        processing_error = exc
    finally:
        renewer.stop()

    if processing_error is None:
        try:
            renewer.raise_if_failed()
        except Exception as exc:
            processing_error = exc

    if processing_error is None:
        assert process_result is not None
        try:
            completed_dispatch = config_repository.mark_schedule_dispatch_status(
                dispatch_id,
                status="completed",
                completed_at=datetime.now(UTC),
                run_ids=process_result.run_ids,
                worker_detail=_build_schedule_dispatch_worker_detail(
                    dispatch,
                    process_result=process_result,
                    promotions=promotions,
                    state="completed",
                    worker_id=worker_id,
                    lease_renewals=renewer.renewal_count,
                ),
                expected_status="running",
                expected_worker_id=worker_id,
            )
        except ValueError as exc:
            processing_error = exc

    if processing_error is None:
        _set_worker_queue_depth(config_repository)
        heartbeat = _record_worker_heartbeat(
            config_repository,
            worker_id=worker_id,
            status="idle",
            detail=f"Completed schedule dispatch {dispatch.dispatch_id}.",
        )
        return 0, {
            "dispatch": completed_dispatch,
            "result": process_result,
            "promotions": promotions,
            "worker_heartbeat": heartbeat,
            "lease_renewals": renewer.renewal_count,
        }

    error = processing_error
    if error is None:  # pragma: no cover - defensive
        raise RuntimeError("Expected a schedule dispatch processing error.")
    if not isinstance(error, ValueError) or "Schedule dispatch" not in str(error):
        logger.error(
            "schedule dispatch processing failed",
            extra={
                "dispatch_id": dispatch_id,
                "schedule_id": dispatch.schedule_id,
                "target_kind": dispatch.target_kind,
                "target_ref": dispatch.target_ref,
            },
            exc_info=(type(error), error, error.__traceback__),
        )
    try:
        failed_dispatch = config_repository.mark_schedule_dispatch_status(
            dispatch_id,
            status="failed",
            completed_at=datetime.now(UTC),
            run_ids=process_result.run_ids if process_result is not None else (),
            failure_reason=str(error),
            worker_detail=_build_schedule_dispatch_worker_detail(
                dispatch,
                process_result=process_result,
                promotions=promotions,
                state="failed",
                error_type=type(error).__name__,
                worker_id=worker_id,
                lease_renewals=renewer.renewal_count,
            ),
            expected_status="running",
            expected_worker_id=worker_id,
        )
    except ValueError:
        failed_dispatch = config_repository.get_schedule_dispatch(dispatch_id)
    _set_worker_queue_depth(config_repository)
    heartbeat = _record_worker_heartbeat(
        config_repository,
        worker_id=worker_id,
        status="error",
        detail=f"Failed schedule dispatch {dispatch.dispatch_id}: {error}",
    )
    return 1, {
        "dispatch": failed_dispatch,
        "error": str(error),
        "worker_heartbeat": heartbeat,
        "lease_renewals": renewer.renewal_count,
    }


def _watch_schedule_dispatches(
    *,
    output: TextIO,
    settings: AppSettings,
    config_repository,
    service: AccountTransactionService,
    configured_definition_service: ConfiguredIngestionDefinitionService,
    extension_registry: ExtensionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry,
    publication_refresh_registry: PublicationRefreshRegistry,
    logger: logging.Logger,
    worker_id: str,
    lease_seconds: int,
    max_iterations: int | None = None,
    enqueue_limit: int | None = None,
    recover_limit: int | None = None,
    shutdown_event: threading.Event | None = None,
) -> int:
    iterations = 0
    observed_failure = False
    resolved_shutdown_event = shutdown_event or threading.Event()
    restore_signal_handlers = _install_shutdown_signal_handlers(
        resolved_shutdown_event,
        logger=logger,
    )
    try:
        while True:
            now = datetime.now(UTC)
            payload: dict[str, object] = {"worker_id": worker_id}
            if resolved_shutdown_event.is_set():
                payload["worker_heartbeat"] = _record_worker_heartbeat(
                    config_repository,
                    worker_id=worker_id,
                    status="stopped",
                    detail="Schedule dispatch watcher stopped.",
                    observed_at=now,
                )
                _write_json(output, payload)
                return 1 if observed_failure else 0

            recovered_dispatches = config_repository.requeue_expired_schedule_dispatches(
                as_of=now,
                limit=recover_limit,
                recovered_by_worker_id=worker_id,
            )
            enqueued_dispatches = config_repository.enqueue_due_execution_schedules(
                as_of=now,
                limit=enqueue_limit,
            )
            claimed_dispatch = None
            if not resolved_shutdown_event.is_set():
                claimed_dispatch = config_repository.claim_next_schedule_dispatch(
                    worker_id=worker_id,
                    claimed_at=now,
                    lease_seconds=lease_seconds,
                    worker_detail=json.dumps(
                        {"state": "running", "worker_id": worker_id},
                        sort_keys=True,
                    ),
                )
            _set_worker_queue_depth(config_repository)
            payload["recovered_dispatches"] = recovered_dispatches
            payload["enqueued_dispatches"] = enqueued_dispatches
            if claimed_dispatch is None:
                payload["worker_heartbeat"] = _record_worker_heartbeat(
                    config_repository,
                    worker_id=worker_id,
                    status="stopped" if resolved_shutdown_event.is_set() else "idle",
                    detail=(
                        "Schedule dispatch watcher stopped."
                        if resolved_shutdown_event.is_set()
                        else "No schedule dispatches ready for processing."
                    ),
                    observed_at=now,
                )
                _write_json(output, payload)
                iterations += 1
                if resolved_shutdown_event.is_set():
                    return 1 if observed_failure else 0
                if max_iterations is not None and iterations >= max_iterations:
                    return 1 if observed_failure else 0
                if resolved_shutdown_event.wait(settings.worker_poll_interval_seconds):
                    continue
                continue

            exit_code, process_payload = _process_schedule_dispatch(
                claimed_dispatch.dispatch_id,
                settings=settings,
                service=service,
                config_repository=config_repository,
                configured_definition_service=configured_definition_service,
                extension_registry=extension_registry,
                promotion_handler_registry=promotion_handler_registry,
                publication_refresh_registry=publication_refresh_registry,
                logger=logger,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
                claimed_dispatch=claimed_dispatch,
            )
            observed_failure = observed_failure or exit_code != 0
            payload.update(process_payload)
            _write_json(output, payload)
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                return 1 if observed_failure else 0
            if resolved_shutdown_event.wait(settings.worker_poll_interval_seconds):
                continue
    finally:
        restore_signal_handlers()
