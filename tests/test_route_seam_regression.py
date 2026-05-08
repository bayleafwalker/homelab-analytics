"""Seam regression: route modules must not call transformation_service getters directly.

Surfaces should delegate reads to ReportingService and mutations to use-case modules.
Only TransformationService facade entry-points (load_domain_rows, refresh_publications,
load_*, count_*) are permitted from routes.

The test also detects aliased TS calls of the form `svc = _svc(); svc.get_*` by
checking assignments from known TS-returning local helpers (_svc, _ts) and tracking
their aliases through the function body.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

_ROUTES_DIR = pathlib.Path(__file__).parent.parent / "apps" / "api" / "routes"

_FORBIDDEN_PREFIXES = (
    "transformation_service.get_",
    "transformation_service.refresh_",
    "transformation_service.list_category",
    "transformation_service.add_category",
    "transformation_service.remove_category",
    "transformation_service.set_category",
    "transformation_service.create_",
    "transformation_service.archive_",
    "transformation_service.ingest_",
)

_FORBIDDEN_ALIAS_PREFIXES = (
    "get_",
    "refresh_",
    "list_category",
    "add_category",
    "remove_category",
    "set_category",
    "create_",
    "archive_",
    "ingest_",
)

_TS_LOCAL_HELPER_NAMES = {"_svc", "_ts", "_transformation_service"}

_ALLOWED_ROUTE_FILES = {
    "scenario_routes.py",
}


def _collect_attr_calls(tree: ast.AST) -> list[str]:
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            results.append(f"{node.value.id}.{node.attr}")
    return results


def _collect_ts_alias_violations(source: str) -> list[str]:
    """Find calls like `svc = _svc(); svc.get_*` where `svc` aliases a TS helper.

    Walks each function body to identify local variables assigned from a call to a
    known TS-returning helper, then checks whether those aliases have forbidden
    attribute calls.
    """
    tree = ast.parse(source)
    violations: list[str] = []

    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        ts_aliases: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                if (
                    isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id in _TS_LOCAL_HELPER_NAMES
                ):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            ts_aliases.add(target.id)

        if not ts_aliases:
            continue

        for node in ast.walk(func):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in ts_aliases
            ):
                for prefix in _FORBIDDEN_ALIAS_PREFIXES:
                    if node.attr.startswith(prefix):
                        violations.append(f"{node.value.id}.{node.attr}")
                        break

    return violations


class TestRouteSeamRegression(unittest.TestCase):
    def test_no_direct_transformation_service_getter_calls_in_routes(self) -> None:
        violations: list[str] = []
        for route_file in sorted(_ROUTES_DIR.glob("*.py")):
            if route_file.name.startswith("__") or route_file.name in _ALLOWED_ROUTE_FILES:
                continue
            source = route_file.read_text()
            tree = ast.parse(source, filename=str(route_file))
            for call_str in _collect_attr_calls(tree):
                for prefix in _FORBIDDEN_PREFIXES:
                    if call_str.startswith(prefix):
                        violations.append(f"{route_file.name}: {call_str}")
                        break
            for alias_call in _collect_ts_alias_violations(source):
                violations.append(f"{route_file.name} (alias): {alias_call}")

        if violations:
            self.fail(
                "Route modules must not call TransformationService domain methods directly.\n"
                "Delegate reads to ReportingService and mutations to use-case modules.\n"
                "Violations:\n" + "\n".join(f"  {v}" for v in violations)
            )
