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
        "web-token-check:",
        "web-ui-test:",
        "agent-preflight:",
        "sprintctl-health:",
        "sprintctl-preflight:",
        "sprintctl-close:",
        "verify-fast:",
        "verify-all:",
        "verify-domain:",
        "compose-smoke:",
        "db-migrate-postgres-control-plane:",
        "db-migrate-postgres-run-metadata:",
        "sprint-resume:",
        "claim-recover:",
        "claim-heartbeat:",
        "item-verify-auth:",
        "snapshot-refresh:",
        "knowledge-publish:",
    ]:
        assert target in content

    assert ".venv/bin/python" in content
    assert "test-sqlite-adapters:" in content
    assert "test-coverage:" in content
    assert (
        "verify-fast: lint typecheck test-fast test-sqlite-adapters "
        "verify-docs verify-agent verify-arch contract-export-check "
        "web-codegen-check web-token-check web-contracts-check web-build web-typecheck web-ui-test helm-lint"
    ) in content
    assert "APP_IMAGE := homelab-analytics:latest" in content
    assert "WEB_IMAGE := homelab-analytics-web:latest" in content
    assert "docker image inspect $(APP_IMAGE)" in content
    assert "docker image inspect $(WEB_IMAGE)" in content
    assert "migrations/postgres_run_metadata" in content


def test_workflow_helper_wraps_canonical_sprint_and_knowledge_flows() -> None:
    content = (ROOT / "tools" / "workflow.sh").read_text()

    for fragment in [
        "source \"$ROOT/.envrc\"",
        "agent_preflight()",
        "sprintctl_health()",
        "claim_start_preflight()",
        "claim_close()",
        "tcp_check_sprintctl_url",
        "ALLOW_OFFLINE_SPRINTCTL",
        ".sprintctl/claims/claim-${ITEM}.token",
        "sprintctl item done-from-claim",
        "args=(claim resume --json)",
        "sprintctl claim recover --item-id",
        "args=(claim heartbeat --id \"$CLAIM_ID\" --claim-token \"$CLAIM_TOKEN\" --json)",
        "args=(render --output \"$ROOT/docs/sprint-snapshots/sprint-current.txt\")",
        "args=(publish --id \"$CANDIDATE\" --body \"$BODY\" --category \"$CATEGORY\")",
        "kctl render --output \"$ROOT/docs/knowledge/knowledge-base.md\"",
        "\"$py\" -m ruff check",
        "\"$py\" -m mypy",
        "\"$py\" -m pytest tests/test_architecture_contract.py -x --tb=short",
    ]:
        assert fragment in content


def test_agent_runbooks_document_preflight_and_degraded_paths() -> None:
    sprint_ops = (ROOT / "docs" / "runbooks" / "sprint-and-knowledge-operations.md").read_text()
    working_practices = (ROOT / "docs" / "runbooks" / "project-working-practices.md").read_text()
    review_skill = (ROOT / ".agents" / "skills" / "dispatch-review" / "SKILL.md").read_text()

    for fragment in [
        "make agent-preflight",
        "make sprintctl-health",
        "make sprintctl-preflight ITEM=<item-id> ACTOR=<actor>",
        "make sprintctl-close ITEM=<item-id> CLAIM=<claim-id>",
        "Remote sprintctl unavailable mode",
        "offline implementation with deferred sprintctl closeout",
        "Session Closeout Checklist",
    ]:
        assert fragment in sprint_ops

    for fragment in [
        ".venv/bin/python -m pytest <targeted-tests> -x --tb=short",
        ".venv/bin/python -m pip install pytest pluggy ruff mypy mypy_extensions botocore duckdb psycopg",
        "Default verification order for local sessions",
        "tests.api_route_test_support.call_route(app, path, **params)",
        "intended scope file list",
    ]:
        assert fragment in working_practices

    for fragment in [
        "degraded review mode",
        "review degraded",
        "manual findings-first checklist for the seven specialist categories",
    ]:
        assert fragment in review_skill


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
