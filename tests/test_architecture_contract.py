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
    web_source = (ROOT / "apps" / "web" / "app.py").read_text()

    legacy_call_re = re.compile(r"(?<![A-Za-z0-9_])service\.get_monthly_cashflow\(")
    direct_transform_re = re.compile(
        r"(?<![A-Za-z0-9_])transformation_service\.get_monthly_cashflow\("
    )

    assert legacy_call_re.search(api_source) is None
    assert legacy_call_re.search(web_source) is None
    assert direct_transform_re.search(api_source) is None
    assert direct_transform_re.search(web_source) is None
    assert "resolved_reporting_service.get_monthly_cashflow(" in api_source
    assert "resolved_reporting_service.get_monthly_cashflow(" in web_source


def test_app_reporting_routes_flow_through_reporting_service_contract() -> None:
    api_source = (ROOT / "apps" / "api" / "app.py").read_text()
    worker_source = (ROOT / "apps" / "worker" / "main.py").read_text()

    assert "resolved_reporting_service.get_transformation_audit(" in api_source
    assert "reporting_service=resolved_reporting_service" in api_source
    assert "publish_promotion_reporting(" in api_source
    assert "publish_promotion_reporting(" in worker_source


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
