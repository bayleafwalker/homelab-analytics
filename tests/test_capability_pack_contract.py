"""Contract tests for capability pack validation rules."""
from __future__ import annotations

import pytest

from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.platform.capability_types import (
    CapabilityPack,
    PublicationDefinition,
    PublicationFieldDefinition,
    UiDescriptor,
    WorkflowDefinition,
    dimension_field,
    measure_field,
    time_field,
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
                schema_version="1.0.0",
                display_name="Test Publication",
                description="A test publication.",
                visibility="public",
                lineage_required=True,
                retention_policy="indefinite",
                field_semantics={
                    "period_month": time_field(
                        "Calendar month bucket for the test publication.",
                        grain="month",
                    ),
                    "value": measure_field(
                        "Test measure value.",
                        aggregation="sum",
                        unit="currency",
                    ),
                    "category": dimension_field(
                        "Test grouping dimension."
                    ),
                },
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
        schema_version="1.0.0",
        display_name="Test Publication",
        description="A test publication.",
        visibility="public",
        lineage_required=True,
        retention_policy="indefinite",
    )
    defaults.update(overrides)
    return PublicationDefinition(**defaults)


def _minimal_ui_descriptor(**overrides) -> UiDescriptor:
    defaults = dict(
        key="test-ui",
        nav_label="Test",
        nav_path="/test",
        kind="dashboard",
        publication_keys=("test_pub",),
        icon=None,
    )
    defaults.update(overrides)
    return UiDescriptor(**defaults)


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


def test_publication_missing_schema_version_fails_validation() -> None:
    pack = _minimal_pack(publications=(_minimal_publication(schema_version=""),))
    with pytest.raises(ValueError, match="must declare schema_version"):
        pack.validate()


def test_publication_missing_retention_policy_fails_validation() -> None:
    pack = _minimal_pack(publications=(_minimal_publication(retention_policy=""),))
    with pytest.raises(ValueError, match="must declare retention_policy"):
        pack.validate()


def test_publication_measure_field_missing_aggregation_fails_validation() -> None:
    pack = _minimal_pack(
        publications=(
            _minimal_publication(
                field_semantics={
                    "value": measure_field(
                        "Test measure value.",
                        aggregation="sum",
                        unit="currency",
                    ),
                    "broken_value": measure_field(
                        "Broken measure value.",
                        aggregation="sum",
                        unit="currency",
                    ),
                    "broken_measure": PublicationFieldDefinition(
                        description="Broken measure value.",
                        semantic_role="measure",
                        unit="currency",
                        aggregation=None,
                    ),
                }
            ),
        )
    )
    with pytest.raises(ValueError, match="must declare aggregation"):
        pack.validate()


def test_publication_time_field_missing_grain_fails_validation() -> None:
    pack = _minimal_pack(
        publications=(
            _minimal_publication(
                field_semantics={
                    "period_month": PublicationFieldDefinition(
                        description="Calendar month bucket for the test publication.",
                        semantic_role="time",
                        grain=None,
                    ),
                }
            ),
        )
    )
    with pytest.raises(ValueError, match="must declare grain"):
        pack.validate()


# ---------------------------------------------------------------------------
# Pack-local referential integrity
# ---------------------------------------------------------------------------


def test_duplicate_workflow_ids_fails_validation() -> None:
    wf_a = _minimal_workflow(workflow_id="dup-wf", publication_keys=("test_pub",))
    wf_b = _minimal_workflow(workflow_id="dup-wf", publication_keys=("test_pub",))
    pack = _minimal_pack(workflows=(wf_a, wf_b))
    with pytest.raises(ValueError, match="duplicate workflow_id: 'dup-wf'"):
        pack.validate()


def test_duplicate_publication_keys_fails_validation() -> None:
    pub_a = _minimal_publication(key="dup_pub")
    pub_b = _minimal_publication(key="dup_pub")
    pack = _minimal_pack(publications=(pub_a, pub_b))
    with pytest.raises(ValueError, match="duplicate publication key: 'dup_pub'"):
        pack.validate()


def test_duplicate_ui_descriptor_keys_fails_validation() -> None:
    ui_a = _minimal_ui_descriptor(key="dup-ui")
    ui_b = _minimal_ui_descriptor(key="dup-ui")
    pack = _minimal_pack(ui_descriptors=(ui_a, ui_b))
    with pytest.raises(ValueError, match="duplicate UI descriptor key: 'dup-ui'"):
        pack.validate()


def test_workflow_referencing_unknown_publication_key_fails_validation() -> None:
    wf = _minimal_workflow(publication_keys=("nonexistent_pub",))
    pack = _minimal_pack(workflows=(wf,))
    with pytest.raises(ValueError, match="references publication key 'nonexistent_pub'"):
        pack.validate()


def test_ui_descriptor_referencing_unknown_publication_key_fails_validation() -> None:
    ui = _minimal_ui_descriptor(publication_keys=("nonexistent_pub",))
    pack = _minimal_pack(ui_descriptors=(ui,))
    with pytest.raises(ValueError, match="references publication key 'nonexistent_pub'"):
        pack.validate()


def test_workflow_referencing_valid_publication_key_passes_validation() -> None:
    wf = _minimal_workflow(publication_keys=("test_pub",))
    pack = _minimal_pack(workflows=(wf,))
    pack.validate()  # must not raise


def test_ui_descriptor_referencing_valid_publication_key_passes_validation() -> None:
    ui = _minimal_ui_descriptor(publication_keys=("test_pub",))
    pack = _minimal_pack(ui_descriptors=(ui,))
    pack.validate()  # must not raise


