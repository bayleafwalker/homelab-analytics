from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "apps" / "web" / "frontend"


def test_nextjs_frontend_exposes_login_and_logout_routes() -> None:
    login_route = (FRONTEND_ROOT / "app" / "auth" / "login" / "route.js").read_text()
    logout_route = (FRONTEND_ROOT / "app" / "auth" / "logout" / "route.js").read_text()
    login_page = (FRONTEND_ROOT / "app" / "login" / "page.js").read_text()
    control_page = (FRONTEND_ROOT / "app" / "control" / "page.js").read_text()

    assert 'backendRequest("/auth/login"' in login_route
    assert "set-cookie" in login_route
    assert 'backendRequest("/auth/logout"' in logout_route
    assert "Sign In" in login_page
    assert 'action="/auth/login"' in login_page
    assert "Too many failed login attempts" in login_page
    assert "getLocalUsers" in control_page
    assert "getAuthAuditEvents" in control_page


def test_nextjs_frontend_reads_data_from_api_helper_only() -> None:
    dashboard_source = (FRONTEND_ROOT / "app" / "page.js").read_text()
    runs_source = (FRONTEND_ROOT / "app" / "runs" / "page.js").read_text()
    reports_source = (FRONTEND_ROOT / "app" / "reports" / "page.js").read_text()
    control_source = (FRONTEND_ROOT / "app" / "control" / "page.js").read_text()
    backend_source = (FRONTEND_ROOT / "lib" / "backend.js").read_text()

    assert "HOMELAB_ANALYTICS_API_BASE_URL" in backend_source
    assert 'fetch(`${getApiBaseUrl()}${path}`' in backend_source
    assert 'outboundHeaders.set("x-csrf-token", csrfToken)' in backend_source
    assert "getMonthlyCashflow" in dashboard_source
    assert "getRuns" in dashboard_source
    assert "getRuns" in runs_source
    assert "getMonthlyCashflow" in reports_source
    assert "getLocalUsers" in control_source
    assert "ReportingService(" not in dashboard_source
