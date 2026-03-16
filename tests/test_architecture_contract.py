from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest

from packages.pipelines.promotion import promote_source_asset_run
from packages.shared.extensions import build_builtin_extension_registry

pytestmark = [pytest.mark.architecture]

ROOT = Path(__file__).resolve().parents[1]


def _import_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    return names


def test_transformation_service_does_not_import_application_or_reporting_modules() -> None:
    path = ROOT / "packages" / "pipelines" / "transformation_service.py"
    imports = _import_names(path)

    assert not any(name.startswith("apps") for name in imports)
    assert not any(name.startswith("packages.analytics") for name in imports)


def test_transformation_service_imports_split_domain_modules() -> None:
    imports = _import_names(ROOT / "packages" / "pipelines" / "transformation_service.py")

    assert "packages.pipelines.transformation_domain_registry" in imports
    assert "packages.pipelines.transformation_refresh_registry" in imports
    assert "packages.pipelines.transformation_transactions" in imports
    assert "packages.pipelines.transformation_subscriptions" in imports
    assert "packages.pipelines.transformation_contract_prices" in imports
    assert "packages.pipelines.transformation_utilities" in imports


def test_app_reporting_paths_do_not_compute_cashflow_from_landing_service() -> None:
    api_source = (ROOT / "apps" / "api" / "routes" / "report_routes.py").read_text()
    web_dashboard_source = (ROOT / "apps" / "web" / "frontend" / "app" / "page.js").read_text()
    web_backend_source = (ROOT / "apps" / "web" / "frontend" / "lib" / "backend.js").read_text()

    legacy_call_re = re.compile(r"(?<![A-Za-z0-9_])service\.get_monthly_cashflow\(")
    direct_transform_re = re.compile(
        r"(?<![A-Za-z0-9_])transformation_service\.get_monthly_cashflow\("
    )

    assert legacy_call_re.search(api_source) is None
    assert direct_transform_re.search(api_source) is None
    assert "resolved_reporting_service.get_monthly_cashflow(" in api_source
    assert "getMonthlyCashflow" in web_dashboard_source
    assert "HOMELAB_ANALYTICS_API_BASE_URL" in web_backend_source
    assert "ReportingService(" not in web_dashboard_source


def test_app_reporting_routes_flow_through_reporting_service_contract() -> None:
    api_source = (ROOT / "apps" / "api" / "routes" / "report_routes.py").read_text()
    api_app_source = (ROOT / "apps" / "api" / "app.py").read_text()
    worker_handler_source = (ROOT / "apps" / "worker" / "command_handlers.py").read_text()
    worker_control_plane_source = (ROOT / "apps" / "worker" / "control_plane.py").read_text()

    assert "resolved_reporting_service.get_transformation_audit(" in api_source
    assert "reporting_service=resolved_reporting_service" in api_source
    assert "publish_promotion_reporting(" in api_app_source
    assert "publish_promotion_reporting(" in worker_handler_source
    assert "publish_promotion_reporting(" in worker_control_plane_source


def test_runtime_builders_preserve_published_vs_warehouse_reporting_boundary() -> None:
    api_main_source = (ROOT / "apps" / "api" / "main.py").read_text()
    web_main_source = (ROOT / "apps" / "web" / "main.py").read_text()
    web_app_source = (ROOT / "apps" / "web" / "app.py").read_text()
    worker_runtime_source = (ROOT / "apps" / "worker" / "runtime.py").read_text()

    assert "ReportingAccessMode.PUBLISHED" in api_main_source
    assert "build_pipeline_registries(" in api_main_source
    assert "domain_registry=pipeline_registries.transformation_domain_registry" in api_main_source
    assert 'settings.reporting_backend.lower() == "postgres"' in api_main_source
    assert "load_pipeline_registries(" in worker_runtime_source
    assert "domain_registry=domain_registry" in worker_runtime_source
    assert "access_mode=ReportingAccessMode.WAREHOUSE" in worker_runtime_source
    assert "build_web_environment" in web_main_source
    assert "HOMELAB_ANALYTICS_API_BASE_URL" in web_app_source


