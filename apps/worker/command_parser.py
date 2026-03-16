from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
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
    list_service_tokens_parser = subparsers.add_parser("list-service-tokens")
    list_service_tokens_parser.add_argument("--include-revoked", action="store_true")
    create_admin_parser = subparsers.add_parser("create-local-admin-user")
    create_admin_parser.add_argument("username")
    create_admin_parser.add_argument("password")
    create_service_token_parser = subparsers.add_parser("create-service-token")
    create_service_token_parser.add_argument("token_name")
    create_service_token_parser.add_argument(
        "--role",
        default="reader",
        choices=["reader", "operator", "admin"],
    )
    create_service_token_parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Repeatable service-token scope.",
    )
    create_service_token_parser.add_argument("--expires-at", default="")
    reset_password_parser = subparsers.add_parser("reset-local-user-password")
    reset_password_parser.add_argument("username")
    reset_password_parser.add_argument("password")
    revoke_service_token_parser = subparsers.add_parser("revoke-service-token")
    revoke_service_token_parser.add_argument("token_id")
    dispatches_parser = subparsers.add_parser("list-schedule-dispatches")
    dispatches_parser.add_argument("--schedule-id", default="")
    dispatches_parser.add_argument("--status", default="")
    subparsers.add_parser("list-worker-heartbeats")
    enqueue_parser = subparsers.add_parser("enqueue-due-schedules")
    enqueue_parser.add_argument("--as-of", default="")
    enqueue_parser.add_argument("--limit", type=int)
    recover_dispatches_parser = subparsers.add_parser(
        "recover-stale-schedule-dispatches"
    )
    recover_dispatches_parser.add_argument("--as-of", default="")
    recover_dispatches_parser.add_argument("--limit", type=int)
    recover_dispatches_parser.add_argument("--worker-id", default="")
    mark_dispatch_parser = subparsers.add_parser("mark-schedule-dispatch")
    mark_dispatch_parser.add_argument("dispatch_id")
    mark_dispatch_parser.add_argument(
        "--status",
        default="completed",
        choices=["completed", "failed", "running", "enqueued"],
    )
    process_dispatch_parser = subparsers.add_parser("process-schedule-dispatch")
    process_dispatch_parser.add_argument("dispatch_id")
    process_dispatch_parser.add_argument("--worker-id", default="")
    process_dispatch_parser.add_argument("--lease-seconds", type=int)
    watch_dispatch_parser = subparsers.add_parser("watch-schedule-dispatches")
    watch_dispatch_parser.add_argument("--worker-id", default="")
    watch_dispatch_parser.add_argument("--lease-seconds", type=int)
    watch_dispatch_parser.add_argument("--enqueue-limit", type=int)
    watch_dispatch_parser.add_argument("--recover-limit", type=int)
    watch_dispatch_parser.add_argument("--max-iterations", type=int)
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
