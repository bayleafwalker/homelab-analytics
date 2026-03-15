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


def test_app_reporting_paths_do_not_compute_cashflow_from_landing_service() -> None:
    api_source = (ROOT / "apps" / "api" / "app.py").read_text()
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
    api_source = (ROOT / "apps" / "api" / "app.py").read_text()
    worker_source = (ROOT / "apps" / "worker" / "main.py").read_text()

    assert "resolved_reporting_service.get_transformation_audit(" in api_source
    assert "reporting_service=resolved_reporting_service" in api_source
    assert "publish_promotion_reporting(" in api_source
    assert "publish_promotion_reporting(" in worker_source


def test_runtime_builders_preserve_published_vs_warehouse_reporting_boundary() -> None:
    api_main_source = (ROOT / "apps" / "api" / "main.py").read_text()
    web_main_source = (ROOT / "apps" / "web" / "main.py").read_text()
    web_app_source = (ROOT / "apps" / "web" / "app.py").read_text()
    worker_main_source = (ROOT / "apps" / "worker" / "main.py").read_text()

    assert "ReportingAccessMode.PUBLISHED" in api_main_source
    assert "settings.reporting_backend.lower() == \"postgres\"" in api_main_source
    assert "access_mode=ReportingAccessMode.WAREHOUSE" in worker_main_source
    assert "build_web_environment" in web_main_source
    assert "HOMELAB_ANALYTICS_API_BASE_URL" in web_app_source


def test_app_and_web_routes_are_auth_protected_when_local_auth_is_enabled() -> None:
    api_source = (ROOT / "apps" / "api" / "app.py").read_text()
    api_main_source = (ROOT / "apps" / "api" / "main.py").read_text()
    web_backend_source = (ROOT / "apps" / "web" / "frontend" / "lib" / "backend.js").read_text()
    web_control_page = (ROOT / "apps" / "web" / "frontend" / "app" / "control" / "page.js").read_text()
    web_control_catalog_page = (
        ROOT / "apps" / "web" / "frontend" / "app" / "control" / "catalog" / "page.js"
    ).read_text()
    web_control_execution_page = (
        ROOT / "apps" / "web" / "frontend" / "app" / "control" / "execution" / "page.js"
    ).read_text()
    web_run_detail_page = (
        ROOT / "apps" / "web" / "frontend" / "app" / "runs" / "[runId]" / "page.js"
    ).read_text()
    web_login_page = (ROOT / "apps" / "web" / "frontend" / "app" / "login" / "page.js").read_text()
    web_login_route = (ROOT / "apps" / "web" / "frontend" / "app" / "auth" / "login" / "route.js").read_text()
    web_logout_route = (ROOT / "apps" / "web" / "frontend" / "app" / "auth" / "logout" / "route.js").read_text()
    web_main_source = (ROOT / "apps" / "web" / "main.py").read_text()

    assert "required_role_for_path" in api_source
    assert "Authentication required." in api_source
    assert "CSRF validation failed." in api_source
    assert '"/auth/users"' in api_source
    assert '"/control/auth-audit"' in api_source
    assert "auth_mode=resolved_settings.auth_mode" in api_main_source
    assert "session_manager=build_session_manager(resolved_settings)" in api_main_source
    assert "maybe_bootstrap_local_admin" in api_main_source
    assert 'action="/auth/login"' in web_login_page
    assert 'backendRequest("/auth/login"' in web_login_route
    assert 'backendRequest("/auth/logout"' in web_logout_route
    assert 'outboundHeaders.set("x-csrf-token", csrfToken)' in web_backend_source
    assert "getLocalUsers" in web_control_page
    assert "getAuthAuditEvents" in web_control_page
    assert "getSourceSystems" in web_control_catalog_page
    assert "getSourceAssets" in web_control_catalog_page
    assert "getIngestionDefinitions" in web_control_execution_page
    assert "getExecutionSchedules" in web_control_execution_page
    assert "getRun" in web_run_detail_page
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
        registry.get_extension("reporting", "monthly_cashflow_summary").data_access
        == "published"
    )


def test_source_asset_promotion_resolves_transformation_package_from_configuration() -> None:
    source = inspect.getsource(promote_source_asset_run)

    assert "source_asset.transformation_package_id" in source
    assert "config_repository.get_transformation_package" in source
    assert "run.header" not in source
