from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from apps.api.export_contracts import export_contracts
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.household_reporting import PublicationRelation
from packages.platform.capability_types import CapabilityPack, PublicationDefinition
from packages.platform.publication_contracts import build_publication_contract_catalog

pytestmark = [pytest.mark.architecture]


def _publication_contract_map(catalog: dict[str, object]) -> dict[str, object]:
    contracts = catalog["publication_contracts"]
    assert isinstance(contracts, list)
    return {contract.publication_key: contract for contract in contracts}


def _ui_descriptor_map(catalog: dict[str, object]) -> dict[str, object]:
    descriptors = catalog["ui_descriptors"]
    assert isinstance(descriptors, list)
    return {descriptor.key: descriptor for descriptor in descriptors}


def test_export_contracts_writes_openapi_and_publication_catalog() -> None:
    with TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "generated"
        export_contracts(output_dir)

        openapi_path = output_dir / "openapi.json"
        publication_contracts_path = output_dir / "publication-contracts.json"

        assert openapi_path.is_file()
        assert publication_contracts_path.is_file()

        openapi_payload = json.loads(openapi_path.read_text())
        assert (
            "#/components/schemas/PublicationContractsResponse"
            == openapi_payload["paths"]["/contracts/publications"]["get"]["responses"]["200"][
                "content"
            ]["application/json"]["schema"]["$ref"]
        )
        assert (
            "#/components/schemas/MonthlyCashflowResponse"
            == openapi_payload["paths"]["/reports/monthly-cashflow"]["get"]["responses"]["200"][
                "content"
            ]["application/json"]["schema"]["$ref"]
        )

        publication_payload = json.loads(publication_contracts_path.read_text())
        assert "publication_contracts" in publication_payload
        assert "ui_descriptors" in publication_payload


def test_publication_contract_catalog_maps_columns_and_scalar_types() -> None:
    catalog = build_publication_contract_catalog(
        (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK)
    )
    publication_contracts = _publication_contract_map(catalog)
    ui_descriptors = _ui_descriptor_map(catalog)

    monthly_cashflow = publication_contracts["monthly_cashflow"]
    assert monthly_cashflow.relation_name == "mart_monthly_cashflow"
    assert monthly_cashflow.schema_version == "1.0.0"
    assert [column.name for column in monthly_cashflow.columns] == [
        "booking_month",
        "income",
        "expense",
        "net",
        "transaction_count",
    ]
    assert monthly_cashflow.columns[1].json_type == "string"
    assert monthly_cashflow.columns[4].json_type == "number"
    assert monthly_cashflow.columns[0].semantic_role == "time"
    assert monthly_cashflow.columns[0].grain == "month"
    assert monthly_cashflow.columns[1].semantic_role == "measure"
    assert monthly_cashflow.columns[1].aggregation == "sum"
    assert monthly_cashflow.columns[1].unit == "currency"

    backup_freshness = publication_contracts["backup_freshness"]
    backup_columns = {column.name: column for column in backup_freshness.columns}
    assert backup_columns["last_backup_at"].json_type == "string"
    assert backup_columns["last_size_bytes"].json_type == "number"
    assert backup_columns["is_stale"].json_type == "boolean"
    assert backup_columns["last_backup_at"].grain == "timestamp"
    assert backup_columns["last_size_bytes"].unit == "bytes"
    assert backup_columns["is_stale"].semantic_role == "status"
    assert set(backup_freshness.supported_renderers) == {"web", "ha"}
    assert backup_freshness.renderer_hints["ha_state_aggregation"] == "count"
    assert backup_freshness.renderer_hints["ha_filter_field"] == "is_stale"

    dim_category = publication_contracts["dim_category"]
    assert dim_category.relation_name == "rpt_current_dim_category"
    assert dim_category.schema_name == "dim_category"
    assert dim_category.display_name == "Current Categories"
    assert dim_category.description == "Current snapshot of the shared cross-domain category registry."
    dim_category_columns = {column.name: column for column in dim_category.columns}
    assert dim_category_columns["sk"].semantic_role == "identifier"
    assert dim_category_columns["category_id"].semantic_role == "identifier"
    assert (
        dim_category_columns["is_budget_eligible"].description
        == "Whether the category can be targeted by budget definitions."
    )

    dim_counterparty = publication_contracts["dim_counterparty"]
    assert dim_counterparty.schema_name == "dim_counterparty"
    assert dim_counterparty.display_name == "Current Counterparties"
    assert dim_counterparty.columns[0].name == "sk"
    assert dim_counterparty.columns[0].semantic_role == "identifier"
    counterparty_columns = {column.name: column for column in dim_counterparty.columns}
    assert (
        counterparty_columns["category"].description
        == "Current category slug assigned to the counterparty; this remains a free-text bridge until category_id governance lands in finance."
    )

    balance_descriptor = ui_descriptors["balance-trend"]
    assert balance_descriptor.supported_renderers == ("web",)
    assert balance_descriptor.required_permissions == ()
    assert balance_descriptor.renderer_hints["web_surface"] == "reports"
    assert balance_descriptor.renderer_hints["web_render_mode"] == "detail"
    assert balance_descriptor.renderer_hints["web_nav_group"] == "Money"

    overview_descriptor = ui_descriptors["overview"]
    assert overview_descriptor.renderer_hints["web_surface"] == "overview"
    assert overview_descriptor.renderer_hints["web_nav_group"] == "Overview"

    homelab_descriptor = ui_descriptors["homelab-services"]
    assert set(homelab_descriptor.supported_renderers) == {"web", "ha"}
    assert homelab_descriptor.renderer_hints["web_nav_group"] == "Operations"


def test_publication_contract_catalog_requires_reporting_relations() -> None:
    orphan_pack = CapabilityPack(
        name="orphan",
        version="1.0.0",
        sources=(),
        workflows=(),
        publications=(
            PublicationDefinition(
                key="orphan_publication",
                schema_name="orphan_publication",
                schema_version="1.0.0",
                display_name="Orphan Publication",
                description="Missing relation metadata.",
                visibility="public",
                lineage_required=True,
                retention_policy="indefinite",
            ),
        ),
        ui_descriptors=(),
    )

    with pytest.raises(ValueError, match="missing reporting relations"):
        build_publication_contract_catalog((orphan_pack,))


def test_publication_contract_catalog_requires_field_semantics_for_pack_publications() -> None:
    broken_pack = CapabilityPack(
        name="broken",
        version="1.0.0",
        sources=(),
        workflows=(),
        publications=(
            PublicationDefinition(
                key="broken_publication",
                schema_name="broken_publication",
                schema_version="1.0.0",
                display_name="Broken Publication",
                description="Missing semantic metadata for one field.",
                visibility="public",
                lineage_required=True,
                retention_policy="indefinite",
                field_semantics={},
            ),
        ),
        ui_descriptors=(),
    )

    with pytest.raises(ValueError, match="missing field semantics"):
        build_publication_contract_catalog(
            (broken_pack,),
            publication_relations={
                "mart_broken_publication": PublicationRelation(
                    relation_name="mart_broken_publication",
                    columns=[
                        ("period_month", "VARCHAR NOT NULL"),
                        ("value", "DECIMAL(18,4) NOT NULL"),
                    ],
                    order_by="period_month",
                )
            },
        )
