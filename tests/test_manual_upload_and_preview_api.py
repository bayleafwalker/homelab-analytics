from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.csv_validation import ColumnType
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
)
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


def test_api_detects_source_type_for_configured_csv_upload() -> None:
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_client(temp_dir)

        response = client.post(
            "/ingest/detect-source",
            files={
                "file": (
                    "configured-upload.csv",
                    (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_bytes(),
                    "text/csv",
                )
            },
        )

        assert response.status_code == 200
        detection = response.json()["detection"]
        assert detection["format"] == "csv"
        assert "booking_date" in detection["header_columns"]
        candidate = detection["candidate"]
        assert candidate["kind"] == "configured_csv"
        assert candidate["upload_path"] == "/upload/configured-csv"
        assert candidate["source_asset_id"] == "bank_partner_transactions"
        assert candidate["contract_id"] == "household_account_transactions_v1"
        assert candidate["confidence_label"] == "high"
        assert "booking_date" in candidate["matched_columns"]


def test_api_detects_ha_states_json_upload_target() -> None:
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_client(temp_dir)

        response = client.post(
            "/ingest/detect-source",
            files={
                "file": (
                    "ha-states.json",
                    (
                        '[{"entity_id":"sensor.kitchen_temperature","state":"21.3",'
                        '"last_changed":"2026-03-30T07:00:00+00:00"}]'
                    ).encode("utf-8"),
                    "application/json",
                )
            },
        )

        assert response.status_code == 200
        detection = response.json()["detection"]
        assert detection["format"] == "json"
        candidate = detection["candidate"]
        assert candidate["kind"] == "builtin"
        assert candidate["upload_path"] == "/upload/ha-states"
        assert candidate["contract_id"] == "home_assistant_states_json_v1"
        assert candidate["confidence_label"] == "high"
        assert candidate["matched_columns"] == ["entity_id", "state"]


def test_api_detection_returns_no_candidate_for_unknown_binary_upload() -> None:
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_client(temp_dir)

        response = client.post(
            "/ingest/detect-source",
            files={
                "file": (
                    "mystery.bin",
                    b"\x00\x01\x02\x03\x04",
                    "application/octet-stream",
                )
            },
        )

        assert response.status_code == 200
        detection = response.json()["detection"]
        assert detection["format"] == "unknown"
        assert detection["candidate"] is None
        assert detection["alternatives"] == []


def test_api_detection_returns_no_candidate_for_malformed_json() -> None:
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_client(temp_dir)

        response = client.post(
            "/ingest/detect-source",
            files={
                "file": (
                    "broken.json",
                    b"{not-valid-json",
                    "application/json",
                )
            },
        )

        assert response.status_code == 200
        detection = response.json()["detection"]
        assert detection["format"] == "json"
        assert detection["candidate"] is None
        assert detection["alternatives"] == []


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


def test_api_run_detail_retry_and_operational_summary_use_saved_manifest_context() -> None:
    with TemporaryDirectory() as temp_dir:
        client, _ = _build_client(temp_dir)

        first_response = client.post(
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
        assert first_response.status_code == 201
        first_run_id = first_response.json()["run"]["run_id"]

        run_response = client.get(f"/runs/{first_run_id}")
        assert run_response.status_code == 200
        run_payload = run_response.json()["run"]
        assert run_payload["context"]["source_asset_id"] == "bank_partner_transactions"
        assert run_payload["context"]["source_system_id"] == "bank_partner_export"
        assert run_payload["recovery"]["retry_supported"] is True
        assert run_payload["recovery"]["retry_kind"] == "configured_csv"

        retry_response = client.post(f"/runs/{first_run_id}/retry")
        assert retry_response.status_code == 201
        retry_run_id = retry_response.json()["run"]["run_id"]

        retried_run = client.get(f"/runs/{retry_run_id}")
        assert retried_run.status_code == 200
        assert retried_run.json()["run"]["context"]["retry_of_run_id"] == first_run_id

        summary_response = client.get("/control/operational-summary")
        assert summary_response.status_code == 200
        summary = summary_response.json()
        assert summary["source_assets"]["bank_partner_transactions"]["run_count"] == 2
        assert (
            summary["dataset_contracts"]["household_account_transactions_v1"]["run_count"]
            == 2
        )
        assert summary["column_mappings"]["bank_partner_export_v1"]["run_count"] == 2


def test_api_compares_dataset_contract_and_column_mapping_versions() -> None:
    with TemporaryDirectory() as temp_dir:
        client, repository = _build_client(temp_dir)

        repository.create_dataset_contract(
            DatasetContractConfigCreate(
                dataset_contract_id="household_account_transactions_v2",
                dataset_name="household_account_transactions",
                version=2,
                allow_extra_columns=True,
                columns=(
                    DatasetColumnConfig("booked_at", ColumnType.DATE),
                    DatasetColumnConfig("account_id", ColumnType.STRING),
                    DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                    DatasetColumnConfig("amount", ColumnType.DECIMAL),
                    DatasetColumnConfig("currency", ColumnType.STRING),
                    DatasetColumnConfig("description", ColumnType.STRING, required=False),
                    DatasetColumnConfig("category", ColumnType.STRING, required=False),
                ),
            )
        )
        repository.create_column_mapping(
            ColumnMappingCreate(
                column_mapping_id="bank_partner_export_v2",
                source_system_id="bank_partner_export",
                dataset_contract_id="household_account_transactions_v2",
                version=2,
                rules=(
                    ColumnMappingRule("booked_at", source_column="booking_date"),
                    ColumnMappingRule("account_id", source_column="account_number"),
                    ColumnMappingRule("counterparty_name", source_column="merchant"),
                    ColumnMappingRule("amount", source_column="amount_eur"),
                    ColumnMappingRule("currency", default_value="EUR"),
                    ColumnMappingRule("description", source_column="memo"),
                    ColumnMappingRule("category", default_value="uncategorized"),
                ),
            )
        )

        contract_diff = client.get(
            "/config/dataset-contracts/household_account_transactions_v1/diff",
            params={"other_id": "household_account_transactions_v2"},
        )
        assert contract_diff.status_code == 200
        contract_payload = contract_diff.json()["diff"]
        assert any(
            change["field"] == "allow_extra_columns"
            for change in contract_payload["field_changes"]
        )
        assert [column["name"] for column in contract_payload["column_changes"]["added"]] == [
            "category"
        ]

        mapping_diff = client.get(
            "/config/column-mappings/bank_partner_export_v1/diff",
            params={"other_id": "bank_partner_export_v2"},
        )
        assert mapping_diff.status_code == 200
        mapping_payload = mapping_diff.json()["diff"]
        assert any(
            change["target_column"] == "counterparty_name"
            for change in mapping_payload["rule_changes"]["changed"]
        )
        assert [rule["target_column"] for rule in mapping_payload["rule_changes"]["added"]] == [
            "category"
        ]
