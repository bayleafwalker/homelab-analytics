from __future__ import annotations

import json
import time
import uuid
from argparse import Namespace
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from apps.api.app import serialize_promotion, serialize_run
from apps.worker.control_plane import (
    _process_account_transaction_watch_folder,
    _process_configured_ingestion_definition,
    _process_schedule_dispatch,
    _resolved_worker_id,
    _set_worker_queue_depth,
    _watch_schedule_dispatches,
)
from apps.worker.runtime import (
    WorkerRuntime,
    build_contract_price_service,
    build_reporting_service,
    build_subscription_service,
    build_transformation_service,
)
from apps.worker.serialization import (
    _control_plane_snapshot_from_dict,
    _control_plane_snapshot_to_dict,
    _json_default,
    _serialize_inbox_result,
    _write_json,
)
from packages.pipelines.config_preflight import run_config_preflight
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
from packages.pipelines.transformation_service import TransformationService
from packages.shared.auth import (
    hash_password,
    issue_service_token,
    serialize_service_token,
    serialize_user,
)
from packages.shared.extensions import serialize_extension_registry
from packages.storage.auth_store import LocalUserCreate, ServiceTokenCreate, UserRole

WorkerCommandHandler = Callable[[Namespace, WorkerRuntime], int]


def _build_reporting_runtime(
    runtime: WorkerRuntime,
) -> tuple[TransformationService, ReportingService]:
    transformation_service = build_transformation_service(
        runtime.settings,
        publication_refresh_registry=runtime.publication_refresh_registry,
        domain_registry=runtime.transformation_domain_registry,
    )
    return transformation_service, build_reporting_service(
        runtime.settings,
        transformation_service,
        runtime.extension_registry,
    )


def _publish_reporting(
    reporting_service: ReportingService | None,
    promotion: PromotionResult | None,
) -> None:
    publish_promotion_reporting(reporting_service, promotion)


def _serialize_promotion_payload(promotion: PromotionResult) -> dict[str, object]:
    return {"run_id": promotion.run_id, **serialize_promotion(promotion)}


def _handle_ingest_configured_csv(args: Namespace, runtime: WorkerRuntime) -> int:
    from packages.pipelines.configured_csv_ingestion import (
        ConfiguredCsvIngestionService,
    )

    csv_service = ConfiguredCsvIngestionService(
        landing_root=runtime.settings.landing_root,
        metadata_repository=runtime.service.metadata_repository,
        config_repository=runtime.config_repository,
        blob_store=runtime.service.blob_store,
    )
    source_asset = (
        runtime.config_repository.get_source_asset(args.source_asset_id)
        if getattr(args, "source_asset_id", None)
        else None
    )
    if source_asset is None and not (
        args.source_system_id and args.dataset_contract_id and args.column_mapping_id
    ):
        raise ValueError(
            "Configured CSV ingestion requires either --source-asset-id or the full source-system/dataset-contract/column-mapping binding."
        )
    source_system_id = source_asset.source_system_id if source_asset else args.source_system_id
    dataset_contract_id = (
        source_asset.dataset_contract_id if source_asset else args.dataset_contract_id
    )
    column_mapping_id = source_asset.column_mapping_id if source_asset else args.column_mapping_id
    run = csv_service.ingest_file(
        source_path=Path(args.source_path),
        source_system_id=source_system_id,
        dataset_contract_id=dataset_contract_id,
        column_mapping_id=column_mapping_id,
        source_name=args.source_name,
    )
    payload: dict[str, object] = {"run": serialize_run(run)}
    if run.passed:
        transformation_service, reporting_service = _build_reporting_runtime(runtime)
        resolved_source_asset = (
            source_asset
            or runtime.config_repository.find_source_asset_by_binding(
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
            )
        )
        if resolved_source_asset is not None:
            promotion = promote_source_asset_run(
                run.run_id,
                source_asset=resolved_source_asset,
                config_repository=runtime.config_repository,
                landing_root=runtime.settings.landing_root,
                metadata_repository=runtime.service.metadata_repository,
                transformation_service=transformation_service,
                blob_store=runtime.service.blob_store,
                extension_registry=runtime.extension_registry,
                promotion_handler_registry=runtime.promotion_handler_registry,
            )
            _publish_reporting(reporting_service, promotion)
            payload["promotion"] = promotion
    _write_json(runtime.output, payload)
    return 0


