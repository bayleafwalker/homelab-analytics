from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.docs]

ROOT = Path(__file__).resolve().parents[1]


def test_makefile_contains_required_verification_targets() -> None:
    content = (ROOT / "Makefile").read_text()

    assert "SHELL := /usr/bin/bash" in content

    for target in [
        "lint:",
        "typecheck:",
        "test:",
        "test-target:",
        "test-integration:",
        "test-e2e-local:",
        "test-storage-adapters:",
        "verify-config:",
        "verify-docs:",
        "verify-agent:",
        "verify-arch:",
        "contract-export-check:",
        "contract-compat-report:",
        "contract-release-artifacts:",
        "verify-fast:",
        "verify-all:",
        "verify-domain:",
        "compose-smoke:",
    ]:
        assert target in content

    assert ".venv/bin/python" in content
    assert "test-sqlite-adapters:" in content
    assert "test-coverage:" in content
    assert (
        "verify-fast: lint typecheck test-fast test-sqlite-adapters "
        "verify-docs verify-agent verify-arch contract-export-check "
        "web-codegen-check web-typecheck web-build helm-lint"
    ) in content
    assert "APP_IMAGE := homelab-analytics:latest" in content
    assert "WEB_IMAGE := homelab-analytics-web:latest" in content
    assert "docker image inspect $(APP_IMAGE)" in content
    assert "docker image inspect $(WEB_IMAGE)" in content


def test_ci_workflow_runs_blocking_and_advisory_verification() -> None:
    content = (ROOT / ".github" / "workflows" / "verify.yaml").read_text()

    for fragment in [
        "make verify-fast",
        "make contract-release-artifacts",
        "make docker-build",
        "make compose-smoke",
        "make audit-deps",
        "azure/setup-helm",
        "python -m pip install -e .[dev]",
        "actions/upload-artifact@v4",
        "fetch-depth: 0",
    ]:
        assert fragment in content
