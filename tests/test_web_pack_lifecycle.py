"""Structural checks for the /control/packs operator surface."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "apps" / "web" / "frontend"
PACKS_ROOT = FRONTEND_ROOT / "app" / "control" / "packs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_packs_page_is_admin_only_server_component_through_backend_helpers() -> None:
    page = _read(PACKS_ROOT / "page.js")
    backend = _read(FRONTEND_ROOT / "lib" / "backend.ts")

    assert 'user.role !== "admin"' in page
    assert "'use client'" not in page and '"use client"' not in page
    assert "fetch(" not in page
    for helper in ("getPackCatalog(", "getPackHistory(", "getPackChangePlan("):
        assert helper in page
        assert f"export async function {helper}" in backend
    assert '"/control/packs": "list_pack_catalog_control_packs_get";' in backend
    assert (
        '"/control/packs/history": "list_pack_history_control_packs_history_get";' in backend
    )
    assert '"/control/packs/{pack_key}/plan"' in backend


def test_packs_page_renders_badges_dry_run_plan_and_history() -> None:
    page = _read(PACKS_ROOT / "page.js")

    # Compatibility badges for every cached version and the installed one.
    assert "CompatibilityPill" in page
    assert "row.compatibility_status" in page
    assert "installation.compatibility_snapshot.status" in page
    # The dry-run preview names what publications and contracts change.
    assert "Dry run · nothing has changed yet" in page
    assert "plan.publication_changes" in page
    assert "plan.contracts_affected" in page
    assert "change.dependents" in page
    assert "This change would be refused." in page
    # Only an allowed plan offers a confirm form, and it needs a reason.
    assert "plan.allowed ?" in page
    assert 'name="reason"' in page and "required" in page
    assert "MAX_PACK_REASON_LENGTH" in page
    # History shows actor, reason and refused outcomes.
    for marker in ("event.actor", "event.reason", 'event.outcome === "refused"'):
        assert marker in page
    # Trust boundary is stated on the page.
    assert "This page never fetches code." in page


def test_pack_action_route_posts_through_backend_with_reason() -> None:
    route = _read(PACKS_ROOT / "[packKey]" / "actions" / "route.js")
    helpers = _read(FRONTEND_ROOT / "lib" / "pack-lifecycle.js")

    assert "// @ts-check" in route
    assert "cookieHeader" in route
    assert 'backendRequest("post", "/control/packs/{pack_key}/actions"' in route
    assert "!isPackAction(action) || !reason" in route
    assert "{ status: 303 }" in route
    assert "export const MAX_PACK_REASON_LENGTH = 500;" in helpers
    for action in ("install", "upgrade", "rollback", "disable", "enable", "pin", "unpin"):
        assert f'"{action}"' in helpers


def test_packs_page_is_reachable_from_navigation() -> None:
    control_nav = _read(FRONTEND_ROOT / "components" / "control-nav.js")
    nav_model = _read(FRONTEND_ROOT / "lib" / "nav-model.js")

    assert '{ href: "/control/packs", label: "Packs" }' in control_nav
    assert 'href: "/control/packs", label: "Control: packs", minRole: "admin"' in nav_model