def test_worker_main_delegates_to_runtime_and_command_handlers() -> None:
    worker_main_source = (ROOT / "apps" / "worker" / "main.py").read_text()
    worker_handler_source = (ROOT / "apps" / "worker" / "command_handlers.py").read_text()

    assert "build_worker_runtime(" in worker_main_source
    assert "dispatch_worker_command(" in worker_main_source
    assert "build_worker_command_handlers()" in worker_handler_source
    assert '"watch-schedule-dispatches"' in worker_handler_source


def test_api_app_imports_shared_support_modules() -> None:
    imports = _import_names(ROOT / "apps" / "api" / "app.py")

    assert "apps.api.auth_runtime" in imports
    assert "apps.api.support" in imports
    assert "apps.api.runtime_state" in imports


def test_promotion_orchestration_imports_shared_registry_contracts() -> None:
    imports = _import_names(ROOT / "packages" / "pipelines" / "promotion.py")
    builtin_handler_imports = _import_names(
        ROOT / "packages" / "pipelines" / "builtin_promotion_handlers.py"
    )
    promotion_registry_imports = _import_names(
        ROOT / "packages" / "pipelines" / "promotion_registry.py"
    )

    assert "packages.pipelines.promotion_registry" in imports
    assert "packages.pipelines.builtin_promotion_handlers" in imports
    assert "packages.pipelines.promotion_types" in imports
    assert "packages.pipelines.promotion_registry" in builtin_handler_imports
    assert "packages.pipelines.transformation_domain_registry" in promotion_registry_imports


def test_reporting_service_imports_shared_builtin_reporting_registry() -> None:
    imports = _import_names(ROOT / "packages" / "pipelines" / "reporting_service.py")

    assert "packages.pipelines.builtin_reporting" in imports


def test_postgres_ingestion_backend_imports_split_catalog_modules() -> None:
    imports = _import_names(ROOT / "packages" / "storage" / "postgres_ingestion_config.py")

    assert "packages.storage.control_plane_snapshot" in imports
    assert "packages.storage.postgres_asset_definition_catalog" in imports
    assert "packages.storage.postgres_auth_control_plane" in imports
    assert "packages.storage.postgres_control_plane_schema" in imports
    assert "packages.storage.postgres_execution_control_plane" in imports
    assert "packages.storage.postgres_provenance_control_plane" in imports
    assert "packages.storage.postgres_source_contract_catalog" in imports
    assert "packages.storage.ingestion_config" not in imports


def test_sqlite_ingestion_backend_imports_split_catalog_modules() -> None:
    imports = _import_names(ROOT / "packages" / "storage" / "ingestion_config.py")

    assert "packages.storage.ingestion_catalog" in imports
    assert "packages.storage.control_plane_snapshot" in imports
    assert "packages.storage.sqlite_asset_definition_catalog" in imports
    assert "packages.storage.sqlite_auth_control_plane" in imports
    assert "packages.storage.sqlite_control_plane_schema" in imports
    assert "packages.storage.sqlite_execution_control_plane" in imports
    assert "packages.storage.sqlite_provenance_control_plane" in imports
    assert "packages.storage.sqlite_source_contract_catalog" in imports


