"""Seam regression: route modules must not call transformation_service getters directly.

Surfaces should delegate reads to ReportingService and mutations to use-case modules.
Only TransformationService facade entry-points (load_domain_rows, refresh_publications,
load_*, count_*) are permitted from routes.
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
)

_ALLOWED_ROUTE_FILES = {
    "scenario_routes.py",
}


def _collect_attr_calls(tree: ast.AST) -> list[str]:
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            results.append(f"{node.value.id}.{node.attr}")
    return results


class TestRouteSeamRegression(unittest.TestCase):
    def test_no_direct_transformation_service_getter_calls_in_routes(self) -> None:
        violations: list[str] = []
        for route_file in sorted(_ROUTES_DIR.glob("*.py")):
            if route_file.name.startswith("__") or route_file.name in _ALLOWED_ROUTE_FILES:
                continue
            tree = ast.parse(route_file.read_text(), filename=str(route_file))
            for call_str in _collect_attr_calls(tree):
                for prefix in _FORBIDDEN_PREFIXES:
                    if call_str.startswith(prefix):
                        violations.append(f"{route_file.name}: {call_str}")
                        break

        if violations:
            self.fail(
                "Route modules must not call TransformationService domain getters directly.\n"
                "Delegate reads to ReportingService and mutations to use-case modules.\n"
                "Violations:\n" + "\n".join(f"  {v}" for v in violations)
            )
