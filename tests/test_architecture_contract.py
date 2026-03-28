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
    web_backend_source = (ROOT / "apps" / "web" / "frontend" / "lib" / "backend.ts").read_text()

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
    worker_ingest_source = (
        ROOT / "apps" / "worker" / "command_handlers" / "ingest_commands.py"
    ).read_text()
    worker_control_plane_source = (ROOT / "apps" / "worker" / "control_plane.py").read_text()

    assert "resolved_reporting_service.get_transformation_audit(" in api_source
    assert "reporting_service=resolved_reporting_service" in api_source
    assert "publish_promotion_reporting(" in api_app_source
    assert "publish_promotion_reporting(" in worker_ingest_source
    assert "publish_promotion_reporting(" in worker_control_plane_source


def test_runtime_builders_preserve_published_vs_warehouse_reporting_boundary() -> None:
    api_main_source = (ROOT / "apps" / "api" / "main.py").read_text()
    platform_builder_source = (
        ROOT / "packages" / "platform" / "runtime" / "builder.py"
    ).read_text()
    web_main_source = (ROOT / "apps" / "web" / "main.py").read_text()
    web_app_source = (ROOT / "apps" / "web" / "app.py").read_text()
    worker_runtime_source = (ROOT / "apps" / "worker" / "runtime.py").read_text()

    # API uses PUBLISHED mode for postgres, WAREHOUSE otherwise — checked in api/main.py
    assert "ReportingAccessMode.PUBLISHED" in api_main_source
    assert 'settings.reporting_backend.lower() == "postgres"' in api_main_source
    # Pipeline registry loading and catalog sync live in the shared platform builder
    assert "build_pipeline_registries(" in platform_builder_source
    assert "sync_pipeline_catalog(" in platform_builder_source
    assert "domain_registry=pipeline_registries.transformation_domain_registry" in platform_builder_source
    assert "build_transformation_service(" in platform_builder_source
    assert "build_reporting_service(" in platform_builder_source
    # Worker always uses WAREHOUSE mode
    assert "access_mode=ReportingAccessMode.WAREHOUSE" in worker_runtime_source
    assert "build_web_environment" in web_main_source
    assert "HOMELAB_ANALYTICS_API_BASE_URL" in web_app_source


def test_stage1_carryover_docs_name_remaining_dimension_and_completed_fact() -> None:
    roadmap = (ROOT / "docs" / "plans" / "household-operating-platform-roadmap.md").read_text()
    backlog = (ROOT / "docs" / "plans" / "non-finance-domain-backlog.md").read_text()
    semantic_contracts = (ROOT / "docs" / "architecture" / "semantic-contracts.md").read_text()
    requirements = (ROOT / "requirements" / "data-platform.md").read_text()

    assert "`dim_household_member`" in roadmap
    assert "`fact_balance_snapshot`" in roadmap
    assert "`dim_household_member`" in backlog
    assert "`fact_balance_snapshot`" in backlog
    assert "`dim_household_member` is still planned and not implemented." in semantic_contracts
    assert "implemented as the Stage 1 point-in-time balance fact across account and loan balances" in semantic_contracts
    assert "`fact_balance_snapshot`" in requirements
    assert "remaining Stage 1 dimension work is concentrated in `dim_household_member`" in requirements


def test_worker_main_delegates_to_runtime_and_command_handlers() -> None:
    worker_main_source = (ROOT / "apps" / "worker" / "main.py").read_text()
    worker_handler_init_source = (
        ROOT / "apps" / "worker" / "command_handlers" / "__init__.py"
    ).read_text()

    assert "build_worker_runtime(" in worker_main_source
    assert "dispatch_worker_command(" in worker_main_source
    assert "build_worker_command_handlers()" in worker_handler_init_source
    assert '"watch-schedule-dispatches"' in worker_handler_init_source


def test_api_app_imports_shared_support_modules() -> None:
    imports = _import_names(ROOT / "apps" / "api" / "app.py")

    assert "apps.api.auth_runtime" in imports
    assert "apps.api.support" in imports
    assert "apps.api.runtime_state" in imports