def _handle_promote_run(args: Namespace, runtime: WorkerRuntime) -> int:
    transformation_service, reporting_service = _build_reporting_runtime(runtime)
    result = promote_run(
        args.run_id,
        account_service=runtime.service,
        transformation_service=transformation_service,
    )
    _publish_reporting(reporting_service, result)
    _write_json(runtime.output, {"promotion": _serialize_promotion_payload(result)})
    return 0


def _handle_ingest_subscriptions(args: Namespace, runtime: WorkerRuntime) -> int:
    subscription_service = build_subscription_service(runtime.settings)
    run = subscription_service.ingest_file(
        Path(args.source_path),
        source_name=args.source_name,
    )
    payload: dict[str, object] = {"run": serialize_run(run)}
    if run.passed:
        transformation_service, reporting_service = _build_reporting_runtime(runtime)
        promotion = promote_subscription_run(
            run.run_id,
            subscription_service=subscription_service,
            transformation_service=transformation_service,
        )
        _publish_reporting(reporting_service, promotion)
        payload["promotion"] = _serialize_promotion_payload(promotion)
    _write_json(runtime.output, payload)
    return 0


def _handle_ingest_contract_prices(args: Namespace, runtime: WorkerRuntime) -> int:
    contract_price_service = build_contract_price_service(runtime.settings)
    run = contract_price_service.ingest_file(
        Path(args.source_path),
        source_name=args.source_name,
    )
    payload: dict[str, object] = {"run": serialize_run(run)}
    if run.passed:
        transformation_service, reporting_service = _build_reporting_runtime(runtime)
        promotion = promote_contract_price_run(
            run.run_id,
            contract_price_service=contract_price_service,
            transformation_service=transformation_service,
        )
        _publish_reporting(reporting_service, promotion)
        payload["promotion"] = _serialize_promotion_payload(promotion)
    _write_json(runtime.output, payload)
    return 0


def _handle_report_contract_prices(args: Namespace, runtime: WorkerRuntime) -> int:
    _, reporting_service = _build_reporting_runtime(runtime)
    _write_json(
        runtime.output,
        {
            "rows": reporting_service.get_contract_price_current(
                contract_type=getattr(args, "contract_type", None) or None,
                status=getattr(args, "status", None) or None,
            )
        },
    )
    return 0


def _handle_report_electricity_prices(args: Namespace, runtime: WorkerRuntime) -> int:
    _, reporting_service = _build_reporting_runtime(runtime)
    _write_json(
        runtime.output,
        {"rows": reporting_service.get_electricity_price_current()},
    )
    return 0


def _handle_report_subscription_summary(args: Namespace, runtime: WorkerRuntime) -> int:
    _, reporting_service = _build_reporting_runtime(runtime)
    _write_json(
        runtime.output,
        {
            "rows": reporting_service.get_subscription_summary(
                status=getattr(args, "status", None) or None,
                currency=getattr(args, "currency", None) or None,
            )
        },
    )
    return 0


def _handle_ingest_account_transactions(args: Namespace, runtime: WorkerRuntime) -> int:
    run = runtime.service.ingest_file(
        Path(args.source_path),
        source_name=args.source_name,
    )
    payload: dict[str, object] = {"run": serialize_run(run)}
    if run.passed:
        transformation_service, reporting_service = _build_reporting_runtime(runtime)
        promotion = promote_run(
            run.run_id,
            account_service=runtime.service,
            transformation_service=transformation_service,
        )
        _publish_reporting(reporting_service, promotion)
        payload["promotion"] = promotion
    _write_json(runtime.output, payload)
    return 0


def _handle_list_runs(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"runs": [serialize_run(run) for run in runtime.service.list_runs()]},
    )
    return 0


def _handle_list_ingestion_definitions(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"ingestion_definitions": runtime.config_repository.list_ingestion_definitions()},
    )
    return 0


def _handle_list_execution_schedules(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"execution_schedules": runtime.config_repository.list_execution_schedules()},
    )
    return 0


