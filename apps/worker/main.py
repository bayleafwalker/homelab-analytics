from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO

from apps.api.app import serialize_promotion, serialize_run
from packages.pipelines.account_transaction_inbox import (
    InboxProcessResult,
    process_account_transaction_inbox,
)
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.config_preflight import run_config_preflight
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.promotion import (
    promote_contract_price_run,
    promote_run,
    promote_source_asset_run,
    promote_subscription_run,
)
from packages.pipelines.reporting_service import (
    ReportingAccessMode,
    ReportingService,
    publish_promotion_reporting,
)
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.auth import (
    hash_password,
    maybe_bootstrap_local_admin,
    serialize_user,
)
from packages.shared.extensions import (
    ExtensionRegistry,
    load_extension_registry,
    serialize_extension_registry,
)
from packages.shared.logging import configure_logging
from packages.shared.metrics import metrics_registry
from packages.shared.settings import AppSettings
from packages.storage.auth_store import LocalUserCreate, LocalUserRecord, UserRole
from packages.storage.control_plane import (
    ControlPlaneSnapshot,
    ExecutionScheduleRecord,
    PublicationAuditRecord,
    SourceLineageRecord,
)
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigRecord,
    IngestionDefinitionRecord,
    PublicationDefinitionRecord,
    RequestHeaderSecretRef,
    SourceAssetRecord,
    SourceSystemRecord,
    TransformationPackageRecord,
)
from packages.storage.runtime import (
    build_blob_store,
    build_config_store,
    build_reporting_store,
    build_run_metadata_store,
)


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_extension_registry(settings: AppSettings) -> ExtensionRegistry:
    return load_extension_registry(
        extension_paths=settings.extension_paths,
        extension_modules=settings.extension_modules,
    )


def build_config_repository(settings: AppSettings):
    return build_config_store(settings)


def build_transformation_service(settings: AppSettings) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    return TransformationService(
        DuckDBStore.open(str(analytics_path)),
        control_plane_store=build_config_store(settings),
    )


def build_reporting_service(
    settings: AppSettings,
    transformation_service: TransformationService,
    extension_registry: ExtensionRegistry | None = None,
) -> ReportingService:
    return ReportingService(
        transformation_service,
        publication_store=build_reporting_store(settings),
        extension_registry=extension_registry,
        access_mode=ReportingAccessMode.WAREHOUSE,
        control_plane_store=build_config_store(settings),
    )