def test_publication_renderer_hints_default_to_empty_dict() -> None:
    publication = _minimal_publication()
    assert publication.renderer_hints == {}


def test_ui_descriptor_defaults_include_web_renderer_and_empty_metadata() -> None:
    ui = _minimal_ui_descriptor()
    assert ui.required_permissions == ()
    assert ui.supported_renderers == ("web",)
    assert ui.renderer_hints == {}
    assert ui.default_filters == {}


def test_ui_descriptor_missing_supported_renderers_fails_validation() -> None:
    pack = _minimal_pack(
        ui_descriptors=(
            _minimal_ui_descriptor(supported_renderers=()),  # type: ignore[arg-type]
        )
    )
    with pytest.raises(ValueError, match="supported renderer"):
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
    # contract_prices source moved to UTILITIES_PACK
    assert "contract_prices" not in dataset_names


def test_finance_pack_has_expected_publications() -> None:
    pub_keys = {p.key for p in FINANCE_PACK.publications}
    assert "monthly_cashflow" in pub_keys
    assert "subscription_summary" in pub_keys
    # contract_price_current and utility publications moved to UTILITIES_PACK
    assert "contract_price_current" not in pub_keys
    assert "electricity_price_current" not in pub_keys
    assert "utility_cost_summary" not in pub_keys


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


# ---------------------------------------------------------------------------
# UTILITIES_PACK integrity
# ---------------------------------------------------------------------------


def test_utilities_pack_validates_cleanly() -> None:
    UTILITIES_PACK.validate()


def test_utilities_pack_has_expected_publications() -> None:
    pub_keys = {p.key for p in UTILITIES_PACK.publications}
    assert "electricity_price_current" in pub_keys
    assert "utility_cost_summary" in pub_keys
    assert "contract_price_current" in pub_keys


def test_utilities_pack_is_executable() -> None:
    """Utilities must own at least one source and one workflow."""
    assert len(UTILITIES_PACK.sources) > 0, "Utilities pack must declare at least one source"
    assert len(UTILITIES_PACK.workflows) > 0, "Utilities pack must declare at least one workflow"


def test_utilities_pack_has_expected_sources() -> None:
    dataset_names = {s.dataset_name for s in UTILITIES_PACK.sources}
    assert "utility_rates" in dataset_names
    assert "contract_prices" in dataset_names


def test_utilities_pack_workflow_ids_are_unique() -> None:
    ids = [w.workflow_id for w in UTILITIES_PACK.workflows]
    assert len(ids) == len(set(ids)), f"UTILITIES_PACK workflow_ids must be unique, got: {ids}"


def test_utilities_pack_all_publications_have_lineage_required() -> None:
    for pub in UTILITIES_PACK.publications:
        assert pub.lineage_required, f"Publication '{pub.key}' must require lineage"


def test_utilities_pack_all_publications_have_retention_policy() -> None:
    for pub in UTILITIES_PACK.publications:
        assert pub.retention_policy, f"Publication '{pub.key}' must declare retention_policy"


def test_utilities_pack_all_publications_have_description() -> None:
    for pub in UTILITIES_PACK.publications:
        assert pub.description, f"Publication '{pub.key}' must have a description"


# ---------------------------------------------------------------------------
# Cross-pack ownership
# ---------------------------------------------------------------------------


def test_no_publication_key_owned_by_multiple_packs() -> None:
    all_keys: list[str] = []
    for pack in (FINANCE_PACK, UTILITIES_PACK):
        all_keys.extend(p.key for p in pack.publications)
    seen: set[str] = set()
    duplicates = {k for k in all_keys if k in seen or seen.add(k)}  # type: ignore[func-returns-value]
    assert not duplicates, f"Publication keys owned by multiple packs: {duplicates}"


def test_utility_publication_keys_not_in_finance_pack() -> None:
    finance_pub_keys = {p.key for p in FINANCE_PACK.publications}
    utilities_pub_keys = {p.key for p in UTILITIES_PACK.publications}
    overlap = finance_pub_keys & utilities_pub_keys
    assert not overlap, f"Keys owned by both finance and utilities: {overlap}"


# ---------------------------------------------------------------------------
# Publication discovery — all pack publications have reporting relations
# ---------------------------------------------------------------------------


def test_all_pack_publications_have_reporting_relations() -> None:
    from packages.domains.overview.manifest import OVERVIEW_PACK
    from packages.pipelines.builtin_reporting import PUBLICATION_RELATIONS

    relation_keys = set(PUBLICATION_RELATIONS.keys())
    missing: list[str] = []
    for pack in (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK):
        for pub in pack.publications:
            # Publication schema_name maps to mart_<schema_name> in reporting
            mart_key = f"mart_{pub.schema_name}"
            if mart_key not in relation_keys:
                missing.append(f"{pack.name}/{pub.schema_name} (expected {mart_key})")

    assert not missing, (
        f"Pack publications missing from PUBLICATION_RELATIONS (not discoverable): {missing}"
    )


def test_all_three_packs_have_expected_publication_count() -> None:
    from packages.domains.overview.manifest import OVERVIEW_PACK

    assert len(FINANCE_PACK.publications) == 7, (
        f"Finance should have 7 publications, got {len(FINANCE_PACK.publications)}"
    )
    assert len(UTILITIES_PACK.publications) == 7, (
        f"Utilities should have 7 publications, got {len(UTILITIES_PACK.publications)}"
    )
    assert len(OVERVIEW_PACK.publications) == 4, (
        f"Overview should have 4 publications, got {len(OVERVIEW_PACK.publications)}"
    )