def test_app_and_web_routes_are_auth_protected_when_local_auth_is_enabled() -> None:
    api_source = (ROOT / "apps" / "api" / "app.py").read_text()
    auth_runtime_source = (ROOT / "apps" / "api" / "auth_runtime.py").read_text()
    auth_route_source = (ROOT / "apps" / "api" / "routes" / "auth_routes.py").read_text()
    control_route_source = (ROOT / "apps" / "api" / "routes" / "control_routes.py").read_text()
    ingest_route_source = (ROOT / "apps" / "api" / "routes" / "ingest_routes.py").read_text()
    run_route_source = (ROOT / "apps" / "api" / "routes" / "run_routes.py").read_text()
    api_main_source = (ROOT / "apps" / "api" / "main.py").read_text()
    web_backend_source = (ROOT / "apps" / "web" / "frontend" / "lib" / "backend.js").read_text()
    web_control_page = (
        ROOT / "apps" / "web" / "frontend" / "app" / "control" / "page.js"
    ).read_text()
    web_control_catalog_page = (
        ROOT / "apps" / "web" / "frontend" / "app" / "control" / "catalog" / "page.js"
    ).read_text()
    web_dataset_contract_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "catalog"
        / "dataset-contracts"
        / "route.js"
    ).read_text()
    web_column_mapping_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "catalog"
        / "column-mappings"
        / "route.js"
    ).read_text()
    web_preview_route = (
        ROOT / "apps" / "web" / "frontend" / "app" / "control" / "catalog" / "preview" / "route.js"
    ).read_text()
    web_control_execution_page = (
        ROOT / "apps" / "web" / "frontend" / "app" / "control" / "execution" / "page.js"
    ).read_text()
    web_upload_page = (
        ROOT / "apps" / "web" / "frontend" / "app" / "upload" / "page.js"
    ).read_text()
    web_upload_route_helper = (
        ROOT / "apps" / "web" / "frontend" / "lib" / "upload-route.js"
    ).read_text()
    web_upload_configured_route = (
        ROOT / "apps" / "web" / "frontend" / "app" / "upload" / "configured-csv" / "route.js"
    ).read_text()
    web_run_detail_page = (
        ROOT / "apps" / "web" / "frontend" / "app" / "runs" / "[runId]" / "page.js"
    ).read_text()
    web_source_system_update_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "catalog"
        / "source-systems"
        / "[sourceSystemId]"
        / "route.js"
    ).read_text()
    web_source_asset_update_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "catalog"
        / "source-assets"
        / "[sourceAssetId]"
        / "route.js"
    ).read_text()
    web_source_asset_archive_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "catalog"
        / "source-assets"
        / "[sourceAssetId]"
        / "archive"
        / "route.js"
    ).read_text()
    web_source_asset_delete_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "catalog"
        / "source-assets"
        / "[sourceAssetId]"
        / "delete"
        / "route.js"
    ).read_text()
    web_ingestion_definition_update_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "[ingestionDefinitionId]"
        / "route.js"
    ).read_text()
    web_ingestion_definition_archive_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "[ingestionDefinitionId]"
        / "archive"
        / "route.js"
    ).read_text()
    web_ingestion_definition_delete_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "[ingestionDefinitionId]"
        / "delete"
        / "route.js"
    ).read_text()
    web_schedule_update_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "execution-schedules"
        / "[scheduleId]"
        / "route.js"
    ).read_text()
    web_schedule_archive_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "execution-schedules"
        / "[scheduleId]"
        / "archive"
        / "route.js"
    ).read_text()
    web_schedule_delete_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "execution-schedules"
        / "[scheduleId]"
        / "delete"
        / "route.js"
    ).read_text()
    web_schedule_dispatch_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "schedule-dispatches"
        / "route.js"
    ).read_text()
    web_dispatch_detail_page = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "dispatches"
        / "[dispatchId]"
        / "page.js"
    ).read_text()
    web_dispatch_retry_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "execution"
        / "dispatches"
        / "[dispatchId]"
        / "retry"
        / "route.js"
    ).read_text()
    web_login_page = (ROOT / "apps" / "web" / "frontend" / "app" / "login" / "page.js").read_text()
    web_login_route = (
        ROOT / "apps" / "web" / "frontend" / "app" / "auth" / "login" / "route.js"
    ).read_text()
    web_callback_route = (
        ROOT / "apps" / "web" / "frontend" / "app" / "auth" / "callback" / "route.js"
    ).read_text()
    web_logout_route = (
        ROOT / "apps" / "web" / "frontend" / "app" / "auth" / "logout" / "route.js"
    ).read_text()
    web_ready_route = (
        ROOT / "apps" / "web" / "frontend" / "app" / "ready" / "route.js"
    ).read_text()
    web_service_token_route = (
        ROOT / "apps" / "web" / "frontend" / "app" / "control" / "service-tokens" / "route.js"
    ).read_text()
    web_service_token_revoke_route = (
        ROOT
        / "apps"
        / "web"
        / "frontend"
        / "app"
        / "control"
        / "service-tokens"
        / "[tokenId]"
        / "revoke"
        / "route.js"
    ).read_text()
    web_service_token_panel = (
        ROOT / "apps" / "web" / "frontend" / "components" / "service-token-panel.js"
    ).read_text()
    web_run_retry_route = (
        ROOT / "apps" / "web" / "frontend" / "app" / "runs" / "[runId]" / "retry" / "route.js"
    ).read_text()
    web_main_source = (ROOT / "apps" / "web" / "main.py").read_text()

    assert "register_auth_middleware(" in api_source
    assert "build_auth_event_recorder(" in api_source
    assert "required_role_for_path" in auth_runtime_source
    assert "Authentication required." in auth_runtime_source
    assert "CSRF validation failed." in auth_runtime_source
    assert '"/auth/users"' in auth_runtime_source
    assert '"/auth/service-tokens"' in auth_runtime_source
    assert '"/control/auth-audit"' in auth_runtime_source
    assert '"/auth/users"' in auth_route_source
    assert '"/auth/service-tokens"' in auth_route_source
    assert '"/control/auth-audit"' in auth_route_source
    assert '"/control/source-lineage"' in control_route_source
    assert '"/control/publication-audit"' in control_route_source
    assert '"/control/schedule-dispatches"' in control_route_source
    assert '"/control/operational-summary"' in control_route_source
    assert '"/ready"' in api_source
    assert '"/ingest/configured-csv"' in ingest_route_source
    assert '"/transformations/{extension_key}"' in ingest_route_source
    assert '"/runs/{run_id}/retry"' in run_route_source
    assert "register_auth_routes(" in api_source
    assert "register_ingest_routes(" in api_source
    assert "auth_mode=resolved_settings.auth_mode" in api_main_source
    assert "session_manager=build_session_manager(resolved_settings)" in api_main_source
    assert "oidc_provider=build_oidc_provider(resolved_settings)" in api_main_source
    assert "maybe_bootstrap_local_admin" in api_main_source
    assert 'action="/auth/login"' in web_login_page
    assert "Sign In with OIDC" in web_login_page
    assert 'backendRequest("/auth/login"' in web_login_route
    assert "backendRequest(`/auth/callback${search}`" in web_callback_route
    assert 'backendRequest("/auth/logout"' in web_logout_route
    assert 'status: "ready"' in web_ready_route
    assert 'outboundHeaders.set("x-csrf-token", csrfToken)' in web_backend_source
    assert "getLocalUsers" in web_control_page
    assert "getAuthAuditEvents" in web_control_page
    assert "getOperationalSummary" in web_control_page
    assert "getServiceTokens" in web_control_page
    assert 'backendRequest("/auth/service-tokens"' in web_service_token_route
    assert "/auth/service-tokens/${params.tokenId}/revoke" in web_service_token_revoke_route
    assert 'fetch("/control/service-tokens"' in web_service_token_panel
    assert "expiring soon" in web_service_token_panel
    assert "getSourceSystems" in web_control_catalog_page
    assert "getSourceAssets" in web_control_catalog_page
    assert "getDatasetContracts({ includeArchived: true })" in web_control_catalog_page
    assert "getColumnMappings({ includeArchived: true })" in web_control_catalog_page
    assert "getOperationalSummary" in web_control_catalog_page
    assert "MappingPreviewPanel" in web_control_catalog_page
    assert "/config/dataset-contracts" in web_dataset_contract_route
    assert "/config/column-mappings" in web_column_mapping_route
    assert 'backendRequest("/config/column-mappings/preview"' in web_preview_route
    assert "getIngestionDefinitions" in web_control_execution_page
    assert "getExecutionSchedules" in web_control_execution_page
    assert "getOperationalSummary" in web_control_execution_page
    assert "Recovered stale dispatches" in web_control_execution_page
    assert "Worker heartbeats" in web_control_execution_page
    assert "Stale running dispatches" in web_control_execution_page
    assert "Manual Uploads" in web_upload_page
    assert "getSourceAssets({ includeArchived: true })" in web_upload_page
    assert "backendRequest(backendPath" in web_upload_route_helper
    assert "encodeUploadFeedback" in web_upload_route_helper
    assert "parseFeedback" in web_upload_page
    assert 'backendPath: "/ingest/configured-csv"' in web_upload_configured_route
    assert "getRun" in web_run_detail_page
    assert "getSourceLineage" in web_run_detail_page
    assert "getPublicationAudit" in web_run_detail_page
    assert "getTransformationAudit" in web_run_detail_page
    assert "Retry run" in web_run_detail_page
    assert "/config/source-systems/${params.sourceSystemId}" in web_source_system_update_route
    assert "/config/source-assets/${params.sourceAssetId}" in web_source_asset_update_route
    assert "/config/source-assets/${params.sourceAssetId}/archive" in web_source_asset_archive_route
    assert "/config/source-assets/${params.sourceAssetId}" in web_source_asset_delete_route
    assert (
        "/config/ingestion-definitions/${params.ingestionDefinitionId}"
        in web_ingestion_definition_update_route
    )
    assert (
        "/config/ingestion-definitions/${params.ingestionDefinitionId}/archive"
        in web_ingestion_definition_archive_route
    )
    assert (
        "/config/ingestion-definitions/${params.ingestionDefinitionId}"
        in web_ingestion_definition_delete_route
    )
    assert "/config/execution-schedules/${params.scheduleId}" in web_schedule_update_route
    assert "/config/execution-schedules/${params.scheduleId}/archive" in web_schedule_archive_route
    assert "/config/execution-schedules/${params.scheduleId}" in web_schedule_delete_route
    assert 'backendRequest("/control/schedule-dispatches"' in web_schedule_dispatch_route
    assert "getScheduleDispatch" in web_dispatch_detail_page
    assert "Requeue dispatch" in web_dispatch_detail_page
    assert "Claim expires" in web_dispatch_detail_page
    assert "Failure reason" in web_dispatch_detail_page
    assert "/control/schedule-dispatches/${params.dispatchId}/retry" in web_dispatch_retry_route
    assert "backendRequest(`/runs/${params.runId}/retry`" in web_run_retry_route
    assert "build_web_environment" in web_main_source
    assert "resolved_api_base_url" in web_main_source


def test_executable_reporting_extensions_declare_explicit_data_access() -> None:
    registry = build_builtin_extension_registry()

    executable_reporting_extensions = [
        extension
        for extension in registry.list_extensions("reporting")
        if extension.handler is not None
    ]

    assert executable_reporting_extensions
    assert all(
        extension.data_access in {"published", "warehouse"}
        for extension in executable_reporting_extensions
    )
    assert (
        registry.get_extension("reporting", "monthly_cashflow_summary").data_access == "published"
    )


def test_source_asset_promotion_resolves_transformation_package_from_configuration() -> None:
    source = inspect.getsource(promote_source_asset_run)

    assert "source_asset.transformation_package_id" in source
    assert "config_repository.get_transformation_package" in source
    assert "run.header" not in source
