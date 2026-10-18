"""Journey contract for the flagship finance operator loop.

Sprint cinder-ledger-path (#508), item C1. The canonical loop is

    /upload -> /ingest-summary/<run_id> -> /sources and /runs
      -> /reports (monthly finance + publication trust)
      -> /reports#expense-shock -> /scenarios/<scenario_id>

These checks keep the README, the operator walkthrough and the web entry
points telling that same story. Behavioural proof of the loop through the
API lives in tests/test_finance_operator_loop_e2e.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from packages.application.use_cases.morning_brief_sections import MONTHLY_CASHFLOW_KEY

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps" / "web" / "frontend"
APP = FRONTEND / "app"

LOOP_MARKER = "<!-- finance-operator-loop -->"
LOOP_ROUTES = (
    "`/upload`",
    "`/ingest-summary/<run_id>`",
    "`/sources`",
    "`/runs`",
    "`/reports`",
    "`/reports#expense-shock`",
    "`/scenarios/<scenario_id>`",
)
LOOP_DOCS = (
    ROOT / "README.md",
    ROOT / "docs" / "runbooks" / "operator-walkthrough.md",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _loop_line(path: Path) -> str:
    lines = _read(path).splitlines()
    index = lines.index(LOOP_MARKER)
    return lines[index + 1]


def _frontend_sources() -> list[Path]:
    roots = (APP, FRONTEND / "components", FRONTEND / "lib")
    return sorted(
        path
        for root in roots
        for path in root.rglob("*")
        if path.suffix in {".js", ".ts", ".tsx", ".jsx"} and "generated" not in path.parts
    )


@pytest.mark.parametrize("doc", LOOP_DOCS, ids=lambda p: p.name)
def test_docs_state_the_canonical_loop_in_order(doc: Path) -> None:
    line = _loop_line(doc)
    positions = [line.find(route) for route in LOOP_ROUTES]
    assert all(pos >= 0 for pos in positions), f"{doc} loop line is missing a route: {line}"
    assert positions == sorted(positions), f"{doc} loop routes are out of order: {line}"


def test_readme_and_walkthrough_share_one_loop_line() -> None:
    assert len({_loop_line(doc) for doc in LOOP_DOCS}) == 1


def test_walkthrough_proof_images_exist() -> None:
    walkthrough = ROOT / "docs" / "runbooks" / "operator-walkthrough.md"
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", _read(walkthrough))
    assert images, "walkthrough should embed the finance-loop proof images"
    for relative in images:
        assert (walkthrough.parent / relative).resolve().is_file(), relative
    readme_images = re.findall(r'<img src="([^"]+)"', _read(ROOT / "README.md"))
    for relative in readme_images:
        assert (ROOT / relative).is_file(), relative


def test_post_ingest_destination_is_monthly_finance() -> None:
    page = _read(APP / "ingest-summary" / "[runId]" / "page.js")
    assert re.search(
        r'runSucceeded \? \(\s*<Link className="primaryButton" href="/reports">\s*Open monthly finance',
        page,
    ), "a landed upload must hand off to /reports as the primary action"
    assert 'className="primaryButton" href={`/runs/${runId}`}' in page, (
        "a failed upload must hand off to run remediation as the primary action"
    )
    # The label "Open monthly finance" always means the top of /reports.
    for match in re.finditer(r'href="([^"]+)">\s*Open monthly finance', page):
        assert match.group(1) == "/reports"


def test_reports_reads_trust_for_the_published_cashflow_key() -> None:
    page = _read(APP / "reports" / "page.js")
    assert f'MONTHLY_CASHFLOW_PUBLICATION_KEY = "{MONTHLY_CASHFLOW_KEY}"' in page
    assert "getPublicationConfidenceDetail(MONTHLY_CASHFLOW_PUBLICATION_KEY)" in page
    # Non-admin roles get the same verdict through the reader-scoped brief.
    assert "getBriefing()" in page
    assert "<ExpenseShockPanel />" in page
    assert 'href="#expense-shock"' in page


def test_expense_shock_panel_ends_with_a_saved_scenario_next_step() -> None:
    panel = _read(FRONTEND / "components" / "expense-shock-panel.js")
    assert 'id="expense-shock"' in panel
    assert 'fetch("/api/scenarios/expense-shock"' in panel
    assert "href={`/scenarios/${encodeURIComponent(result.scenario_id)}`}" in panel
    assert "/scenarios/compare?left=" in panel
    assert 'href="/sources"' in panel  # stale scenarios lead with source refresh


def test_scenario_detail_shows_the_shocked_expense() -> None:
    page = _read(APP / "scenarios" / "[scenarioId]" / "page.js")
    assert "{fmt(row.scenario_expense)}" in page


def test_trust_and_remediation_surfaces_link_back_to_monthly_finance() -> None:
    assert 'href="/reports"' in _read(APP / "sources" / "page.js")
    briefing = _read(APP / "briefing" / "page.js")
    assert 'money: { href: "/reports"' in briefing
    assert 'sources: { href: "/sources"' in briefing


def test_nav_exposes_every_loop_surface() -> None:
    nav = _read(FRONTEND / "lib" / "nav-model.js")
    for href in ("/upload", "/sources", "/runs", "/reports", "/scenarios", "/briefing"):
        assert f'href: "{href}"' in nav, href


def test_browser_api_calls_have_a_same_origin_route() -> None:
    """Client components fetch /api/... from the web origin; web and API run on
    different origins by default, so each prefix needs a Next.js route."""
    pattern = re.compile(r"fetch\(\s*[`\"'](/api/[a-z0-9-]+)")
    prefixes = {
        match.group(1)
        for path in _frontend_sources()
        for match in pattern.finditer(_read(path))
    }
    assert "/api/scenarios" in prefixes
    for prefix in sorted(prefixes):
        route_dir = APP / prefix.lstrip("/")
        routes = list(route_dir.rglob("route.js")) + list(route_dir.rglob("route.ts"))
        assert routes, f"browser calls {prefix} but no same-origin route exists under {route_dir}"


def _route_exports_get(route: Path) -> bool:
    return bool(re.search(r"export\s+(async\s+function|const|function)\s+GET\b", _read(route)))


def test_links_never_target_post_only_route_handlers() -> None:
    """A link (GET) to a POST-only route handler answers 405; remediation and
    onboarding links must land on a page instead."""
    link_pattern = re.compile(r'(?:href=|href:\s*|uploadPath:\s*)["`](/[^"`#?$]+)')
    offenders: list[str] = []
    for path in _frontend_sources():
        if path.name == "upload-detection-wizard.js":
            continue  # uses uploadPath as a form action, which is a POST
        for match in link_pattern.finditer(_read(path)):
            target = match.group(1).rstrip("/")
            route = APP / target.lstrip("/") / "route.js"
            if route.is_file() and not _route_exports_get(route):
                offenders.append(f"{path.relative_to(FRONTEND)} -> {target}")
    assert offenders == []


def test_upload_anchors_resolve_to_upload_cards() -> None:
    upload_page = _read(APP / "upload" / "page.js")
    actions = set(re.findall(r'action="(/upload/[a-z-]+)"', upload_page))
    assert "id={uploadCardAnchor(action)}" in upload_page
    anchors = {action.lstrip("/").replace("/", "-") for action in actions}
    used = {
        match.group(1)
        for path in _frontend_sources()
        for match in re.finditer(r"/upload#(upload-[a-z]+(?:-[a-z]+)*)", _read(path))
    }
    assert used, "remediation links should target upload card anchors"
    assert used <= anchors, f"unknown upload anchors: {sorted(used - anchors)}"