def test_config_routes_validate_transformation_packages_against_loaded_handlers() -> None:
    api_app_source = (ROOT / "apps" / "api" / "app.py").read_text()
    config_route_source = (ROOT / "apps" / "api" / "routes" / "config_routes.py").read_text()
    worker_ingest_source = (
        ROOT / "apps" / "worker" / "command_handlers" / "ingest_commands.py"
    ).read_text()

    assert "get_default_promotion_handler_registry()" in api_app_source
    assert "promotion_handler_registry=resolved_promotion_handler_registry" in api_app_source
    assert "promotion_handler_registry: PromotionHandlerRegistry" in config_route_source
    assert "promotion_handler_registry=promotion_handler_registry" in config_route_source
    assert "promotion_handler_registry=runtime.promotion_handler_registry" in worker_ingest_source


def test_promotion_orchestration_imports_shared_registry_contracts() -> None:
    imports = _import_names(ROOT / "packages" / "pipelines" / "promotion.py")
    builtin_handler_imports = _import_names(
        ROOT / "packages" / "pipelines" / "builtin_promotion_handlers.py"
    )
    promotion_registry_imports = _import_names(
        ROOT / "packages" / "pipelines" / "promotion_registry.py"
    )
    extension_registry_imports = _import_names(
        ROOT / "packages" / "pipelines" / "extension_registries.py"
    )

    assert "packages.pipelines.promotion_registry" in imports
    assert "packages.pipelines.builtin_promotion_handlers" in imports
    assert "packages.pipelines.promotion_types" in imports
    assert "packages.pipelines.promotion_registry" in builtin_handler_imports
    assert "packages.pipelines.transformation_domain_registry" in promotion_registry_imports
    assert "packages.pipelines.pipeline_catalog" in extension_registry_imports


def test_reporting_service_imports_shared_builtin_reporting_registry() -> None:
    imports = _import_names(ROOT / "packages" / "pipelines" / "reporting_service.py")

    assert "packages.pipelines.builtin_reporting" in imports


def test_postgres_ingestion_backend_imports_split_catalog_modules() -> None:
    imports = _import_names(ROOT / "packages" / "storage" / "postgres_ingestion_config.py")

    assert "packages.storage.control_plane_snapshot" in imports
    assert "packages.storage.migration_runner" in imports
    assert "packages.storage.postgres_asset_definition_catalog" in imports
    assert "packages.storage.postgres_auth_control_plane" in imports
    assert "packages.storage.postgres_control_plane_schema" not in imports
    assert "packages.storage.postgres_execution_control_plane" in imports
    assert "packages.storage.postgres_provenance_control_plane" in imports
    assert "packages.storage.postgres_source_contract_catalog" in imports
    assert "packages.storage.ingestion_config" not in imports


def test_sqlite_ingestion_backend_imports_split_catalog_modules() -> None:
    imports = _import_names(ROOT / "packages" / "storage" / "ingestion_config.py")

    assert "packages.storage.ingestion_catalog" in imports
    assert "packages.storage.control_plane_snapshot" in imports
    assert "packages.storage.migration_runner" not in imports
    assert "packages.storage.sqlite_asset_definition_catalog" in imports
    assert "packages.storage.sqlite_auth_control_plane" in imports
    assert "packages.storage.sqlite_control_plane_schema" in imports
    assert "packages.storage.sqlite_execution_control_plane" in imports
    assert "packages.storage.sqlite_provenance_control_plane" in imports
    assert "packages.storage.sqlite_source_contract_catalog" in imports


def test_postgres_run_metadata_backend_uses_migration_runner() -> None:
    imports = _import_names(ROOT / "packages" / "storage" / "postgres_run_metadata.py")
    assert "packages.storage.migration_runner" in imports
    source = (ROOT / "packages" / "storage" / "postgres_run_metadata.py").read_text()
    assert "migrations/postgres_run_metadata" in source


