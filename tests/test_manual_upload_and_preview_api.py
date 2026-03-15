from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import seed_source_asset_graph


def _build_client(temp_dir: str) -> tuple[TestClient, IngestionConfigRepository]:
    repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
    seed_source_asset_graph(repository)
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
    return client, repository


def test_api_supports_multipart_configured_csv_upload_by_source_asset_binding() -> None:
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_client(temp_dir)

        response = client.post(
            "/ingest/configured-csv",
            data={
                "source_asset_id": "bank_partner_transactions",
                "source_name": "browser-upload",
            },
            files={
                "file": (
                    "configured-upload.csv",
                    (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_bytes(),
                    "text/csv",
                )
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["run"]["dataset_name"] == "household_account_transactions"
        assert payload["run"]["source_name"] == "browser-upload"
        assert payload["run"]["status"] == "landed"


def test_api_previews_saved_column_mapping_versions_against_sample_csv() -> None:
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_client(temp_dir)

        response = client.post(
            "/config/column-mappings/preview",
            json={
                "dataset_contract_id": "household_account_transactions_v1",
                "column_mapping_id": "bank_partner_export_v1",
                "sample_csv": (
                    ACCOUNT_FIXTURES / "configured_account_transactions_source.csv"
                ).read_text(),
                "preview_limit": 2,
            },
        )

        assert response.status_code == 200
        preview = response.json()["preview"]
        assert preview["source_header"] == [
            "booking_date",
            "account_number",
            "payee",
            "amount_eur",
            "memo",
        ]
        assert preview["mapped_header"] == [
            "booked_at",
            "account_id",
            "counterparty_name",
            "amount",
            "currency",
            "description",
        ]
        assert preview["sample_row_count"] == 2
        assert len(preview["preview_rows"]) == 2
        assert preview["preview_rows"][0]["currency"] == "EUR"
        assert preview["issues"] == []


def test_api_archives_dataset_contract_and_column_mapping_versions_by_default_list_filter() -> None:
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_client(temp_dir)

        contract_archive = client.patch(
            "/config/dataset-contracts/household_account_transactions_v1/archive",
            json={"archived": True},
        )
        assert contract_archive.status_code == 200
        assert contract_archive.json()["dataset_contract"]["archived"] is True

        mapping_archive = client.patch(
            "/config/column-mappings/bank_partner_export_v1/archive",
            json={"archived": True},
        )
        assert mapping_archive.status_code == 200
        assert mapping_archive.json()["column_mapping"]["archived"] is True

        assert client.get("/config/dataset-contracts").json()["dataset_contracts"] == []
        assert client.get("/config/column-mappings").json()["column_mappings"] == []

        dataset_contracts = client.get(
            "/config/dataset-contracts",
            params={"include_archived": "true"},
        ).json()["dataset_contracts"]
        column_mappings = client.get(
            "/config/column-mappings",
            params={"include_archived": "true"},
        ).json()["column_mappings"]

        assert dataset_contracts[0]["dataset_contract_id"] == "household_account_transactions_v1"
        assert dataset_contracts[0]["archived"] is True
        assert column_mappings[0]["column_mapping_id"] == "bank_partner_export_v1"
        assert column_mappings[0]["archived"] is True
