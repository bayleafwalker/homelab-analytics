"""Platform domain-freshness aggregation and source-freshness domain labelling (#1553)."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.platform.domain_freshness import (
    domain_for_package,
    is_stale_publication,
    summarize_domains,
    worst_case_verdict,
)
from packages.storage.ingestion_config import (
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    SourceAssetCreate,
)
from packages.storage.run_metadata import RunMetadataRepository
from tests.control_plane_test_support import seed_source_asset_graph


def _client(temp_dir: str) -> tuple[TestClient, IngestionConfigRepository, object]:
    repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
    seeded = seed_source_asset_graph(repository)
    client = TestClient(
        create_app(
            AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            ),
            config_repository=repository,
            enable_unsafe_admin=True,
        )
    )
    return client, repository, seeded["source_asset"]


def _build_client_with_asset(
    temp_dir: str,
    *,
    source_asset_id: str,
    dataset_name: str,
) -> TestClient:
    """Seed the standard graph, then rebind the source asset to ``dataset_name``."""
    client, repository, source_asset = _client(temp_dir)
    if dataset_name != "household_account_transactions":
        contract = repository.create_dataset_contract(
            DatasetContractConfigCreate(
                dataset_contract_id=f"{source_asset_id}_contract",
                dataset_name=dataset_name,
                version=1,
                allow_extra_columns=True,
                columns=(),
            )
        )
        dataset_contract_id = contract.dataset_contract_id
    else:
        dataset_contract_id = source_asset.dataset_contract_id
    repository.update_source_asset(
        SourceAssetCreate(
            source_asset_id=source_asset.source_asset_id,
            source_system_id=source_asset.source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=source_asset.column_mapping_id,
            transformation_package_id=None,
            name=source_asset.name,
            asset_type=source_asset.asset_type,
            description=source_asset.description,
            created_at=source_asset.created_at,
        )
    )
    return client


def test_unknown_package_falls_back_to_a_spaced_label() -> None:
    assert domain_for_package("builtin_garden_sensors") == "garden sensors"
    assert domain_for_package("custom_household_costs") == "custom household costs"


def test_worst_case_verdict_keeps_the_winners_spelling() -> None:
    assert worst_case_verdict("DEGRADED", "degraded") == "DEGRADED"
    assert worst_case_verdict("bogus", "trustworthy") == "trustworthy"


def test_summarize_domains_counts_only_non_trustworthy_as_degraded() -> None:
    rows = [
        {"domain": "finance", "confidence_verdict": "Trustworthy", "freshness_state": "current"},
        {"domain": "finance", "confidence_verdict": "degraded", "freshness_state": "due_soon"},
    ]
    assert summarize_domains(rows) == [
        {
            "domain": "finance",
            "verdict": "degraded",
            "count": 2,
            "degraded_count": 1,
            "stale_count": 0,
        }
    ]
    assert not is_stale_publication("overdue")


def test_source_freshness_row_infers_domain_from_dataset_name() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client_with_asset(
            temp_dir,
            source_asset_id="bank_partner_transactions",
            dataset_name="household_account_transactions",
        )
        (row,) = client.get("/control/source-freshness").json()["datasets"]
        assert row["domain"] == "finance"


def test_source_freshness_row_without_a_resolvable_package_is_platform() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client_with_asset(
            temp_dir,
            source_asset_id="bank_partner_transactions",
            dataset_name="garden_sensors",
        )
        (row,) = client.get("/control/source-freshness").json()["datasets"]
        assert row["domain"] == "platform"