def _handle_list_local_users(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"users": [serialize_user(user) for user in runtime.config_repository.list_local_users()]},
    )
    return 0


def _handle_list_service_tokens(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {
            "service_tokens": [
                serialize_service_token(token)
                for token in runtime.config_repository.list_service_tokens(
                    include_revoked=getattr(args, "include_revoked", False)
                )
            ]
        },
    )
    return 0


def _handle_create_local_admin_user(args: Namespace, runtime: WorkerRuntime) -> int:
    user = runtime.config_repository.create_local_user(
        LocalUserCreate(
            user_id=f"user-{args.username}",
            username=args.username,
            password_hash=hash_password(args.password),
            role=UserRole.ADMIN,
        )
    )
    _write_json(runtime.output, {"user": serialize_user(user)})
    return 0


def _handle_create_service_token(args: Namespace, runtime: WorkerRuntime) -> int:
    expires_at = (
        datetime.fromisoformat(args.expires_at) if getattr(args, "expires_at", "") else None
    )
    issued_token = issue_service_token(f"token-{uuid.uuid4().hex}")
    token = runtime.config_repository.create_service_token(
        ServiceTokenCreate(
            token_id=issued_token.token_id,
            token_name=args.token_name,
            token_secret_hash=issued_token.token_secret_hash,
            role=UserRole(args.role),
            scopes=tuple(args.scope),
            expires_at=expires_at,
        )
    )
    _write_json(
        runtime.output,
        {
            "service_token": serialize_service_token(token),
            "token_value": issued_token.token_value,
        },
    )
    return 0


def _handle_reset_local_user_password(args: Namespace, runtime: WorkerRuntime) -> int:
    user = runtime.config_repository.get_local_user_by_username(args.username)
    updated_user = runtime.config_repository.update_local_user_password(
        user.user_id,
        password_hash=hash_password(args.password),
    )
    _write_json(runtime.output, {"user": serialize_user(updated_user)})
    return 0


def _handle_revoke_service_token(args: Namespace, runtime: WorkerRuntime) -> int:
    token = runtime.config_repository.revoke_service_token(args.token_id)
    _write_json(runtime.output, {"service_token": serialize_service_token(token)})
    return 0


def _handle_list_schedule_dispatches(args: Namespace, runtime: WorkerRuntime) -> int:
    dispatches = runtime.config_repository.list_schedule_dispatches(
        schedule_id=getattr(args, "schedule_id", None) or None,
        status=getattr(args, "status", None) or None,
    )
    _set_worker_queue_depth(runtime.config_repository)
    _write_json(runtime.output, {"dispatches": dispatches})
    return 0


def _handle_list_worker_heartbeats(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"workers": runtime.config_repository.list_worker_heartbeats()},
    )
    return 0


def _handle_enqueue_due_schedules(args: Namespace, runtime: WorkerRuntime) -> int:
    as_of = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", "") else None
    dispatches = runtime.config_repository.enqueue_due_execution_schedules(
        as_of=as_of,
        limit=getattr(args, "limit", None),
    )
    _set_worker_queue_depth(runtime.config_repository)
    _write_json(runtime.output, {"dispatches": dispatches})
    return 0


