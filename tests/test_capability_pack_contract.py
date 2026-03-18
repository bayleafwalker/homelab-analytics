"""Contract tests for capability pack validation rules."""
from __future__ import annotations

import pytest

from packages.domains.finance.manifest import FINANCE_PACK
from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    WorkflowDefinition,
)

pytestmark = [pytest.mark.architecture]


def _minimal_pack(**overrides) -> CapabilityPack:
    defaults = dict(
        name="test",
        version="1.0.0",
        sources=(),
        workflows=(),
        publications=(
            PublicationDefinition(
                key="test_pub",
                schema_name="test_pub",
                display_name="Test Publication",
                description="A test publication.",
                visibility="public",
                lineage_required=True,
                retention_policy="indefinite",
            ),
        ),
        ui_descriptors=(),
    )
    defaults.update(overrides)
    return CapabilityPack(**defaults)


def _minimal_workflow(**overrides) -> WorkflowDefinition:
    defaults = dict(
        workflow_id="test-workflow",
        display_name="Test Workflow",
        source_dataset_name="test_source",
        retry_policy="always",
        idempotency_mode="run_id",
        required_permissions=("operator",),
        command_name="test-workflow",
        publication_keys=(),
    )
    defaults.update(overrides)
    return WorkflowDefinition(**defaults)


def _minimal_publication(**overrides) -> PublicationDefinition:
    defaults = dict(
        key="test_pub",
        schema_name="test_pub",
        display_name="Test Publication",
        description="A test publication.",
        visibility="public",
        lineage_required=True,
        retention_policy="indefinite",
    )
    defaults.update(overrides)
    return PublicationDefinition(**defaults)


# ---------------------------------------------------------------------------
# Pack-level validation
# ---------------------------------------------------------------------------


def test_pack_missing_name_fails_validation() -> None:
    pack = _minimal_pack(name="")
    with pytest.raises(ValueError, match="name is required"):
        pack.validate()


def test_pack_missing_version_fails_validation() -> None:
    pack = _minimal_pack(version="")
    with pytest.raises(ValueError, match="version is required"):
        pack.validate()


def test_pack_missing_publications_fails_validation() -> None:
    pack = _minimal_pack(publications=())
    with pytest.raises(ValueError, match="must declare at least one publication"):
        pack.validate()


def test_pack_with_all_required_fields_passes_validation() -> None:
    pack = _minimal_pack()
    pack.validate()  # must not raise


# ---------------------------------------------------------------------------
# Workflow validation
# ---------------------------------------------------------------------------


def test_workflow_missing_retry_policy_fails_validation() -> None:
    pack = _minimal_pack(workflows=(_minimal_workflow(retry_policy=""),))
    with pytest.raises(ValueError, match="must declare retry_policy"):
        pack.validate()


def test_workflow_missing_idempotency_mode_fails_validation() -> None:
    pack = _minimal_pack(workflows=(_minimal_workflow(idempotency_mode=""),))
    with pytest.raises(ValueError, match="must declare idempotency_mode"):
        pack.validate()


def test_workflow_missing_required_permissions_fails_validation() -> None:
    pack = _minimal_pack(
        workflows=(_minimal_workflow(required_permissions=None),)  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="must declare required_permissions"):
        pack.validate()


def test_workflow_missing_command_name_fails_validation() -> None:
    pack = _minimal_pack(workflows=(_minimal_workflow(command_name=""),))
    with pytest.raises(ValueError, match="must declare command_name"):
        pack.validate()


# ---------------------------------------------------------------------------
# Publication validation
# ---------------------------------------------------------------------------


def test_publication_missing_key_fails_validation() -> None:
    pack = _minimal_pack(publications=(_minimal_publication(key=""),))
    with pytest.raises(ValueError, match="must declare key"):
        pack.validate()


def test_publication_missing_schema_name_fails_validation() -> None:
    pack = _minimal_pack(publications=(_minimal_publication(schema_name=""),))
    with pytest.raises(ValueError, match="must declare schema_name"):
        pack.validate()


def test_publication_missing_visibility_fails_validation() -> None:
    pack = _minimal_pack(publications=(_minimal_publication(visibility=""),))
    with pytest.raises(ValueError, match="must declare visibility"):
        pack.validate()


def test_publication_missing_retention_policy_fails_validation() -> None:
    pack = _minimal_pack(publications=(_minimal_publication(retention_policy=""),))
    with pytest.raises(ValueError, match="must declare retention_policy"):
        pack.validate()


# ---------------------------------------------------------------------------
# FINANCE_PACK integrity
# ---------------------------------------------------------------------------


def test_finance_pack_validates_cleanly() -> None:
    FINANCE_PACK.validate()


def test_finance_pack_has_expected_sources() -> None:
    dataset_names = {s.dataset_name for s in FINANCE_PACK.sources}
    assert "account_transactions" in dataset_names
    assert "subscriptions" in dataset_names
    assert "contract_prices" in dataset_names


def test_finance_pack_has_expected_publications() -> None:
    pub_keys = {p.key for p in FINANCE_PACK.publications}
    assert "monthly_cashflow" in pub_keys
    assert "subscription_summary" in pub_keys
    assert "contract_price_current" in pub_keys
    assert "electricity_price_current" in pub_keys
    assert "utility_cost_summary" in pub_keys


def test_finance_pack_all_publications_have_lineage_required() -> None:
    for pub in FINANCE_PACK.publications:
        assert pub.lineage_required, f"Publication '{pub.key}' must require lineage"


def test_finance_pack_all_workflows_have_complete_declarations() -> None:
    for workflow in FINANCE_PACK.workflows:
        assert workflow.retry_policy, f"Workflow '{workflow.workflow_id}' missing retry_policy"
        assert workflow.idempotency_mode, (
            f"Workflow '{workflow.workflow_id}' missing idempotency_mode"
        )
        assert workflow.required_permissions is not None, (
            f"Workflow '{workflow.workflow_id}' missing required_permissions"
        )
        assert workflow.command_name, f"Workflow '{workflow.workflow_id}' missing command_name"


def test_finance_pack_all_publications_have_retention_policy() -> None:
    for pub in FINANCE_PACK.publications:
        assert pub.retention_policy, f"Publication '{pub.key}' must declare retention_policy"


def test_finance_pack_all_publications_have_description() -> None:
    for pub in FINANCE_PACK.publications:
        assert pub.description, f"Publication '{pub.key}' must have a description"
