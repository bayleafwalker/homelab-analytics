"""Ingest, promote, and report worker command handlers."""
from __future__ import annotations

import time
from argparse import Namespace
from pathlib import Path

from apps.api.app import serialize_promotion, serialize_run
from apps.worker.control_plane import (
    _process_account_transaction_watch_folder,
    _process_configured_ingestion_definition,
)
from apps.worker.runtime import (
    WorkerRuntime,
    build_contract_price_service,
    build_reporting_service,
    build_subscription_service,
    build_transformation_service,
)
from apps.worker.serialization import (
    _serialize_inbox_result,
    _write_json,
)
from packages.demo import seed_demo_data, write_demo_bundle
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


def handle_ingest_account_transactions(args: Namespace, runtime: WorkerRuntime) -> int:
    # Dev/demo shortcut. Operator path is ingest-configured-csv.
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


def handle_generate_demo_data(args: Namespace, runtime: WorkerRuntime) -> int:
    output_dir = Path(args.output_dir)
    manifest = write_demo_bundle(output_dir)
    _write_json(
        runtime.output,
        {
            "output_dir": str(output_dir),
            "manifest_path": str(output_dir / "manifest.json"),
            "artifact_count": len(manifest["artifacts"]),
            "seed": manifest["seed"],
        },
    )
    return 0


def handle_seed_demo_data(args: Namespace, runtime: WorkerRuntime) -> int:
    payload = seed_demo_data(runtime.settings, Path(args.input_dir))
    _write_json(runtime.output, payload)
    return 0


def handle_ingest_configured_csv(args: Namespace, runtime: WorkerRuntime) -> int:
    from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService

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
            "Configured CSV ingestion requires either --source-asset-id or the full"
            " source-system/dataset-contract/column-mapping binding."
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


def handle_ingest_subscriptions(args: Namespace, runtime: WorkerRuntime) -> int:
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


def handle_ingest_contract_prices(args: Namespace, runtime: WorkerRuntime) -> int:
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


def handle_promote_run(args: Namespace, runtime: WorkerRuntime) -> int:
    transformation_service, reporting_service = _build_reporting_runtime(runtime)
    result = promote_run(
        args.run_id,
        account_service=runtime.service,
        transformation_service=transformation_service,
    )
    _publish_reporting(reporting_service, result)
    _write_json(runtime.output, {"promotion": _serialize_promotion_payload(result)})
    return 0


def handle_process_account_transactions_inbox(args: Namespace, runtime: WorkerRuntime) -> int:
    inbox_result = _process_account_transaction_watch_folder(
        settings=runtime.settings,
        config_repository=runtime.config_repository,
        configured_definition_service=runtime.configured_definition_service,
        source_name=args.source_name,
    )
    _write_json(runtime.output, {"result": _serialize_inbox_result(inbox_result)})
    return 0


def handle_watch_account_transactions_inbox(args: Namespace, runtime: WorkerRuntime) -> int:
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


def handle_process_ingestion_definition(args: Namespace, runtime: WorkerRuntime) -> int:
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


def handle_run_landing_extension(args: Namespace, runtime: WorkerRuntime) -> int:
    landing_result = runtime.extension_registry.execute(
        "landing",
        args.extension_key,
        service=runtime.service,
        source_path=args.source_path,
        source_name=args.source_name,
    )
    _write_json(runtime.output, {"result": landing_result})
    return 0


def handle_run_transformation_extension(args: Namespace, runtime: WorkerRuntime) -> int:
    transformation_result = runtime.extension_registry.execute(
        "transformation",
        args.extension_key,
        service=runtime.service,
        run_id=args.run_id,
    )
    _write_json(runtime.output, {"result": transformation_result})
    return 0


def handle_run_reporting_extension(args: Namespace, runtime: WorkerRuntime) -> int:
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


def handle_report_monthly_cashflow(args: Namespace, runtime: WorkerRuntime) -> int:
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


def handle_report_utility_cost_summary(args: Namespace, runtime: WorkerRuntime) -> int:
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


def handle_report_contract_prices(args: Namespace, runtime: WorkerRuntime) -> int:
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


def handle_report_electricity_prices(args: Namespace, runtime: WorkerRuntime) -> int:
    _, reporting_service = _build_reporting_runtime(runtime)
    _write_json(
        runtime.output,
        {"rows": reporting_service.get_electricity_price_current()},
    )
    return 0


def handle_report_subscription_summary(args: Namespace, runtime: WorkerRuntime) -> int:
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