def _handle_recover_stale_schedule_dispatches(
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


def _handle_mark_schedule_dispatch(args: Namespace, runtime: WorkerRuntime) -> int:
    dispatch = runtime.config_repository.mark_schedule_dispatch_status(
        args.dispatch_id,
        status=args.status,
        completed_at=datetime.now(UTC),
    )
    _set_worker_queue_depth(runtime.config_repository)
    _write_json(runtime.output, {"dispatch": dispatch})
    return 0


def _handle_process_schedule_dispatch(args: Namespace, runtime: WorkerRuntime) -> int:
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


def _handle_watch_schedule_dispatches(args: Namespace, runtime: WorkerRuntime) -> int:
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


def _handle_export_control_plane(args: Namespace, runtime: WorkerRuntime) -> int:
    snapshot = runtime.config_repository.export_snapshot()
    destination = Path(args.output_path)
    destination.write_text(
        json.dumps(
            _control_plane_snapshot_to_dict(snapshot),
            default=_json_default,
            indent=2,
        )
    )
    _write_json(
        runtime.output,
        {
            "output_path": str(destination),
            "snapshot": {
                "source_systems": len(snapshot.source_systems),
                "dataset_contracts": len(snapshot.dataset_contracts),
                "column_mappings": len(snapshot.column_mappings),
                "source_assets": len(snapshot.source_assets),
                "ingestion_definitions": len(snapshot.ingestion_definitions),
                "execution_schedules": len(snapshot.execution_schedules),
                "source_lineage": len(snapshot.source_lineage),
                "publication_audit": len(snapshot.publication_audit),
                "auth_audit_events": len(snapshot.auth_audit_events),
                "local_users": len(snapshot.local_users),
                "service_tokens": len(snapshot.service_tokens),
            },
        },
    )
    return 0


def _handle_import_control_plane(args: Namespace, runtime: WorkerRuntime) -> int:
    source = Path(args.input_path)
    snapshot = _control_plane_snapshot_from_dict(json.loads(source.read_text()))
    runtime.config_repository.import_snapshot(snapshot)
    _write_json(
        runtime.output,
        {
            "input_path": str(source),
            "imported": True,
        },
    )
    return 0


def _handle_verify_config(args: Namespace, runtime: WorkerRuntime) -> int:
    report = run_config_preflight(
        runtime.config_repository,
        extension_registry=runtime.extension_registry,
        source_asset_id=getattr(args, "source_asset_id", None) or None,
        ingestion_definition_id=(getattr(args, "ingestion_definition_id", None) or None),
    )
    _write_json(runtime.output, {"report": report})
    return 0 if report.passed else 1


def _handle_list_extensions(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"extensions": serialize_extension_registry(runtime.extension_registry)},
    )
    return 0


def _handle_run_landing_extension(args: Namespace, runtime: WorkerRuntime) -> int:
    landing_result = runtime.extension_registry.execute(
        "landing",
        args.extension_key,
        service=runtime.service,
        source_path=args.source_path,
        source_name=args.source_name,
    )
    _write_json(runtime.output, {"result": landing_result})
    return 0


