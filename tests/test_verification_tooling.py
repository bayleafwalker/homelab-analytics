from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.docs]

ROOT = Path(__file__).resolve().parents[1]


def test_makefile_contains_required_verification_targets() -> None:
    content = (ROOT / "Makefile").read_text()

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
        "verify-fast:",
        "verify-all:",
        "verify-domain:",
        "compose-smoke:",
    ]:
        assert target in content

    assert ".venv/bin/python" in content
    assert "verify-fast: lint typecheck test-fast verify-docs verify-agent verify-arch helm-lint" in content
    assert "docker image inspect homelab-analytics:latest" in content


def test_ci_workflow_runs_blocking_and_advisory_verification() -> None:
    content = (ROOT / ".github" / "workflows" / "verify.yaml").read_text()

    for fragment in [
        "make verify-fast",
        "make docker-build",
        "make compose-smoke",
        "make audit-deps",
        "azure/setup-helm",
        "python -m pip install -e .[dev]",
    ]:
        assert fragment in content
