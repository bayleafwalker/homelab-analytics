"""Worker command handler package — thin dispatcher over family modules."""
from __future__ import annotations

from argparse import Namespace
from collections.abc import Callable

from apps.worker.runtime import WorkerRuntime

from .admin_commands import (
    handle_create_local_admin_user,
    handle_create_service_token,
    handle_export_control_plane,
    handle_import_control_plane,
    handle_list_execution_schedules,
    handle_list_ingestion_definitions,
    handle_list_local_users,
    handle_list_runs,
    handle_list_service_tokens,
    handle_reset_local_user_password,
    handle_revoke_service_token,
    handle_verify_config,
)
from .ingest_commands import (
    handle_generate_demo_data,
    handle_ingest_account_transactions,
    handle_ingest_configured_csv,
    handle_ingest_contract_prices,
    handle_ingest_subscriptions,
    handle_process_account_transactions_inbox,
    handle_process_ingestion_definition,
    handle_promote_run,
    handle_report_contract_prices,
    handle_report_electricity_prices,
    handle_report_monthly_cashflow,
    handle_report_subscription_summary,
    handle_report_utility_cost_summary,
    handle_run_landing_extension,
    handle_run_reporting_extension,
    handle_run_transformation_extension,
    handle_seed_demo_data,
    handle_watch_account_transactions_inbox,
)
from .registry_commands import (
    handle_list_extension_registry_activations,
    handle_list_extension_registry_revisions,
    handle_list_extension_registry_sources,
    handle_list_extensions,
    handle_list_functions,
    handle_list_publication_definitions,
    handle_list_publication_keys,
    handle_list_transformation_handlers,
    handle_list_transformation_packages,
    handle_sync_extension_registry_source,
)
from .schedule_commands import (
    handle_enqueue_due_schedules,
    handle_list_schedule_dispatches,
    handle_list_worker_heartbeats,
    handle_mark_schedule_dispatch,
    handle_process_schedule_dispatch,
    handle_recover_stale_schedule_dispatches,
    handle_watch_schedule_dispatches,
)

WorkerCommandHandler = Callable[[Namespace, WorkerRuntime], int]


def build_worker_command_handlers() -> dict[str, WorkerCommandHandler]:
    return {
        "create-local-admin-user": handle_create_local_admin_user,
        "create-service-token": handle_create_service_token,
        "enqueue-due-schedules": handle_enqueue_due_schedules,
        "export-control-plane": handle_export_control_plane,
        "generate-demo-data": handle_generate_demo_data,
        "import-control-plane": handle_import_control_plane,
        "ingest-account-transactions": handle_ingest_account_transactions,
        "ingest-configured-csv": handle_ingest_configured_csv,
        "ingest-contract-prices": handle_ingest_contract_prices,
        "ingest-subscriptions": handle_ingest_subscriptions,
        "list-extension-registry-activations": handle_list_extension_registry_activations,
        "list-extension-registry-revisions": handle_list_extension_registry_revisions,
        "list-extension-registry-sources": handle_list_extension_registry_sources,
        "list-execution-schedules": handle_list_execution_schedules,
        "list-extensions": handle_list_extensions,
        "list-functions": handle_list_functions,
        "list-ingestion-definitions": handle_list_ingestion_definitions,
        "list-local-users": handle_list_local_users,
        "list-publication-definitions": handle_list_publication_definitions,
        "list-publication-keys": handle_list_publication_keys,
        "list-runs": handle_list_runs,
        "list-schedule-dispatches": handle_list_schedule_dispatches,
        "list-service-tokens": handle_list_service_tokens,
        "list-transformation-handlers": handle_list_transformation_handlers,
        "list-transformation-packages": handle_list_transformation_packages,
        "list-worker-heartbeats": handle_list_worker_heartbeats,
        "mark-schedule-dispatch": handle_mark_schedule_dispatch,
        "process-account-transactions-inbox": handle_process_account_transactions_inbox,
        "process-ingestion-definition": handle_process_ingestion_definition,
        "process-schedule-dispatch": handle_process_schedule_dispatch,
        "promote-run": handle_promote_run,
        "recover-stale-schedule-dispatches": handle_recover_stale_schedule_dispatches,
        "report-contract-prices": handle_report_contract_prices,
        "report-electricity-prices": handle_report_electricity_prices,
        "report-monthly-cashflow": handle_report_monthly_cashflow,
        "report-subscription-summary": handle_report_subscription_summary,
        "report-utility-cost-summary": handle_report_utility_cost_summary,
        "reset-local-user-password": handle_reset_local_user_password,
        "revoke-service-token": handle_revoke_service_token,
        "run-landing-extension": handle_run_landing_extension,
        "run-reporting-extension": handle_run_reporting_extension,
        "run-transformation-extension": handle_run_transformation_extension,
        "seed-demo-data": handle_seed_demo_data,
        "sync-extension-registry-source": handle_sync_extension_registry_source,
        "verify-config": handle_verify_config,
        "watch-account-transactions-inbox": handle_watch_account_transactions_inbox,
        "watch-schedule-dispatches": handle_watch_schedule_dispatches,
    }


def dispatch_worker_command(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int | None:
    handler = build_worker_command_handlers().get(args.command)
    if handler is None:
        return None
    return handler(args, runtime)
