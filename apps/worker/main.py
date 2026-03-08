from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
from typing import TextIO

from apps.api.app import serialize_promotion, serialize_run, serialize_summary
from packages.pipelines.account_transaction_inbox import (
    InboxProcessResult,
    process_account_transaction_inbox,
)
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.promotion import (
    promote_contract_price_run,
    promote_run,
    promote_source_asset_run,
    promote_subscription_run,
)
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import (
    ExtensionRegistry,
    load_extension_registry,
    serialize_extension_registry,
)
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=RunMetadataRepository(settings.metadata_database_path),
    )


def build_extension_registry(settings: AppSettings) -> ExtensionRegistry:
    return load_extension_registry(
        extension_paths=settings.extension_paths,
        extension_modules=settings.extension_modules,
    )


def build_config_repository(settings: AppSettings) -> IngestionConfigRepository:
    return IngestionConfigRepository(settings.resolved_config_database_path)


def build_transformation_service(settings: AppSettings) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    return TransformationService(DuckDBStore.open(str(analytics_path)))


def build_subscription_service(settings: AppSettings) -> SubscriptionService:
    return SubscriptionService(
        landing_root=settings.landing_root,
        metadata_repository=RunMetadataRepository(settings.metadata_database_path),
    )


def build_contract_price_service(settings: AppSettings) -> ContractPriceService:
    return ContractPriceService(
        landing_root=settings.landing_root,
        metadata_repository=RunMetadataRepository(settings.metadata_database_path),
    )


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    settings: AppSettings | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    resolved_settings = settings or AppSettings.from_env()
    parser = _build_parser()
    args = parser.parse_args(argv)
    service = build_service(resolved_settings)
    config_repository = build_config_repository(resolved_settings)
    configured_definition_service = ConfiguredIngestionDefinitionService(
        landing_root=resolved_settings.landing_root,
        metadata_repository=service.metadata_repository,
        config_repository=config_repository,
        blob_store=service.blob_store,
    )
    extension_registry = build_extension_registry(resolved_settings)

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
            payload = {"run": serialize_run(run)}
            if run.passed:
                transformation_service = build_transformation_service(resolved_settings)
                resolved_source_asset = source_asset or config_repository.find_source_asset_by_binding(
                    source_system_id=source_system_id,
                    dataset_contract_id=dataset_contract_id,
                    column_mapping_id=column_mapping_id,
                )
                if resolved_source_asset is not None:
                    payload["promotion"] = promote_source_asset_run(
                        run.run_id,
                        source_asset=resolved_source_asset,
                        config_repository=config_repository,
                        landing_root=resolved_settings.landing_root,
                        metadata_repository=service.metadata_repository,
                        transformation_service=transformation_service,
                        blob_store=service.blob_store,
                    )
            _write_json(output, payload)
            return 0

        if args.command == "promote-run":
            transformation_service = build_transformation_service(resolved_settings)
            result = promote_run(
                args.run_id,
                account_service=service,
                transformation_service=transformation_service,
            )
            _write_json(output, {"promotion": {"run_id": result.run_id, **serialize_promotion(result)}})
            return 0

        if args.command == "ingest-subscriptions":
            sub_service = build_subscription_service(resolved_settings)
            run = sub_service.ingest_file(
                Path(args.source_path),
                source_name=args.source_name,
            )
            payload: dict = {"run": serialize_run(run)}
            if run.passed:
                transformation_service = build_transformation_service(resolved_settings)
                promo = promote_subscription_run(
                    run.run_id,
                    subscription_service=sub_service,
                    transformation_service=transformation_service,
                )
                payload["promotion"] = {"run_id": promo.run_id, **serialize_promotion(promo)}
            _write_json(output, payload)
            return 0

        if args.command == "ingest-contract-prices":
            contract_price_service = build_contract_price_service(resolved_settings)
            run = contract_price_service.ingest_file(
                Path(args.source_path),
                source_name=args.source_name,
            )
            payload: dict = {"run": serialize_run(run)}
            if run.passed:
                transformation_service = build_transformation_service(resolved_settings)
                promo = promote_contract_price_run(
                    run.run_id,
                    contract_price_service=contract_price_service,
                    transformation_service=transformation_service,
                )
                payload["promotion"] = {"run_id": promo.run_id, **serialize_promotion(promo)}
            _write_json(output, payload)
            return 0

        if args.command == "report-contract-prices":
            transformation_service = build_transformation_service(resolved_settings)
            _write_json(
                output,
                {
                    "rows": transformation_service.get_contract_price_current(
                        contract_type=getattr(args, "contract_type", None) or None,
                        status=getattr(args, "status", None) or None,
                    )
                },
            )
            return 0

        if args.command == "report-electricity-prices":
            transformation_service = build_transformation_service(resolved_settings)
            _write_json(
                output,
                {"rows": transformation_service.get_electricity_price_current()},
            )
            return 0

        if args.command == "report-subscription-summary":
            transformation_service = build_transformation_service(resolved_settings)
            rows = transformation_service.get_subscription_summary(
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
            payload = {"run": serialize_run(run)}
            if run.passed:
                transformation_service = build_transformation_service(resolved_settings)
                payload["promotion"] = promote_run(
                    run.run_id,
                    account_service=service,
                    transformation_service=transformation_service,
                )
            _write_json(output, payload)
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

        if args.command == "list-extensions":
            _write_json(
                output,
                {"extensions": serialize_extension_registry(extension_registry)},
            )
            return 0

        if args.command == "run-landing-extension":
            result = extension_registry.execute(
                "landing",
                args.extension_key,
                service=service,
                source_path=args.source_path,
                source_name=args.source_name,
            )
            _write_json(output, {"result": result})
            return 0

        if args.command == "process-account-transactions-inbox":
            result = process_account_transaction_inbox(
                service=service,
                inbox_dir=resolved_settings.account_transactions_inbox_dir,
                processed_dir=resolved_settings.processed_files_dir,
                failed_dir=resolved_settings.failed_files_dir,
                source_name=args.source_name,
            )
            _write_json(output, {"result": _serialize_inbox_result(result)})
            return 0

        if args.command == "watch-account-transactions-inbox":
            iterations = 0
            while True:
                result = process_account_transaction_inbox(
                    service=service,
                    inbox_dir=resolved_settings.account_transactions_inbox_dir,
                    processed_dir=resolved_settings.processed_files_dir,
                    failed_dir=resolved_settings.failed_files_dir,
                    source_name=args.source_name,
                )
                _write_json(output, {"result": _serialize_inbox_result(result)})
                iterations += 1
                if (
                    args.max_iterations is not None
                    and iterations >= args.max_iterations
                ):
                    return 0
                time.sleep(resolved_settings.worker_poll_interval_seconds)

        if args.command == "process-ingestion-definition":
            result = configured_definition_service.process_ingestion_definition(
                args.ingestion_definition_id
            )
            payload: dict[str, object] = {"result": result}
            transformation_service = build_transformation_service(resolved_settings)
            ingestion_definition = config_repository.get_ingestion_definition(
                args.ingestion_definition_id
            )
            source_asset = config_repository.get_source_asset(
                ingestion_definition.source_asset_id
            )
            payload["promotions"] = [
                promote_source_asset_run(
                    run_id,
                    source_asset=source_asset,
                    config_repository=config_repository,
                    landing_root=resolved_settings.landing_root,
                    metadata_repository=service.metadata_repository,
                    transformation_service=transformation_service,
                    blob_store=service.blob_store,
                )
                for run_id in result.run_ids
            ]
            _write_json(output, payload)
            return 0

        if args.command == "run-transformation-extension":
            result = extension_registry.execute(
                "transformation",
                args.extension_key,
                service=service,
                run_id=args.run_id,
            )
            _write_json(output, {"result": result})
            return 0

        if args.command == "report-monthly-cashflow":
            summaries = service.get_monthly_cashflow(args.run_id)
            _write_json(
                output,
                {"summaries": [serialize_summary(summary) for summary in summaries]},
            )
            return 0

        if args.command == "run-reporting-extension":
            result = extension_registry.execute(
                "reporting",
                args.extension_key,
                service=service,
                run_id=args.run_id,
            )
            _write_json(output, {"result": result})
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
    report_parser.add_argument("run_id")

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


if __name__ == "__main__":
    raise SystemExit(main())
