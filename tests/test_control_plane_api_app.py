from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.metrics import metrics_registry
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import FIXED_DUE_AT, seed_source_asset_graph


def test_admin_routes_return_404_when_unsafe_admin_is_disabled() -> None:
    with TemporaryDirectory() as temp_dir:
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        client = TestClient(create_app(service))

        for path in [
            "/extensions",
            "/config/source-systems",
            "/control/source-lineage",
        ]:
            response = client.get(path)

            assert response.status_code == 404
            assert response.json()["detail"] == (
                "Unsafe admin routes are disabled until authentication is implemented."
            )


def test_control_plane_api_exposes_schedules_lineage_audit_and_metrics() -> None:
    metrics_registry.clear()
    try:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            seeded = seed_source_asset_graph(repository)
            dispatch = repository.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)[0]
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            client = TestClient(
                create_app(
                    service,
                    config_repository=repository,
                    enable_unsafe_admin=True,
                )
            )

            create_response = client.post(
                "/config/execution-schedules",
                json={
                    "schedule_id": "bank_partner_hourly",
                    "target_kind": "ingestion_definition",
                    "target_ref": seeded["ingestion_definition"].ingestion_definition_id,
                    "cron_expression": "0 * * * *",
                    "timezone": "UTC",
                    "enabled": True,
                    "max_concurrency": 2,
                },
            )
            assert create_response.status_code == 201
            assert (
                create_response.json()["execution_schedule"]["schedule_id"]
                == "bank_partner_hourly"
            )

            schedules_response = client.get("/config/execution-schedules")
            assert schedules_response.status_code == 200
            assert {
                item["schedule_id"]
                for item in schedules_response.json()["execution_schedules"]
            } == {"bank_partner_hourly", "bank_partner_poll"}

            lineage_response = client.get(
                "/control/source-lineage",
                params={"run_id": "run-001"},
            )
            assert lineage_response.status_code == 200
            assert lineage_response.json()["lineage"][0]["lineage_id"] == "lineage-001"

            audit_response = client.get(
                "/control/publication-audit",
                params={"run_id": "run-001"},
            )
            assert audit_response.status_code == 200
            assert (
                audit_response.json()["publication_audit"][0]["publication_audit_id"]
                == "publication-001"
            )

            dispatch_response = client.get(
                "/control/schedule-dispatches",
                params={"status": "enqueued"},
            )
            assert dispatch_response.status_code == 200
            assert dispatch_response.json()["dispatches"] == [
                {
                    "dispatch_id": dispatch.dispatch_id,
                    "schedule_id": "bank_partner_poll",
                    "target_kind": "ingestion_definition",
                    "target_ref": seeded["ingestion_definition"].ingestion_definition_id,
                    "enqueued_at": FIXED_DUE_AT.isoformat(),
                    "status": "enqueued",
                    "completed_at": None,
                }
            ]

            ingest_response = client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            assert ingest_response.status_code == 201

            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            assert metrics_response.headers["content-type"].startswith("text/plain")
            assert "ingestion_runs_total 1" in metrics_response.text
            assert "worker_queue_depth 1" in metrics_response.text
    finally:
        metrics_registry.clear()


def test_control_plane_api_updates_entities_and_enqueues_manual_dispatches() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seeded = seed_source_asset_graph(repository)
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        client = TestClient(
            create_app(
                service,
                config_repository=repository,
                enable_unsafe_admin=True,
            )
        )

        source_system_response = client.patch(
            f"/config/source-systems/{seeded['source_system'].source_system_id}",
            json={
                "source_system_id": seeded["source_system"].source_system_id,
                "name": "Bank Partner Export v2",
                "source_type": "api",
                "transport": "https",
                "schedule_mode": "scheduled",
                "description": "Updated source system.",
                "enabled": False,
            },
        )
        assert source_system_response.status_code == 200
        assert source_system_response.json()["source_system"]["enabled"] is False

        source_asset_response = client.patch(
            f"/config/source-assets/{seeded['source_asset'].source_asset_id}",
            json={
                "source_asset_id": seeded["source_asset"].source_asset_id,
                "source_system_id": seeded["source_system"].source_system_id,
                "dataset_contract_id": seeded["dataset_contract"].dataset_contract_id,
                "column_mapping_id": seeded["column_mapping"].column_mapping_id,
                "name": "Bank Partner Transactions v2",
                "asset_type": "dataset",
                "transformation_package_id": "builtin_account_transactions",
                "description": "Updated source asset.",
                "enabled": False,
            },
        )
        assert source_asset_response.status_code == 200
        assert source_asset_response.json()["source_asset"]["enabled"] is False

        ingestion_definition_response = client.patch(
            f"/config/ingestion-definitions/{seeded['ingestion_definition'].ingestion_definition_id}",
            json={
                "ingestion_definition_id": seeded["ingestion_definition"].ingestion_definition_id,
                "source_asset_id": seeded["source_asset"].source_asset_id,
                "transport": "filesystem",
                "schedule_mode": "watch-folder",
                "source_path": "/tmp/updated-inbox",
                "file_pattern": "*.txt",
                "processed_path": "/tmp/updated-processed",
                "failed_path": "/tmp/updated-failed",
                "poll_interval_seconds": 60,
                "request_url": None,
                "request_method": None,
                "request_headers": [],
                "request_timeout_seconds": None,
                "response_format": None,
                "output_file_name": None,
                "enabled": True,
                "source_name": "configured-ingestion-v2",
            },
        )
        assert ingestion_definition_response.status_code == 200
        assert (
            ingestion_definition_response.json()["ingestion_definition"]["file_pattern"]
            == "*.txt"
        )

        schedule_response = client.patch(
            "/config/execution-schedules/bank_partner_poll",
            json={
                "schedule_id": "bank_partner_poll",
                "target_kind": "ingestion_definition",
                "target_ref": seeded["ingestion_definition"].ingestion_definition_id,
                "cron_expression": "0 * * * *",
                "timezone": "UTC",
                "enabled": True,
                "max_concurrency": 2,
            },
        )
        assert schedule_response.status_code == 200
        assert schedule_response.json()["execution_schedule"]["max_concurrency"] == 2

        dispatch_response = client.post(
            "/control/schedule-dispatches",
            json={"schedule_id": "bank_partner_poll"},
        )
        assert dispatch_response.status_code == 201
        assert dispatch_response.json()["dispatch"]["schedule_id"] == "bank_partner_poll"

        due_enqueue_response = client.post(
            "/control/schedule-dispatches",
            json={"limit": 1},
        )
        assert due_enqueue_response.status_code == 201
        assert "dispatches" in due_enqueue_response.json()
