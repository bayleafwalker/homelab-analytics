"""Table-driven contract tests asserting FINANCE_PACK workflow declarations are complete.

Each parametrized test runs once per workflow, giving clear per-workflow failure messages
rather than a single aggregate assertion.
"""
from __future__ import annotations

import pytest

from packages.domains.finance.manifest import FINANCE_PACK

pytestmark = [pytest.mark.architecture]


@pytest.mark.parametrize("workflow", FINANCE_PACK.workflows, ids=lambda w: w.workflow_id)
def test_workflow_has_workflow_id(workflow) -> None:
    assert workflow.workflow_id, "Workflow must have a non-empty workflow_id"


@pytest.mark.parametrize("workflow", FINANCE_PACK.workflows, ids=lambda w: w.workflow_id)
def test_workflow_has_display_name(workflow) -> None:
    assert workflow.display_name, f"Workflow '{workflow.workflow_id}' must have a display_name"


@pytest.mark.parametrize("workflow", FINANCE_PACK.workflows, ids=lambda w: w.workflow_id)
def test_workflow_has_retry_policy(workflow) -> None:
    valid_policies = {"always", "on_failure", "never"}
    assert workflow.retry_policy in valid_policies, (
        f"Workflow '{workflow.workflow_id}' retry_policy must be one of {valid_policies}, "
        f"got '{workflow.retry_policy}'"
    )


@pytest.mark.parametrize("workflow", FINANCE_PACK.workflows, ids=lambda w: w.workflow_id)
def test_workflow_has_idempotency_mode(workflow) -> None:
    valid_modes = {"run_id", "content_hash", "none"}
    assert workflow.idempotency_mode in valid_modes, (
        f"Workflow '{workflow.workflow_id}' idempotency_mode must be one of {valid_modes}, "
        f"got '{workflow.idempotency_mode}'"
    )


@pytest.mark.parametrize("workflow", FINANCE_PACK.workflows, ids=lambda w: w.workflow_id)
def test_workflow_has_required_permissions(workflow) -> None:
    assert workflow.required_permissions is not None, (
        f"Workflow '{workflow.workflow_id}' must declare required_permissions"
    )
    assert len(workflow.required_permissions) > 0, (
        f"Workflow '{workflow.workflow_id}' required_permissions must not be empty"
    )


@pytest.mark.parametrize("workflow", FINANCE_PACK.workflows, ids=lambda w: w.workflow_id)
def test_workflow_source_dataset_name_references_known_source(workflow) -> None:
    known_sources = {s.dataset_name for s in FINANCE_PACK.sources}
    # configured_csv is a synthetic source not in the sources list — allow it
    synthetic_sources = {"configured_csv"}
    if workflow.source_dataset_name not in synthetic_sources:
        assert workflow.source_dataset_name in known_sources, (
            f"Workflow '{workflow.workflow_id}' source_dataset_name "
            f"'{workflow.source_dataset_name}' does not match any declared source. "
            f"Known: {known_sources}"
        )


def test_finance_pack_has_at_least_one_workflow() -> None:
    assert len(FINANCE_PACK.workflows) > 0, "FINANCE_PACK must declare at least one workflow"


def test_finance_pack_workflow_ids_are_unique() -> None:
    ids = [w.workflow_id for w in FINANCE_PACK.workflows]
    assert len(ids) == len(set(ids)), f"FINANCE_PACK workflow_ids must be unique, got: {ids}"


def test_ingest_contract_prices_produces_only_finance_publications() -> None:
    workflow = next(
        (w for w in FINANCE_PACK.workflows if w.workflow_id == "ingest-contract-prices"),
        None,
    )
    assert workflow is not None, "FINANCE_PACK must declare ingest-contract-prices workflow"
    finance_pub_keys = {p.key for p in FINANCE_PACK.publications}
    unknown_keys = set(workflow.publication_keys) - finance_pub_keys
    assert not unknown_keys, (
        f"ingest-contract-prices declares publication_keys not owned by FINANCE_PACK: {unknown_keys}"
    )
