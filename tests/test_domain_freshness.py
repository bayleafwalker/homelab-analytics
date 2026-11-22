"""Platform domain-freshness aggregation and source-freshness domain labelling (#1553)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.routes import control_routes
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
    ColumnMappingCreate,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    SourceAssetCreate,
    SourceFreshnessConfigCreate,
)
from packages.storage.run_metadata import (
    IngestionRunCreate,
    IngestionRunStatus,
    RunMetadataRepository,
)
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


def test_source_freshness_preserves_stale_and_missing_sources_across_domains(
    tmp_path, monkeypatch
) -> None:
    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 10, 22)

    monkeypatch.setattr(control_routes, "date", FixedDate)
    client, repository, finance = _client(str(tmp_path))
    utility_contract = repository.create_dataset_contract(
        DatasetContractConfigCreate(
            dataset_contract_id="utility_usage_contract", dataset_name="utility_usage",
            version=1, allow_extra_columns=True, columns=(),
        )
    )
    utility_mapping = repository.create_column_mapping(
        ColumnMappingCreate(
            column_mapping_id="utility_usage_mapping", source_system_id=finance.source_system_id,
            dataset_contract_id=utility_contract.dataset_contract_id, version=1, rules=(),
        )
    )
    utility = repository.create_source_asset(
        SourceAssetCreate(
            source_asset_id="utility_meter", source_system_id=finance.source_system_id,
            dataset_contract_id=utility_contract.dataset_contract_id,
            column_mapping_id=utility_mapping.column_mapping_id,
            transformation_package_id="builtin_utility_usage", name="Utility meter",
            asset_type="dataset",
        )
    )
    for asset in (finance, utility):
        repository.create_source_freshness_config(
            SourceFreshnessConfigCreate(
                source_asset_id=asset.source_asset_id, acquisition_mode="manual_export",
                expected_frequency="monthly", coverage_kind="calendar_month",
                due_day_of_month=5, expected_window_days=2, freshness_sla_days=7,
                sensitivity_class="low", reminder_channel="dashboard",
                requires_human_action=True,
            )
        )
    RunMetadataRepository(tmp_path / "runs.db").create_run(
        IngestionRunCreate(
            run_id="old-finance-run", source_name="bank-export",
            dataset_name="household_account_transactions", file_name="old.csv",
            raw_path="old.csv", manifest_path="missing.json", sha256="0" * 64,
            row_count=1, header=("amount",), status=IngestionRunStatus.LANDED,
            passed=True, created_at=datetime(2026, 9, 10, tzinfo=UTC),
        )
    )

    with client:
        response = client.get("/control/source-freshness")

    assert response.status_code == 200, response.text
    rows = {row["source_asset_id"]: row for row in response.json()["datasets"]}
    assert set(rows) == {finance.source_asset_id, utility.source_asset_id}
    stale = rows[finance.source_asset_id]
    missing = rows[utility.source_asset_id]
    assert (stale["domain"], stale["freshness_state"], stale["latest_run_id"]) == (
        "finance", "overdue", "old-finance-run",
    )
    assert stale["covered_through"] is not None
    assert (missing["domain"], missing["freshness_state"], missing["latest_run_id"]) == (
        "utilities", "overdue", None,
    )
    assert missing["covered_through"] is None