def _handle_process_account_transactions_inbox(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    inbox_result = _process_account_transaction_watch_folder(
        settings=runtime.settings,
        config_repository=runtime.config_repository,
        configured_definition_service=runtime.configured_definition_service,
        source_name=args.source_name,
    )
    _write_json(runtime.output, {"result": _serialize_inbox_result(inbox_result)})
    return 0


def _handle_watch_account_transactions_inbox(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    iterations = 0
    while True:
        inbox_result = _process_account_transaction_watch_folder(
            settings=runtime.settings,
            config_repository=runtime.config_repository,
            configured_definition_service=runtime.configured_definition_service,
            source_name=args.source_name,
        )
        _write_json(runtime.output, {"result": _serialize_inbox_result(inbox_result)})
        iterations += 1
        if args.max_iterations is not None and iterations >= args.max_iterations:
            return 0
        time.sleep(runtime.settings.worker_poll_interval_seconds)


def _handle_process_ingestion_definition(args: Namespace, runtime: WorkerRuntime) -> int:
    payload = _process_configured_ingestion_definition(
        args.ingestion_definition_id,
        settings=runtime.settings,
        service=runtime.service,
        config_repository=runtime.config_repository,
        configured_definition_service=runtime.configured_definition_service,
        extension_registry=runtime.extension_registry,
        promotion_handler_registry=runtime.promotion_handler_registry,
        transformation_domain_registry=runtime.transformation_domain_registry,
        publication_refresh_registry=runtime.publication_refresh_registry,
    )
    _write_json(runtime.output, payload)
    return 0


def _handle_run_transformation_extension(args: Namespace, runtime: WorkerRuntime) -> int:
    transformation_result = runtime.extension_registry.execute(
        "transformation",
        args.extension_key,
        service=runtime.service,
        run_id=args.run_id,
    )
    _write_json(runtime.output, {"result": transformation_result})
    return 0


def _handle_report_monthly_cashflow(args: Namespace, runtime: WorkerRuntime) -> int:
    _, reporting_service = _build_reporting_runtime(runtime)
    _write_json(
        runtime.output,
        {
            "rows": reporting_service.get_monthly_cashflow(
                from_month=getattr(args, "from_month", None) or None,
                to_month=getattr(args, "to_month", None) or None,
            ),
            "from_month": getattr(args, "from_month", None) or None,
            "to_month": getattr(args, "to_month", None) or None,
        },
    )
    return 0


def _handle_report_utility_cost_summary(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    _, reporting_service = _build_reporting_runtime(runtime)
    _write_json(
        runtime.output,
        {
            "rows": reporting_service.get_utility_cost_summary(
                utility_type=getattr(args, "utility_type", None) or None,
                meter_id=getattr(args, "meter_id", None) or None,
                from_period=getattr(args, "from_period", None) or None,
                to_period=getattr(args, "to_period", None) or None,
                granularity=getattr(args, "granularity", "month"),
            ),
            "utility_type": getattr(args, "utility_type", None) or None,
            "meter_id": getattr(args, "meter_id", None) or None,
            "from_period": getattr(args, "from_period", None) or None,
            "to_period": getattr(args, "to_period", None) or None,
            "granularity": getattr(args, "granularity", "month"),
        },
    )
    return 0


def _handle_run_reporting_extension(args: Namespace, runtime: WorkerRuntime) -> int:
    transformation_service, reporting_service = _build_reporting_runtime(runtime)
    reporting_result = runtime.extension_registry.execute(
        "reporting",
        args.extension_key,
        service=runtime.service,
        reporting_service=reporting_service,
        transformation_service=transformation_service,
        run_id=args.run_id,
    )
    _write_json(runtime.output, {"result": reporting_result})
    return 0


def build_worker_command_handlers() -> dict[str, WorkerCommandHandler]:
    return {
        "create-local-admin-user": _handle_create_local_admin_user,
        "create-service-token": _handle_create_service_token,
        "enqueue-due-schedules": _handle_enqueue_due_schedules,
        "export-control-plane": _handle_export_control_plane,
        "import-control-plane": _handle_import_control_plane,
        "ingest-account-transactions": _handle_ingest_account_transactions,
        "ingest-configured-csv": _handle_ingest_configured_csv,
        "ingest-contract-prices": _handle_ingest_contract_prices,
        "ingest-subscriptions": _handle_ingest_subscriptions,
        "list-execution-schedules": _handle_list_execution_schedules,
        "list-extensions": _handle_list_extensions,
        "list-ingestion-definitions": _handle_list_ingestion_definitions,
        "list-local-users": _handle_list_local_users,
        "list-runs": _handle_list_runs,
        "list-schedule-dispatches": _handle_list_schedule_dispatches,
        "list-service-tokens": _handle_list_service_tokens,
        "list-worker-heartbeats": _handle_list_worker_heartbeats,
        "mark-schedule-dispatch": _handle_mark_schedule_dispatch,
        "process-account-transactions-inbox": _handle_process_account_transactions_inbox,
        "process-ingestion-definition": _handle_process_ingestion_definition,
        "process-schedule-dispatch": _handle_process_schedule_dispatch,
        "promote-run": _handle_promote_run,
        "recover-stale-schedule-dispatches": _handle_recover_stale_schedule_dispatches,
        "report-contract-prices": _handle_report_contract_prices,
        "report-electricity-prices": _handle_report_electricity_prices,
        "report-monthly-cashflow": _handle_report_monthly_cashflow,
        "report-subscription-summary": _handle_report_subscription_summary,
        "report-utility-cost-summary": _handle_report_utility_cost_summary,
        "reset-local-user-password": _handle_reset_local_user_password,
        "revoke-service-token": _handle_revoke_service_token,
        "run-landing-extension": _handle_run_landing_extension,
        "run-reporting-extension": _handle_run_reporting_extension,
        "run-transformation-extension": _handle_run_transformation_extension,
        "verify-config": _handle_verify_config,
        "watch-account-transactions-inbox": _handle_watch_account_transactions_inbox,
        "watch-schedule-dispatches": _handle_watch_schedule_dispatches,
    }


def dispatch_worker_command(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int | None:
    handler = build_worker_command_handlers().get(args.command)
    if handler is None:
        return None
    return handler(args, runtime)