def test_app_and_web_routes_are_auth_protected_when_local_auth_is_enabled() -> None:
    api_source = (ROOT / "apps" / "api" / "app.py").read_text()
    auth_runtime_source = (ROOT / "apps" / "api" / "auth_runtime.py").read_text()
    auth_route_source = (
        ROOT / "apps" / "api" / "routes" / "auth_management_routes.py"
    ).read_text()
    control_route_source = (ROOT / "apps" / "api" / "routes" / "control_routes.py").read_text()
    ingest_route_source = (ROOT / "apps" / "api" / "routes" / "ingest_routes.py").read_text()
    run_route_source = (ROOT / "apps" / "api" / "routes" / "run_routes.py").read_text()
    api_main_source = (ROOT / "apps" / "api" / "main.py").read_text()
    web_backend_source = (ROOT / "apps" / "web" / "frontend" / "lib" / "backend.ts").read_text()
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

    scope_authorization_source = (
        ROOT / "packages" / "platform" / "auth" / "scope_authorization.py"
    ).read_text()
    assert "register_auth_middleware(" in api_source
    assert "build_auth_event_recorder(" in api_source
    assert "required_role_for_path" in auth_runtime_source
    assert "Authentication required." in auth_runtime_source
    assert "CSRF validation failed." in auth_runtime_source
    assert '"/auth/users"' in scope_authorization_source
    assert '"/auth/service-tokens"' in scope_authorization_source
    assert '"/control/auth-audit"' in scope_authorization_source
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
    # auth_mode is resolved from container.settings inside app.py
    assert "resolved_auth_mode" in api_source
    assert "session_manager=build_session_manager(resolved_settings)" in api_main_source
    assert "oidc_provider=build_oidc_provider(resolved_settings)" in api_main_source
    # admin bootstrap happens in the shared platform builder (called from api/main.py via build_container)
    platform_builder_source = (
        ROOT / "packages" / "platform" / "runtime" / "builder.py"
    ).read_text()
    assert "maybe_bootstrap_local_admin" in platform_builder_source
    assert 'action="/auth/login"' in web_login_page
    assert "Sign In with OIDC" in web_login_page
    assert 'backendRequest("get", "/auth/login"' in web_login_route
    assert 'backendRequest("get", "/auth/callback"' in web_callback_route
    assert 'backendRequest("post", "/auth/logout"' in web_logout_route
    assert 'status: "ready"' in web_ready_route
    assert 'outboundHeaders.set("x-csrf-token", csrfToken)' in web_backend_source
    assert "getLocalUsers" in web_control_page
    assert "getAuthAuditEvents" in web_control_page
    assert "getOperationalSummary" in web_control_page
    assert "getServiceTokens" in web_control_page
    assert 'backendJsonRequest("post", "/auth/service-tokens"' in web_service_token_route
    assert "/auth/service-tokens/{token_id}/revoke" in web_service_token_revoke_route
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
    assert "backendJsonRequest" in web_preview_route
    assert '"/config/column-mappings/preview"' in web_preview_route
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
    assert '"/config/source-systems/{source_system_id}"' in web_source_system_update_route
    assert '"/config/source-assets/{source_asset_id}"' in web_source_asset_update_route
    assert '"/config/source-assets/{source_asset_id}/archive"' in web_source_asset_archive_route
    assert '"/config/source-assets/{source_asset_id}"' in web_source_asset_delete_route
    assert (
        '"/config/ingestion-definitions/{ingestion_definition_id}"'
        in web_ingestion_definition_update_route
    )
    assert (
        '"/config/ingestion-definitions/{ingestion_definition_id}/archive"'
        in web_ingestion_definition_archive_route
    )
    assert (
        '"/config/ingestion-definitions/{ingestion_definition_id}"'
        in web_ingestion_definition_delete_route
    )
    assert '"/config/execution-schedules/{schedule_id}"' in web_schedule_update_route
    assert '"/config/execution-schedules/{schedule_id}/archive"' in web_schedule_archive_route
    assert '"/config/execution-schedules/{schedule_id}"' in web_schedule_delete_route
    assert 'backendRequest("post", "/control/schedule-dispatches"' in web_schedule_dispatch_route
    assert "getScheduleDispatch" in web_dispatch_detail_page
    assert "Requeue dispatch" in web_dispatch_detail_page
    assert "Claim expires" in web_dispatch_detail_page
    assert "Failure reason" in web_dispatch_detail_page
    assert '"/control/schedule-dispatches/{dispatch_id}/retry"' in web_dispatch_retry_route
    assert 'backendJsonRequest("post", "/runs/{run_id}/retry"' in web_run_retry_route
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


# ---------------------------------------------------------------------------
# New boundary rules (Phase 4): platform/domains/adapters layer enforcement
# ---------------------------------------------------------------------------


def _collect_imports_in_dir(directory: Path) -> list[str]:
    """Return all import module names found in Python files under `directory`."""
    all_imports: list[str] = []
    for py_file in directory.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        all_imports.extend(_import_names(py_file))
    return all_imports


def test_domains_do_not_import_from_apps() -> None:
    domains_dir = ROOT / "packages" / "domains"
    imports = _collect_imports_in_dir(domains_dir)
    app_imports = [imp for imp in imports if imp.startswith("apps.")]
    assert not app_imports, (
        f"packages/domains must not import from apps.* — found: {app_imports}"
    )


