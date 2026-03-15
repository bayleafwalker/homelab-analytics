from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "apps" / "web" / "frontend"


def test_nextjs_frontend_exposes_login_and_logout_routes() -> None:
    login_route = (FRONTEND_ROOT / "app" / "auth" / "login" / "route.js").read_text()
    logout_route = (FRONTEND_ROOT / "app" / "auth" / "logout" / "route.js").read_text()
    login_page = (FRONTEND_ROOT / "app" / "login" / "page.js").read_text()
    control_page = (FRONTEND_ROOT / "app" / "control" / "page.js").read_text()
    control_catalog_page = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "page.js"
    ).read_text()
    control_execution_page = (
        FRONTEND_ROOT / "app" / "control" / "execution" / "page.js"
    ).read_text()
    source_system_route = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "source-systems" / "route.js"
    ).read_text()
    source_asset_route = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "source-assets" / "route.js"
    ).read_text()
    ingestion_definition_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "route.js"
    ).read_text()
    process_definition_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "[ingestionDefinitionId]"
        / "process"
        / "route.js"
    ).read_text()
    execution_schedule_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "execution-schedules"
        / "route.js"
    ).read_text()
    run_detail_page = (
        FRONTEND_ROOT / "app" / "runs" / "[runId]" / "page.js"
    ).read_text()

    assert 'backendRequest("/auth/login"' in login_route
    assert "set-cookie" in login_route
    assert 'backendRequest("/auth/logout"' in logout_route
    assert "Sign In" in login_page
    assert 'action="/auth/login"' in login_page
    assert "Too many failed login attempts" in login_page
    assert "getLocalUsers" in control_page
    assert "getAuthAuditEvents" in control_page
    assert "getSourceSystems" in control_catalog_page
    assert "getSourceAssets" in control_catalog_page
    assert "getIngestionDefinitions" in control_execution_page
    assert "getExecutionSchedules" in control_execution_page
    assert "getRun" in run_detail_page
    assert 'backendRequest("/config/source-systems"' in source_system_route
    assert 'backendRequest("/config/source-assets"' in source_asset_route
    assert 'backendRequest("/config/ingestion-definitions"' in ingestion_definition_route
    assert 'backendRequest("/config/execution-schedules"' in execution_schedule_route
    assert "/ingest/ingestion-definitions/${params.ingestionDefinitionId}/process" in process_definition_route


def test_nextjs_frontend_reads_data_from_api_helper_only() -> None:
    dashboard_source = (FRONTEND_ROOT / "app" / "page.js").read_text()
    runs_source = (FRONTEND_ROOT / "app" / "runs" / "page.js").read_text()
    reports_source = (FRONTEND_ROOT / "app" / "reports" / "page.js").read_text()
    control_source = (FRONTEND_ROOT / "app" / "control" / "page.js").read_text()
    control_catalog_source = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "page.js"
    ).read_text()
    control_execution_source = (
        FRONTEND_ROOT / "app" / "control" / "execution" / "page.js"
    ).read_text()
    run_detail_source = (
        FRONTEND_ROOT / "app" / "runs" / "[runId]" / "page.js"
    ).read_text()
    backend_source = (FRONTEND_ROOT / "lib" / "backend.js").read_text()

    assert "HOMELAB_ANALYTICS_API_BASE_URL" in backend_source
    assert 'fetch(`${getApiBaseUrl()}${path}`' in backend_source
    assert 'outboundHeaders.set("x-csrf-token", csrfToken)' in backend_source
    assert "getSourceSystems" in backend_source
    assert "getSourceAssets" in backend_source
    assert "getIngestionDefinitions" in backend_source
    assert "getExecutionSchedules" in backend_source
    assert "getRun" in backend_source
    assert "getMonthlyCashflow" in dashboard_source
    assert "getRuns" in dashboard_source
    assert "getRuns" in runs_source
    assert "getMonthlyCashflow" in reports_source
    assert "getLocalUsers" in control_source
    assert "getSourceSystems" in control_catalog_source
    assert "getIngestionDefinitions" in control_execution_source
    assert "getRun" in run_detail_source
    assert "ReportingService(" not in dashboard_source