def build_subscription_service(settings: AppSettings) -> SubscriptionService:
    return SubscriptionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_contract_price_service(settings: AppSettings) -> ContractPriceService:
    return ContractPriceService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    settings: AppSettings | None = None,
) -> int:
    configure_logging()
    logger = logging.getLogger("homelab_analytics.worker")
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    resolved_settings = settings or AppSettings.from_env()
    parser = _build_parser()
    args = parser.parse_args(argv)
    logger.info("worker command starting", extra={"command": args.command})
    service = build_service(resolved_settings)
    config_repository = build_config_repository(resolved_settings)
    maybe_bootstrap_local_admin(config_repository, resolved_settings)
    configured_definition_service = ConfiguredIngestionDefinitionService(
        landing_root=resolved_settings.landing_root,
        metadata_repository=service.metadata_repository,
        config_repository=config_repository,
        blob_store=service.blob_store,
    )
    extension_registry = build_extension_registry(resolved_settings)

    def publish_reporting(
        reporting_service: ReportingService | None,
        promotion,
    ) -> None:
        publish_promotion_reporting(reporting_service, promotion)

    try:
        if args.command == "ingest-configured-csv":
            from packages.pipelines.configured_csv_ingestion import (
                ConfiguredCsvIngestionService,
            )

            csv_service = ConfiguredCsvIngestionService(
                landing_root=resolved_settings.landing_root,
                metadata_repository=service.metadata_repository,
                config_repository=config_repository,
                blob_store=service.blob_store,
            )
            source_asset = (
                config_repository.get_source_asset(args.source_asset_id)
                if getattr(args, "source_asset_id", None)
                else None
            )
            if source_asset is None and not (
                args.source_system_id and args.dataset_contract_id and args.column_mapping_id
            ):
                raise ValueError(
                    "Configured CSV ingestion requires either --source-asset-id or the full source-system/dataset-contract/column-mapping binding."
                )
            source_system_id = (
                source_asset.source_system_id if source_asset else args.source_system_id
            )
            dataset_contract_id = (
                source_asset.dataset_contract_id
                if source_asset
                else args.dataset_contract_id
            )
            column_mapping_id = (
                source_asset.column_mapping_id if source_asset else args.column_mapping_id
            )
            run = csv_service.ingest_file(
                source_path=Path(args.source_path),
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
                source_name=args.source_name,
            )
            configured_payload: dict[str, object] = {"run": serialize_run(run)}
            if run.passed:
                transformation_service = build_transformation_service(resolved_settings)
                reporting_service = build_reporting_service(
                    resolved_settings,
                    transformation_service,
                    extension_registry,
                )
                resolved_source_asset = source_asset or config_repository.find_source_asset_by_binding(
                    source_system_id=source_system_id,
                    dataset_contract_id=dataset_contract_id,
                    column_mapping_id=column_mapping_id,
                )
                if resolved_source_asset is not None:
                    configured_payload["promotion"] = promote_source_asset_run(
                        run.run_id,
                        source_asset=resolved_source_asset,
                        config_repository=config_repository,
                        landing_root=resolved_settings.landing_root,
                        metadata_repository=service.metadata_repository,
                        transformation_service=transformation_service,
                        blob_store=service.blob_store,
                        extension_registry=extension_registry,
                    )
                    publish_reporting(
                        reporting_service,
                        configured_payload["promotion"],
                    )
            _write_json(output, configured_payload)
            return 0

        if args.command == "promote-run":
            transformation_service = build_transformation_service(resolved_settings)
            reporting_service = build_reporting_service(
                resolved_settings,
                transformation_service,
                extension_registry,
            )
            result = promote_run(
                args.run_id,
                account_service=service,
                transformation_service=transformation_service,
            )
            publish_reporting(reporting_service, result)
            _write_json(output, {"promotion": {"run_id": result.run_id, **serialize_promotion(result)}})
            return 0

        if args.command == "ingest-subscriptions":
            sub_service = build_subscription_service(resolved_settings)
            run = sub_service.ingest_file(
                Path(args.source_path),
                source_name=args.source_name,
            )
            subscription_payload: dict[str, object] = {"run": serialize_run(run)}
            if run.passed:
                transformation_service = build_transformation_service(resolved_settings)
                reporting_service = build_reporting_service(
                    resolved_settings,
                    transformation_service,
                    extension_registry,
                )
                promo = promote_subscription_run(
                    run.run_id,
                    subscription_service=sub_service,
                    transformation_service=transformation_service,
                )
                publish_reporting(reporting_service, promo)
                subscription_payload["promotion"] = {
                    "run_id": promo.run_id,
                    **serialize_promotion(promo),
                }
            _write_json(output, subscription_payload)
            return 0

        if args.command == "ingest-contract-prices":
            contract_price_service = build_contract_price_service(resolved_settings)
            run = contract_price_service.ingest_file(
                Path(args.source_path),
                source_name=args.source_name,
            )
            contract_price_payload: dict[str, object] = {"run": serialize_run(run)}
            if run.passed:
                transformation_service = build_transformation_service(resolved_settings)
                reporting_service = build_reporting_service(
                    resolved_settings,
                    transformation_service,
                    extension_registry,
                )
                promo = promote_contract_price_run(
                    run.run_id,
                    contract_price_service=contract_price_service,
                    transformation_service=transformation_service,
                )
                publish_reporting(reporting_service, promo)
                contract_price_payload["promotion"] = {
                    "run_id": promo.run_id,
                    **serialize_promotion(promo),
                }
            _write_json(output, contract_price_payload)
            return 0

        if args.command == "report-contract-prices":
            transformation_service = build_transformation_service(resolved_settings)
            reporting_service = build_reporting_service(
                resolved_settings,
                transformation_service,
                extension_registry,
            )
            _write_json(
                output,
                {
                    "rows": reporting_service.get_contract_price_current(
                        contract_type=getattr(args, "contract_type", None) or None,
                        status=getattr(args, "status", None) or None,
                    )
                },
            )
            return 0

        if args.command == "report-electricity-prices":
            transformation_service = build_transformation_service(resolved_settings)
            reporting_service = build_reporting_service(
                resolved_settings,
                transformation_service,
                extension_registry,
            )
            _write_json(
                output,
                {"rows": reporting_service.get_electricity_price_current()},
            )
            return 0

        if args.command == "report-subscription-summary":
            transformation_service = build_transformation_service(resolved_settings)
            reporting_service = build_reporting_service(
                resolved_settings,
                transformation_service,
                extension_registry,
            )
            rows = reporting_service.get_subscription_summary(
                status=getattr(args, "status", None) or None,
                currency=getattr(args, "currency", None) or None,
            )
            _write_json(output, {"rows": rows})
            return 0

        if args.command == "ingest-account-transactions":
            run = service.ingest_file(
                Path(args.source_path),
                source_name=args.source_name,
            )
            account_payload: dict[str, object] = {"run": serialize_run(run)}
            if run.passed:
                transformation_service = build_transformation_service(resolved_settings)
                reporting_service = build_reporting_service(
                    resolved_settings,
                    transformation_service,
                    extension_registry,
                )
                account_payload["promotion"] = promote_run(
                    run.run_id,
                    account_service=service,
                    transformation_service=transformation_service,
                )
                publish_reporting(reporting_service, account_payload["promotion"])
            _write_json(output, account_payload)
            return 0

        if args.command == "list-runs":
            _write_json(output, {"runs": [serialize_run(run) for run in service.list_runs()]})
            return 0

        if args.command == "list-ingestion-definitions":
            _write_json(
                output,
                {
                    "ingestion_definitions": config_repository.list_ingestion_definitions()
                },
            )
            return 0

        if args.command == "list-execution-schedules":
            _write_json(
                output,
                {
                    "execution_schedules": config_repository.list_execution_schedules()
                },
            )
            return 0

        if args.command == "list-local-users":
            _write_json(
                output,
                {
                    "users": [
                        serialize_user(user)
                        for user in config_repository.list_local_users()
                    ]
                },
            )
            return 0

        if args.command == "create-local-admin-user":
            user = config_repository.create_local_user(
                LocalUserCreate(
                    user_id=f"user-{args.username}",
                    username=args.username,
                    password_hash=hash_password(args.password),
                    role=UserRole.ADMIN,
                )
            )
            _write_json(output, {"user": serialize_user(user)})
            return 0

        if args.command == "reset-local-user-password":
            user = config_repository.get_local_user_by_username(args.username)
            updated_user = config_repository.update_local_user_password(
                user.user_id,
                password_hash=hash_password(args.password),
            )
            _write_json(output, {"user": serialize_user(updated_user)})
            return 0

        if args.command == "list-schedule-dispatches":
            dispatches = config_repository.list_schedule_dispatches(
                schedule_id=getattr(args, "schedule_id", None) or None,
                status=getattr(args, "status", None) or None,
            )
            metrics_registry.set(
                "worker_queue_depth",
                float(
                    len(
                        [
                            dispatch
                            for dispatch in dispatches
                            if dispatch.status == "enqueued"
                        ]
                    )
                ),
                help_text="Current queued schedule-dispatch count.",
            )
            _write_json(output, {"dispatches": dispatches})
            return 0

        if args.command == "enqueue-due-schedules":
            as_of = (
                datetime.fromisoformat(args.as_of)
                if getattr(args, "as_of", "")
                else None
            )
            dispatches = config_repository.enqueue_due_execution_schedules(
                as_of=as_of,
                limit=getattr(args, "limit", None),
            )
            metrics_registry.set(
                "worker_queue_depth",
                float(
                    len(config_repository.list_schedule_dispatches(status="enqueued"))
                ),
                help_text="Current queued schedule-dispatch count.",
            )
            _write_json(output, {"dispatches": dispatches})
            return 0

        if args.command == "mark-schedule-dispatch":
            dispatch = config_repository.mark_schedule_dispatch_status(
                args.dispatch_id,
                status=args.status,
                completed_at=datetime.now(UTC),
            )
            metrics_registry.set(
                "worker_queue_depth",
                float(
                    len(config_repository.list_schedule_dispatches(status="enqueued"))
                ),
                help_text="Current queued schedule-dispatch count.",
            )
            _write_json(output, {"dispatch": dispatch})
            return 0

        if args.command == "export-control-plane":
            snapshot = config_repository.export_snapshot()
            destination = Path(args.output_path)
            destination.write_text(
                json.dumps(
                    _control_plane_snapshot_to_dict(snapshot),
                    default=_json_default,
                    indent=2,
                )
            )
            _write_json(
                output,
                {
                    "output_path": str(destination),
                    "snapshot": {
                        "source_systems": len(snapshot.source_systems),
                        "dataset_contracts": len(snapshot.dataset_contracts),
                        "column_mappings": len(snapshot.column_mappings),
                        "source_assets": len(snapshot.source_assets),
                        "ingestion_definitions": len(snapshot.ingestion_definitions),
                        "execution_schedules": len(snapshot.execution_schedules),
                        "local_users": len(snapshot.local_users),
                    },
                },
            )
            return 0

        if args.command == "import-control-plane":
            source = Path(args.input_path)
            snapshot = _control_plane_snapshot_from_dict(
                json.loads(source.read_text())
            )
            config_repository.import_snapshot(snapshot)
            _write_json(
                output,
                {
                    "input_path": str(source),
                    "imported": True,
                },
            )
            return 0

        if args.command == "verify-config":
            report = run_config_preflight(
                config_repository,
                extension_registry=extension_registry,
                source_asset_id=getattr(args, "source_asset_id", None) or None,
                ingestion_definition_id=(
                    getattr(args, "ingestion_definition_id", None) or None
                ),
            )
            _write_json(output, {"report": report})
            return 0 if report.passed else 1

        if args.command == "list-extensions":
            _write_json(
                output,
                {"extensions": serialize_extension_registry(extension_registry)},
            )
            return 0

        if args.command == "run-landing-extension":
            landing_result = extension_registry.execute(
                "landing",
                args.extension_key,
                service=service,
                source_path=args.source_path,
                source_name=args.source_name,
            )
            _write_json(output, {"result": landing_result})
            return 0

        if args.command == "process-account-transactions-inbox":
            inbox_result = process_account_transaction_inbox(
                service=service,
                inbox_dir=resolved_settings.account_transactions_inbox_dir,
                processed_dir=resolved_settings.processed_files_dir,
                failed_dir=resolved_settings.failed_files_dir,
                source_name=args.source_name,
            )
            _write_json(output, {"result": _serialize_inbox_result(inbox_result)})
            return 0

        if args.command == "watch-account-transactions-inbox":
            iterations = 0
            while True:
                inbox_result = process_account_transaction_inbox(
                    service=service,
                    inbox_dir=resolved_settings.account_transactions_inbox_dir,
                    processed_dir=resolved_settings.processed_files_dir,
                    failed_dir=resolved_settings.failed_files_dir,
                    source_name=args.source_name,
                )
                _write_json(output, {"result": _serialize_inbox_result(inbox_result)})
                iterations += 1
                if (
                    args.max_iterations is not None
                    and iterations >= args.max_iterations
                ):
                    return 0
                time.sleep(resolved_settings.worker_poll_interval_seconds)

        if args.command == "process-ingestion-definition":
            process_result = configured_definition_service.process_ingestion_definition(
                args.ingestion_definition_id
            )
            process_payload: dict[str, object] = {"result": process_result}
            transformation_service = build_transformation_service(resolved_settings)
            reporting_service = build_reporting_service(
                resolved_settings,
                transformation_service,
                extension_registry,
            )
            ingestion_definition = config_repository.get_ingestion_definition(
                args.ingestion_definition_id
            )
            source_asset = config_repository.get_source_asset(
                ingestion_definition.source_asset_id
            )
            promotions = [
                promote_source_asset_run(
                    run_id,
                    source_asset=source_asset,
                    config_repository=config_repository,
                    landing_root=resolved_settings.landing_root,
                    metadata_repository=service.metadata_repository,
                    transformation_service=transformation_service,
                    blob_store=service.blob_store,
                    extension_registry=extension_registry,
                )
                for run_id in process_result.run_ids
            ]
            for promotion in promotions:
                publish_reporting(reporting_service, promotion)
            process_payload["promotions"] = promotions
            _write_json(output, process_payload)
            return 0

        if args.command == "run-transformation-extension":
            transformation_result = extension_registry.execute(
                "transformation",
                args.extension_key,
                service=service,
                run_id=args.run_id,
            )
            _write_json(output, {"result": transformation_result})
            return 0

        if args.command == "report-monthly-cashflow":
            transformation_service = build_transformation_service(resolved_settings)
            reporting_service = build_reporting_service(
                resolved_settings,
                transformation_service,
                extension_registry,
            )
            _write_json(
                output,
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

        if args.command == "report-utility-cost-summary":
            transformation_service = build_transformation_service(resolved_settings)
            reporting_service = build_reporting_service(
                resolved_settings,
                transformation_service,
                extension_registry,
            )
            _write_json(
                output,
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

        if args.command == "run-reporting-extension":
            transformation_service = build_transformation_service(resolved_settings)
            reporting_service = build_reporting_service(
                resolved_settings,
                transformation_service,
                extension_registry,
            )
            reporting_result = extension_registry.execute(
                "reporting",
                args.extension_key,
                service=service,
                reporting_service=reporting_service,
                transformation_service=transformation_service,
                run_id=args.run_id,
            )
            _write_json(output, {"result": reporting_result})
            return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        error_output.write(f"{exc}\n")
        return 1

    error_output.write("Unknown command\n")
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="homelab-analytics-worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest-account-transactions")
    ingest_parser.add_argument("source_path")
    ingest_parser.add_argument("--source-name", default="manual-upload")

    configured_csv_parser = subparsers.add_parser("ingest-configured-csv")
    configured_csv_parser.add_argument("source_path")
    configured_csv_parser.add_argument("--source-asset-id", default="")
    configured_csv_parser.add_argument("--source-system-id", default="")
    configured_csv_parser.add_argument("--dataset-contract-id", default="")
    configured_csv_parser.add_argument("--column-mapping-id", default="")
    configured_csv_parser.add_argument("--source-name", default="manual-upload")

    subparsers.add_parser("list-runs")
    subparsers.add_parser("list-ingestion-definitions")
    subparsers.add_parser("list-execution-schedules")
    subparsers.add_parser("list-local-users")
    create_admin_parser = subparsers.add_parser("create-local-admin-user")
    create_admin_parser.add_argument("username")
    create_admin_parser.add_argument("password")
    reset_password_parser = subparsers.add_parser("reset-local-user-password")
    reset_password_parser.add_argument("username")
    reset_password_parser.add_argument("password")
    dispatches_parser = subparsers.add_parser("list-schedule-dispatches")
    dispatches_parser.add_argument("--schedule-id", default="")
    dispatches_parser.add_argument("--status", default="")
    enqueue_parser = subparsers.add_parser("enqueue-due-schedules")
    enqueue_parser.add_argument("--as-of", default="")
    enqueue_parser.add_argument("--limit", type=int)
    mark_dispatch_parser = subparsers.add_parser("mark-schedule-dispatch")
    mark_dispatch_parser.add_argument("dispatch_id")
    mark_dispatch_parser.add_argument(
        "--status",
        default="completed",
        choices=["completed", "failed", "running", "enqueued"],
    )
    export_control_plane_parser = subparsers.add_parser("export-control-plane")
    export_control_plane_parser.add_argument("output_path")
    import_control_plane_parser = subparsers.add_parser("import-control-plane")
    import_control_plane_parser.add_argument("input_path")
    verify_config_parser = subparsers.add_parser("verify-config")
    verify_config_parser.add_argument("--source-asset-id", default="")
    verify_config_parser.add_argument("--ingestion-definition-id", default="")
    subparsers.add_parser("list-extensions")

    landing_parser = subparsers.add_parser("run-landing-extension")
    landing_parser.add_argument("extension_key")
    landing_parser.add_argument("source_path")
    landing_parser.add_argument("--source-name", default="manual-upload")

    process_parser = subparsers.add_parser("process-account-transactions-inbox")
    process_parser.add_argument("--source-name", default="folder-watch")

    watch_parser = subparsers.add_parser("watch-account-transactions-inbox")
    watch_parser.add_argument("--source-name", default="folder-watch")
    watch_parser.add_argument("--max-iterations", type=int)

    process_definition_parser = subparsers.add_parser("process-ingestion-definition")
    process_definition_parser.add_argument("ingestion_definition_id")

    transformation_parser = subparsers.add_parser("run-transformation-extension")
    transformation_parser.add_argument("extension_key")
    transformation_parser.add_argument("run_id")

    report_parser = subparsers.add_parser("report-monthly-cashflow")
    report_parser.add_argument("run_id", nargs="?")
    report_parser.add_argument("--from-month", default="")
    report_parser.add_argument("--to-month", default="")

    utility_report_parser = subparsers.add_parser("report-utility-cost-summary")
    utility_report_parser.add_argument("--utility-type", default="")
    utility_report_parser.add_argument("--meter-id", default="")
    utility_report_parser.add_argument("--from-period", default="")
    utility_report_parser.add_argument("--to-period", default="")
    utility_report_parser.add_argument("--granularity", default="month")

    reporting_parser = subparsers.add_parser("run-reporting-extension")
    reporting_parser.add_argument("extension_key")
    reporting_parser.add_argument("run_id")

    promote_parser = subparsers.add_parser("promote-run")
    promote_parser.add_argument("run_id")

    subscription_ingest_parser = subparsers.add_parser("ingest-subscriptions")
    subscription_ingest_parser.add_argument("source_path")
    subscription_ingest_parser.add_argument("--source-name", default="manual-upload")

    subscription_report_parser = subparsers.add_parser("report-subscription-summary")
    subscription_report_parser.add_argument("--status", default="")
    subscription_report_parser.add_argument("--currency", default="")

    contract_price_ingest_parser = subparsers.add_parser("ingest-contract-prices")
    contract_price_ingest_parser.add_argument("source_path")
    contract_price_ingest_parser.add_argument("--source-name", default="manual-upload")

    contract_price_report_parser = subparsers.add_parser("report-contract-prices")
    contract_price_report_parser.add_argument("--contract-type", default="")
    contract_price_report_parser.add_argument("--status", default="")

    subparsers.add_parser("report-electricity-prices")

    return parser


def _write_json(output: TextIO, payload: dict) -> None:
    output.write(f"{json.dumps(payload, default=_json_default)}\n")


def _serialize_inbox_result(result: InboxProcessResult) -> dict[str, int]:
    return {
        "discovered_files": result.discovered_files,
        "processed_files": result.processed_files,
        "rejected_files": result.rejected_files,
    }


def _json_default(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {value!r}")


def _control_plane_snapshot_to_dict(snapshot: ControlPlaneSnapshot) -> dict[str, object]:
    return {
        "source_systems": list(snapshot.source_systems),
        "dataset_contracts": list(snapshot.dataset_contracts),
        "column_mappings": list(snapshot.column_mappings),
        "transformation_packages": list(snapshot.transformation_packages),
        "publication_definitions": list(snapshot.publication_definitions),
        "source_assets": list(snapshot.source_assets),
        "ingestion_definitions": list(snapshot.ingestion_definitions),
        "execution_schedules": list(snapshot.execution_schedules),
        "source_lineage": list(snapshot.source_lineage),
        "publication_audit": list(snapshot.publication_audit),
        "local_users": list(snapshot.local_users),
    }


def _control_plane_snapshot_from_dict(payload: dict[str, Any]) -> ControlPlaneSnapshot:
    return ControlPlaneSnapshot(
        source_systems=tuple(
            SourceSystemRecord(
                source_system_id=item["source_system_id"],
                name=item["name"],
                source_type=item["source_type"],
                transport=item["transport"],
                schedule_mode=item["schedule_mode"],
                description=item.get("description"),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("source_systems", [])
        ),
        dataset_contracts=tuple(
            DatasetContractConfigRecord(
                dataset_contract_id=item["dataset_contract_id"],
                dataset_name=item["dataset_name"],
                version=item["version"],
                allow_extra_columns=item["allow_extra_columns"],
                columns=tuple(
                    DatasetColumnConfig(
                        name=column["name"],
                        type=ColumnType(column["type"]),
                        required=column["required"],
                    )
                    for column in item["columns"]
                ),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("dataset_contracts", [])
        ),
        column_mappings=tuple(
            ColumnMappingRecord(
                column_mapping_id=item["column_mapping_id"],
                source_system_id=item["source_system_id"],
                dataset_contract_id=item["dataset_contract_id"],
                version=item["version"],
                rules=tuple(
                    ColumnMappingRule(
                        target_column=rule["target_column"],
                        source_column=rule.get("source_column"),
                        default_value=rule.get("default_value"),
                    )
                    for rule in item["rules"]
                ),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("column_mappings", [])
        ),
        transformation_packages=tuple(
            TransformationPackageRecord(
                transformation_package_id=item["transformation_package_id"],
                name=item["name"],
                handler_key=item["handler_key"],
                version=item["version"],
                description=item.get("description"),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("transformation_packages", [])
        ),
        publication_definitions=tuple(
            PublicationDefinitionRecord(
                publication_definition_id=item["publication_definition_id"],
                transformation_package_id=item["transformation_package_id"],
                publication_key=item["publication_key"],
                name=item["name"],
                description=item.get("description"),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("publication_definitions", [])
        ),
        source_assets=tuple(
            SourceAssetRecord(
                source_asset_id=item["source_asset_id"],
                source_system_id=item["source_system_id"],
                dataset_contract_id=item["dataset_contract_id"],
                column_mapping_id=item["column_mapping_id"],
                transformation_package_id=item.get("transformation_package_id"),
                name=item["name"],
                asset_type=item["asset_type"],
                description=item.get("description"),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("source_assets", [])
        ),
        ingestion_definitions=tuple(
            IngestionDefinitionRecord(
                ingestion_definition_id=item["ingestion_definition_id"],
                source_asset_id=item["source_asset_id"],
                transport=item["transport"],
                schedule_mode=item["schedule_mode"],
                source_path=item["source_path"],
                file_pattern=item["file_pattern"],
                processed_path=item.get("processed_path"),
                failed_path=item.get("failed_path"),
                poll_interval_seconds=item.get("poll_interval_seconds"),
                request_url=item.get("request_url"),
                request_method=item.get("request_method"),
                request_headers=tuple(
                    RequestHeaderSecretRef(
                        name=header["name"],
                        secret_name=header["secret_name"],
                        secret_key=header["secret_key"],
                    )
                    for header in item.get("request_headers", [])
                ),
                request_timeout_seconds=item.get("request_timeout_seconds"),
                response_format=item.get("response_format"),
                output_file_name=item.get("output_file_name"),
                enabled=item["enabled"],
                source_name=item.get("source_name"),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("ingestion_definitions", [])
        ),
        execution_schedules=tuple(
            ExecutionScheduleRecord(
                schedule_id=item["schedule_id"],
                target_kind=item["target_kind"],
                target_ref=item["target_ref"],
                cron_expression=item["cron_expression"],
                timezone=item["timezone"],
                enabled=item["enabled"],
                max_concurrency=item["max_concurrency"],
                next_due_at=(
                    datetime.fromisoformat(item["next_due_at"])
                    if item.get("next_due_at")
                    else None
                ),
                last_enqueued_at=(
                    datetime.fromisoformat(item["last_enqueued_at"])
                    if item.get("last_enqueued_at")
                    else None
                ),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("execution_schedules", [])
        ),
        source_lineage=tuple(
            SourceLineageRecord(
                lineage_id=item["lineage_id"],
                input_run_id=item.get("input_run_id"),
                target_layer=item["target_layer"],
                target_name=item["target_name"],
                target_kind=item["target_kind"],
                row_count=item.get("row_count"),
                source_system=item.get("source_system"),
                source_run_id=item.get("source_run_id"),
                recorded_at=datetime.fromisoformat(item["recorded_at"]),
            )
            for item in payload.get("source_lineage", [])
        ),
        publication_audit=tuple(
            PublicationAuditRecord(
                publication_audit_id=item["publication_audit_id"],
                run_id=item.get("run_id"),
                publication_key=item["publication_key"],
                relation_name=item["relation_name"],
                status=item["status"],
                published_at=datetime.fromisoformat(item["published_at"]),
            )
            for item in payload.get("publication_audit", [])
        ),
        local_users=tuple(
            LocalUserRecord(
                user_id=item["user_id"],
                username=item["username"],
                password_hash=item["password_hash"],
                role=UserRole(item["role"]),
                enabled=item["enabled"],
                created_at=datetime.fromisoformat(item["created_at"]),
                last_login_at=(
                    datetime.fromisoformat(item["last_login_at"])
                    if item.get("last_login_at")
                    else None
                ),
            )
            for item in payload.get("local_users", [])
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