def test_domains_do_not_import_from_adapters() -> None:
    domains_dir = ROOT / "packages" / "domains"
    imports = _collect_imports_in_dir(domains_dir)
    adapter_imports = [imp for imp in imports if imp.startswith("packages.adapters.")]
    assert not adapter_imports, (
        f"packages/domains must not import from packages.adapters.* — found: {adapter_imports}"
    )


def test_platform_auth_does_not_import_from_apps() -> None:
    auth_dir = ROOT / "packages" / "platform" / "auth"
    imports = _collect_imports_in_dir(auth_dir)
    app_imports = [imp for imp in imports if imp.startswith("apps.")]
    assert not app_imports, (
        f"packages/platform/auth must not import from apps.* — found: {app_imports}"
    )


def test_platform_does_not_import_from_domains() -> None:
    """Platform layer must have zero imports from packages.domains (ADR §8.1)."""
    platform_dir = ROOT / "packages" / "platform"
    imports = _collect_imports_in_dir(platform_dir)
    domain_imports = [imp for imp in imports if imp.startswith("packages.domains.")]
    assert not domain_imports, (
        f"packages/platform must not import from packages.domains.* — found: {domain_imports}"
    )


def test_platform_runtime_builder_accepts_packs_via_parameter() -> None:
    """Builder must accept capability packs as a parameter, not import domain packs directly."""
    builder_source = (ROOT / "packages" / "platform" / "runtime" / "builder.py").read_text()
    # Builder must accept packs via parameter and validate them
    assert "capability_packs" in builder_source
    assert "pack.validate()" in builder_source
    # Builder must NOT import any specific domain pack
    assert "packages.domains" not in builder_source


def test_finance_pack_is_stored_in_app_container() -> None:
    container_source = (ROOT / "packages" / "platform" / "runtime" / "container.py").read_text()
    assert "finance_pack" in container_source
    assert "CapabilityPack" in container_source


# ---------------------------------------------------------------------------
# Auth policy matrix tests (ADR §14)
# ---------------------------------------------------------------------------


def _iter_api_route_method_paths() -> set[tuple[str, str]]:
    route_dir = ROOT / "apps" / "api" / "routes"
    discovered: set[tuple[str, str]] = set()
    method_names = {"get", "post", "put", "patch", "delete", "options", "head"}
    for module_path in route_dir.glob("*.py"):
        if module_path.name.startswith("__"):
            continue
        tree = ast.parse(module_path.read_text(), filename=str(module_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            method_name = node.func.attr.lower()
            if method_name not in method_names:
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
                continue
            path = first_arg.value
            if not path.startswith("/"):
                continue
            discovered.add((path, method_name.upper()))
    return discovered


def test_request_auth_policy_covers_all_non_public_api_routes() -> None:
    from packages.platform.auth.scope_authorization import required_role_for_request

    public_routes = {
        ("/auth/login", "GET"),
        ("/auth/login", "POST"),
        ("/auth/logout", "POST"),
        ("/auth/callback", "GET"),
        ("/health", "GET"),
        ("/ready", "GET"),
        ("/metrics", "GET"),
    }
    uncovered: list[tuple[str, str]] = []
    for path, method in sorted(_iter_api_route_method_paths()):
        if (path, method) in public_routes:
            continue
        if required_role_for_request(path, method) is None:
            uncovered.append((method, path))
    assert uncovered == [], (
        "Every non-public API route must have a request-aware auth role mapping. "
        f"Uncovered routes: {uncovered}"
    )


def test_request_permission_and_scope_policy_covers_protected_api_routes() -> None:
    from packages.platform.auth.scope_authorization import (
        required_permission_for_request,
        required_service_token_scope_for_request,
    )

    public_routes = {
        ("/auth/login", "GET"),
        ("/auth/login", "POST"),
        ("/auth/logout", "POST"),
        ("/auth/callback", "GET"),
        ("/health", "GET"),
        ("/ready", "GET"),
        ("/metrics", "GET"),
    }
    role_only_routes = {
        ("/auth/me", "GET"),
    }

    missing_permission: list[tuple[str, str]] = []
    missing_scope: list[tuple[str, str]] = []
    for path, method in sorted(_iter_api_route_method_paths()):
        route_key = (path, method)
        if route_key in public_routes or route_key in role_only_routes:
            continue
        if required_permission_for_request(path, method=method) is None:
            missing_permission.append((method, path))
        if required_service_token_scope_for_request(path, method) is None:
            missing_scope.append((method, path))

    assert missing_permission == [], (
        "Protected API routes must have request-aware permission mappings. "
        f"Missing: {missing_permission}"
    )
    assert missing_scope == [], (
        "Protected API routes must have service-token scope mappings. "
        f"Missing: {missing_scope}"
    )


@pytest.mark.parametrize(
    "path,expected_role",
    [
        # Public / unauthenticated paths
        ("/health", None),
        ("/ready", None),
        ("/metrics", None),
        ("/auth/login", None),
        ("/auth/logout", None),
        ("/auth/callback", None),
        # Reader paths
        ("/auth/me", "reader"),
        ("/runs", "reader"),
        ("/runs/abc-123", "reader"),
        ("/reports/cashflow", "reader"),
        ("/control/source-lineage", "reader"),
        ("/control/publication-audit", "reader"),
        ("/transformation-audit", "reader"),
        # Operator paths
        ("/ingest/account-transactions", "operator"),
        ("/runs/abc-123/retry", "operator"),
        # Admin paths
        ("/auth/users", "admin"),
        ("/auth/service-tokens", "admin"),
        ("/control/auth-audit", "admin"),
        ("/config/sources", "admin"),
        ("/control/schedule-dispatches", "admin"),
        ("/extensions", "admin"),
        ("/sources", "admin"),
        ("/transformations/run", "admin"),
    ],
)
def test_auth_policy_role_requirement(path: str, expected_role: str | None) -> None:
    from packages.platform.auth.scope_authorization import required_role_for_path
    from packages.storage.auth_store import UserRole

    result = required_role_for_path(path)
    if expected_role is None:
        assert result is None, (
            f"Path '{path}' should require no role, but got {result}"
        )
    else:
        assert result is not None, (
            f"Path '{path}' should require role '{expected_role}', but got None"
        )
        assert result == UserRole(expected_role), (
            f"Path '{path}' expected role '{expected_role}', got '{result}'"
        )


@pytest.mark.parametrize(
    "path,expected_scope",
    [
        # Public / unauthenticated paths
        ("/health", None),
        ("/ready", None),
        ("/metrics", None),
        ("/auth/login", None),
        ("/auth/logout", None),
        ("/auth/callback", None),
        # Ingest paths → ingest:write scope
        ("/ingest/account-transactions", "ingest:write"),
        ("/runs/abc-123/retry", "ingest:write"),
        # Run / audit paths → runs:read scope
        ("/runs", "runs:read"),
        ("/runs/abc-123", "runs:read"),
        ("/control/source-lineage", "runs:read"),
        ("/control/publication-audit", "runs:read"),
        ("/transformation-audit", "runs:read"),
        # Reports → reports:read scope
        ("/reports/cashflow", "reports:read"),
        # Admin paths → admin:write scope
        ("/auth/users", "admin:write"),
        ("/auth/service-tokens", "admin:write"),
        ("/control/auth-audit", "admin:write"),
        ("/config/sources", "admin:write"),
        ("/extensions", "admin:write"),
    ],
)
def test_auth_policy_service_token_scope_requirement(
    path: str, expected_scope: str | None
) -> None:
    from packages.platform.auth.scope_authorization import required_service_token_scope_for_path

    result = required_service_token_scope_for_path(path)
    assert result == expected_scope, (
        f"Path '{path}' expected scope '{expected_scope}', got '{result}'"
    )


# ---------------------------------------------------------------------------
# Multi-pack builder contracts
# ---------------------------------------------------------------------------


def test_build_container_stores_all_registered_packs() -> None:
    """Container must expose a capability_packs tuple holding all registered packs."""
    container_source = (ROOT / "packages" / "platform" / "runtime" / "container.py").read_text()
    assert "capability_packs" in container_source
    assert "tuple[CapabilityPack" in container_source


def test_build_container_validates_cross_pack_publication_uniqueness() -> None:
    """Builder must reject duplicate publication keys across packs."""
    builder_source = (ROOT / "packages" / "platform" / "runtime" / "builder.py").read_text()
    # Cross-pack uniqueness check uses Counter or duplicate detection
    assert "duplicates" in builder_source
    assert "Publication keys owned by multiple" in builder_source


def test_both_entrypoints_register_finance_and_utilities_packs() -> None:
    """Both API and worker entrypoints must register FINANCE_PACK and UTILITIES_PACK."""
    api_main = (ROOT / "apps" / "api" / "main.py").read_text()
    worker_runtime = (ROOT / "apps" / "worker" / "runtime.py").read_text()
    for source, label in ((api_main, "apps/api/main.py"), (worker_runtime, "apps/worker/runtime.py")):
        assert "FINANCE_PACK" in source, f"{label} must register FINANCE_PACK"
        assert "UTILITIES_PACK" in source, f"{label} must register UTILITIES_PACK"


# ---------------------------------------------------------------------------
# Structural seam guards
# ---------------------------------------------------------------------------


def test_source_routes_is_coordinator_not_handler() -> None:
    source_routes_path = Path("apps/api/routes/source_routes.py")
    source = source_routes_path.read_text(encoding="utf-8")
    assert "@app.get" not in source, (
        "source_routes.py must be a coordinator — found @app.get, indicating direct route handlers"
    )
    assert "@app.post" not in source, (
        "source_routes.py must be a coordinator — found @app.post, indicating direct route handlers"
    )
    assert "@app.patch" not in source, (
        "source_routes.py must be a coordinator — found @app.patch, indicating direct route handlers"
    )
    assert "@app.delete" not in source, (
        "source_routes.py must be a coordinator — found @app.delete, indicating direct route handlers"
    )


def test_source_route_sub_modules_exist() -> None:
    expected = [
        Path("apps/api/routes/source_system_routes.py"),
        Path("apps/api/routes/source_contract_routes.py"),
        Path("apps/api/routes/source_mapping_routes.py"),
        Path("apps/api/routes/source_asset_routes.py"),
        Path("apps/api/routes/source_ingestion_routes.py"),
    ]
    for path in expected:
        assert path.exists(), f"Expected source route sub-module not found: {path}"


def test_sqlite_capability_matrix_documents_guaranteed_vs_best_effort_contract() -> None:
    content = (
        ROOT / "docs" / "architecture" / "sqlite-control-plane-capability-matrix.md"
    ).read_text()
    for term in [
        "Postgres",
        "SQLite",
        "Guaranteed",
        "Best-effort",
        "local bootstrap",
        "snapshot",
    ]:
        assert term in content, (
            "SQLite capability matrix must document guaranteed vs best-effort "
            f"support boundaries; missing {term!r}"
        )


# ---------------------------------------------------------------------------
# Migration file contracts
# ---------------------------------------------------------------------------


def test_migration_files_follow_naming_convention() -> None:
    """Migration files must be named NNNN_description.sql (4-digit zero-padded prefix)."""
    import re

    pattern = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")
    for migrations_dir in (
        ROOT / "migrations" / "sqlite",
        ROOT / "migrations" / "postgres",
        ROOT / "migrations" / "postgres_run_metadata",
    ):
        assert migrations_dir.exists(), (
            f"{migrations_dir} directory not found — run the migration system setup"
        )
        for f in migrations_dir.glob("*.sql"):
            if f.name.startswith("."):
                continue
            assert pattern.match(f.name), (
                f"Migration file {f} does not follow naming convention NNNN_description.sql"
            )


def test_sqlite_migration_versions_do_not_get_ahead_of_postgres() -> None:
    """Postgres is canonical; SQLite versions may lag but must not lead."""
    sqlite_versions = {
        f.stem.split("_")[0]
        for f in (ROOT / "migrations" / "sqlite").glob("*.sql")
    }
    postgres_versions = {
        f.stem.split("_")[0]
        for f in (ROOT / "migrations" / "postgres").glob("*.sql")
    }
    assert sqlite_versions.issubset(postgres_versions), (
        "SQLite migration versions must be a subset of canonical Postgres versions. "
        f"sqlite={sqlite_versions}, postgres={postgres_versions}."
    )


def test_shared_auth_is_compatibility_shim() -> None:
    shared_auth_path = Path("packages/shared/auth.py")
    lines = shared_auth_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 100, (
        f"packages/shared/auth.py should be a ~50-line compatibility shim, got {len(lines)} lines"
    )


def test_platform_auth_modules_exist() -> None:
    expected = [
        Path("packages/platform/auth/session_manager.py"),
        Path("packages/platform/auth/oidc_provider.py"),
        Path("packages/platform/auth/crypto.py"),
        Path("packages/platform/auth/role_hierarchy.py"),
        Path("packages/platform/auth/serialization.py"),
        Path("packages/platform/auth/configuration.py"),
    ]
    for path in expected:
        assert path.exists(), f"Expected platform auth module not found: {path}"
