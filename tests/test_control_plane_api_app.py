from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.auth import issue_service_token
from packages.shared.metrics import metrics_registry
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    ServiceTokenCreate,
    UserRole,
)
from packages.storage.control_plane import WorkerHeartbeatCreate
from packages.storage.ingestion_config import (
    IngestionConfigRepository,
    IngestionDefinitionCreate,
    SourceAssetCreate,
)
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import (
    FIXED_CREATED_AT,
    FIXED_DUE_AT,
    seed_source_asset_graph,
)


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
            runtime_now = datetime.now(UTC)
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            seeded = seed_source_asset_graph(repository)
            dispatch = repository.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)[0]
            first_token = issue_service_token("token-dashboard-001")
            repository.create_service_token(
                ServiceTokenCreate(
                    token_id=first_token.token_id,
                    token_name="dashboard-reader",
                    token_secret_hash=first_token.token_secret_hash,
                    role=UserRole.READER,
                    scopes=(SERVICE_TOKEN_SCOPE_REPORTS_READ,),
                    expires_at=runtime_now + timedelta(days=2),
                    created_at=FIXED_CREATED_AT,
                )
            )
            second_token = issue_service_token("token-bot-002")
            repository.create_service_token(
                ServiceTokenCreate(
                    token_id=second_token.token_id,
                    token_name="automation-bot",
                    token_secret_hash=second_token.token_secret_hash,
                    role=UserRole.READER,
                    scopes=(SERVICE_TOKEN_SCOPE_REPORTS_READ,),
                    created_at=FIXED_CREATED_AT,
                )
            )
            repository.record_service_token_use(
                second_token.token_id,
                used_at=runtime_now,
            )
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
                    "started_at": None,
                    "completed_at": None,
                    "run_ids": [],
                    "failure_reason": None,
                    "worker_detail": None,
                    "claimed_by_worker_id": None,
                    "claimed_at": None,
                    "claim_expires_at": None,
                }
            ]

            dispatch_detail_response = client.get(
                f"/control/schedule-dispatches/{dispatch.dispatch_id}"
            )
            assert dispatch_detail_response.status_code == 200
            assert (
                dispatch_detail_response.json()["schedule"]["schedule_id"]
                == "bank_partner_poll"
            )
            assert (
                dispatch_detail_response.json()["ingestion_definition"][
                    "ingestion_definition_id"
                ]
                == seeded["ingestion_definition"].ingestion_definition_id
            )
            assert (
                dispatch_detail_response.json()["source_asset"]["source_asset_id"]
                == seeded["source_asset"].source_asset_id
            )
            assert dispatch_detail_response.json()["runs"] == []

            ingest_response = client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            assert ingest_response.status_code == 201
            run_id = ingest_response.json()["run"]["run_id"]

            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            assert metrics_response.headers["content-type"].startswith("text/plain")
            assert "ingestion_runs_total 1" in metrics_response.text
            assert "auth_service_tokens_total 2" in metrics_response.text
            assert "auth_service_tokens_active 2" in metrics_response.text
            assert "auth_service_tokens_expiring_7d 1" in metrics_response.text
            assert "auth_service_tokens_never_used 1" in metrics_response.text
            assert "auth_service_tokens_used_24h 1" in metrics_response.text
            assert "worker_queue_depth 1" in metrics_response.text
            assert "worker_running_dispatches 0" in metrics_response.text
            assert "worker_stale_dispatches 0" in metrics_response.text
            assert "worker_active_workers 0" in metrics_response.text
            assert "worker_failed_dispatch_ratio 0" in metrics_response.text

            repository.mark_schedule_dispatch_status(
                dispatch.dispatch_id,
                status="completed",
                started_at=FIXED_DUE_AT,
                completed_at=FIXED_DUE_AT,
                run_ids=(run_id,),
                worker_detail="worker-complete",
            )
            completed_detail_response = client.get(
                f"/control/schedule-dispatches/{dispatch.dispatch_id}"
            )
            assert completed_detail_response.status_code == 200
            assert completed_detail_response.json()["dispatch"]["status"] == "completed"
            assert completed_detail_response.json()["dispatch"]["run_ids"] == [run_id]
            assert completed_detail_response.json()["runs"][0]["run_id"] == run_id

            repository.record_worker_heartbeat(
                WorkerHeartbeatCreate(
                    worker_id="worker-alpha",
                    status="idle",
                    observed_at=FIXED_DUE_AT,
                )
            )
            summary_response = client.get("/control/operational-summary")
            assert summary_response.status_code == 200
            assert summary_response.json()["queue"]["active_workers"] == 1
            assert summary_response.json()["queue"]["stale_running_dispatches"] == 0
            assert summary_response.json()["queue"]["recovered_dispatches"] == 0
            assert summary_response.json()["auth"]["service_tokens"]["active"] == 2
            assert (
                summary_response.json()["auth"]["service_tokens"]["expiring_within_7d"]
                == 1
            )
            assert summary_response.json()["auth"]["service_tokens"]["used_within_24h"] == 1
            assert summary_response.json()["workers"][0]["worker_id"] == "worker-alpha"
            assert "heartbeat_age_seconds" in summary_response.json()["workers"][0]
            assert summary_response.json()["recent_recovered_dispatches"] == []
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
        dispatch_id = dispatch_response.json()["dispatch"]["dispatch_id"]
        assert dispatch_response.json()["dispatch"]["schedule_id"] == "bank_partner_poll"

        blocked_retry_response = client.post(
            f"/control/schedule-dispatches/{dispatch_id}/retry",
        )
        assert blocked_retry_response.status_code == 409

        repository.mark_schedule_dispatch_status(
            dispatch_id,
            status="failed",
            started_at=FIXED_DUE_AT,
            completed_at=FIXED_DUE_AT,
            failure_reason="worker-failed",
            worker_detail="worker-failed",
        )
        retry_response = client.post(
            f"/control/schedule-dispatches/{dispatch_id}/retry",
        )
        assert retry_response.status_code == 201
        assert retry_response.json()["dispatch"]["status"] == "enqueued"
        assert retry_response.json()["dispatch"]["schedule_id"] == "bank_partner_poll"

        due_enqueue_response = client.post(
            "/control/schedule-dispatches",
            json={"limit": 1},
        )
        assert due_enqueue_response.status_code == 201
        assert "dispatches" in due_enqueue_response.json()


def test_control_plane_api_supports_archive_delete_and_include_archived_filters() -> None:
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

        source_asset_archive_response = client.patch(
            f"/config/source-assets/{seeded['source_asset'].source_asset_id}/archive",
            json={"archived": True},
        )
        assert source_asset_archive_response.status_code == 200
        assert source_asset_archive_response.json()["source_asset"]["archived"] is True
        assert source_asset_archive_response.json()["source_asset"]["enabled"] is False
        assert client.get("/config/source-assets").json()["source_assets"] == []
        source_asset_list_response = client.get(
            "/config/source-assets",
            params={"include_archived": "true"},
        )
        assert source_asset_list_response.status_code == 200
        assert source_asset_list_response.json()["source_assets"][0]["archived"] is True
        blocked_source_asset_delete = client.delete(
            f"/config/source-assets/{seeded['source_asset'].source_asset_id}"
        )
        assert blocked_source_asset_delete.status_code == 400
        assert "ingestion definitions" in blocked_source_asset_delete.json()["error"]
        client.patch(
            f"/config/source-assets/{seeded['source_asset'].source_asset_id}/archive",
            json={"archived": False},
        )

        orphan_source_asset = repository.create_source_asset(
            SourceAssetCreate(
                source_asset_id="bank_partner_transactions_orphan_api",
                source_system_id=seeded["source_asset"].source_system_id,
                dataset_contract_id=seeded["source_asset"].dataset_contract_id,
                column_mapping_id=seeded["source_asset"].column_mapping_id,
                transformation_package_id=seeded["source_asset"].transformation_package_id,
                name="Bank Partner Transactions Orphan API",
                asset_type=seeded["source_asset"].asset_type,
                description="Temporary asset for API delete coverage.",
                enabled=False,
                created_at=FIXED_CREATED_AT,
            )
        )
        orphan_archive_response = client.patch(
            f"/config/source-assets/{orphan_source_asset.source_asset_id}/archive",
            json={"archived": True},
        )
        assert orphan_archive_response.status_code == 200
        orphan_delete_response = client.delete(
            f"/config/source-assets/{orphan_source_asset.source_asset_id}"
        )
        assert orphan_delete_response.status_code == 204

        ingestion_definition_archive_response = client.patch(
            f"/config/ingestion-definitions/{seeded['ingestion_definition'].ingestion_definition_id}/archive",
            json={"archived": True},
        )
        assert ingestion_definition_archive_response.status_code == 200
        assert (
            ingestion_definition_archive_response.json()["ingestion_definition"]["archived"]
            is True
        )
        assert (
            ingestion_definition_archive_response.json()["ingestion_definition"]["enabled"]
            is False
        )
        assert client.get("/config/ingestion-definitions").json()["ingestion_definitions"] == []
        ingestion_definition_list_response = client.get(
            "/config/ingestion-definitions",
            params={"include_archived": "true"},
        )
        assert ingestion_definition_list_response.status_code == 200
        assert (
            ingestion_definition_list_response.json()["ingestion_definitions"][0][
                "archived"
            ]
            is True
        )
        blocked_definition_delete = client.delete(
            f"/config/ingestion-definitions/{seeded['ingestion_definition'].ingestion_definition_id}"
        )
        assert blocked_definition_delete.status_code == 400
        assert "schedules" in blocked_definition_delete.json()["error"]
        client.patch(
            f"/config/ingestion-definitions/{seeded['ingestion_definition'].ingestion_definition_id}/archive",
            json={"archived": False},
        )

        orphan_definition = repository.create_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id="bank_partner_watch_folder_orphan_api",
                source_asset_id=seeded["source_asset"].source_asset_id,
                transport="filesystem",
                schedule_mode="watch-folder",
                source_path="/tmp/homelab/orphan-api-inbox",
                file_pattern="*.csv",
                processed_path="/tmp/homelab/orphan-api-processed",
                failed_path="/tmp/homelab/orphan-api-failed",
                poll_interval_seconds=30,
                enabled=False,
                source_name="folder-watch-orphan-api",
                created_at=FIXED_CREATED_AT,
            )
        )
        orphan_definition_archive_response = client.patch(
            f"/config/ingestion-definitions/{orphan_definition.ingestion_definition_id}/archive",
            json={"archived": True},
        )
        assert orphan_definition_archive_response.status_code == 200
        orphan_definition_delete_response = client.delete(
            f"/config/ingestion-definitions/{orphan_definition.ingestion_definition_id}"
        )
        assert orphan_definition_delete_response.status_code == 204

        schedule_archive_response = client.patch(
            "/config/execution-schedules/bank_partner_poll/archive",
            json={"archived": True},
        )
        assert schedule_archive_response.status_code == 200
        assert schedule_archive_response.json()["execution_schedule"]["archived"] is True
        assert schedule_archive_response.json()["execution_schedule"]["enabled"] is False
        assert client.get("/config/execution-schedules").json()["execution_schedules"] == []
        schedule_list_response = client.get(
            "/config/execution-schedules",
            params={"include_archived": "true"},
        )
        assert schedule_list_response.status_code == 200
        assert schedule_list_response.json()["execution_schedules"][0]["archived"] is True
        blocked_dispatch_response = client.post(
            "/control/schedule-dispatches",
            json={"schedule_id": "bank_partner_poll"},
        )
        assert blocked_dispatch_response.status_code == 400
        assert "archived" in blocked_dispatch_response.json()["error"]
        schedule_delete_response = client.delete("/config/execution-schedules/bank_partner_poll")
        assert schedule_delete_response.status_code == 204


def test_bidirectional_lineage_endpoints() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seed_source_asset_graph(repository)
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

        # target_name filter on /control/source-lineage
        hit = client.get(
            "/control/source-lineage",
            params={"target_name": "fact_account_transaction"},
        )
        assert hit.status_code == 200
        assert len(hit.json()["lineage"]) == 1
        assert hit.json()["lineage"][0]["target_name"] == "fact_account_transaction"

        miss = client.get(
            "/control/source-lineage",
            params={"target_name": "no_such_publication"},
        )
        assert miss.status_code == 200
        assert miss.json()["lineage"] == []

        # /control/lineage/upstream: given a publication, return contributing sources
        upstream = client.get(
            "/control/lineage/upstream",
            params={"publication_key": "fact_account_transaction"},
        )
        assert upstream.status_code == 200
        assert upstream.json()["publication_key"] == "fact_account_transaction"
        assert upstream.json()["contributing_sources"] == ["manual-upload"]

        upstream_miss = client.get(
            "/control/lineage/upstream",
            params={"publication_key": "no_such_publication"},
        )
        assert upstream_miss.status_code == 200
        assert upstream_miss.json()["contributing_sources"] == []

        # /control/lineage/downstream: given a source, return dependent publications
        downstream = client.get(
            "/control/lineage/downstream",
            params={"source_asset_id": "manual-upload"},
        )
        assert downstream.status_code == 200
        assert downstream.json()["source_asset_id"] == "manual-upload"
        assert downstream.json()["publications"] == ["fact_account_transaction"]


def test_control_plane_api_confidence_endpoint_with_stale_only_filter() -> None:
    from datetime import UTC, datetime, timedelta

    from packages.platform.publication_confidence import FreshnessState
    from packages.storage.control_plane import PublicationConfidenceSnapshotCreate

    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seed_source_asset_graph(repository)
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

        now = datetime.now(UTC)

        # Record confidence snapshots with different freshness states
        repository.record_publication_confidence_snapshot(
            (
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="snap-001",
                    publication_key="fact_account_transaction",
                    assessed_at=now,
                    freshness_state=FreshnessState.CURRENT,
                    completeness_pct=100,
                    confidence_verdict="trustworthy",
                    quality_flags={"validation_errors": 0},
                    source_freshness_states={
                        "source1": {
                            "source_asset_id": "source1",
                            "freshness_state": "current",
                            "last_ingest_at": now.isoformat(),
                            "covered_through": "2026-04-07",
                        }
                    },
                ),
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="snap-002",
                    publication_key="fact_account_transaction",
                    assessed_at=now + timedelta(minutes=5),
                    freshness_state=FreshnessState.STALE,
                    completeness_pct=75,
                    confidence_verdict="degraded",
                    quality_flags={"validation_errors": 2},
                    source_freshness_states={
                        "source1": {
                            "source_asset_id": "source1",
                            "freshness_state": "overdue",
                            "last_ingest_at": (now - timedelta(hours=2)).isoformat(),
                            "covered_through": "2026-04-06",
                        }
                    },
                ),
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="snap-003",
                    publication_key="fact_account_transaction",
                    assessed_at=now + timedelta(minutes=10),
                    freshness_state=FreshnessState.UNAVAILABLE,
                    completeness_pct=0,
                    confidence_verdict="unavailable",
                    quality_flags={"validation_errors": 5},
                    source_freshness_states=None,
                ),
            )
        )

        # Test default (stale_only=false) - should return all snapshots
        response = client.get("/control/confidence")
        assert response.status_code == 200
        data = response.json()
        assert len(data["publications"]) == 3
        verdicts = {pub["freshness_state"] for pub in data["publications"]}
        assert verdicts == {FreshnessState.CURRENT, FreshnessState.STALE, FreshnessState.UNAVAILABLE}

        # All publications should have source_freshness_states and quality_flags in response
        for pub in data["publications"]:
            assert "source_freshness_states" in pub
            assert "quality_flags" in pub

        # Test stale_only=true - should return only STALE and UNAVAILABLE snapshots
        response_stale = client.get("/control/confidence", params={"stale_only": "true"})
        assert response_stale.status_code == 200
        data_stale = response_stale.json()
        assert len(data_stale["publications"]) == 2
        stale_verdicts = {pub["freshness_state"] for pub in data_stale["publications"]}
        assert stale_verdicts == {FreshnessState.STALE, FreshnessState.UNAVAILABLE}

        # Verify domain_summaries are recalculated from filtered set
        # Platform domain (default for fact_account_transaction)
        assert len(data_stale["domain_summaries"]) == 1
        assert data_stale["domain_summaries"][0]["domain"] == "platform"
        assert data_stale["domain_summaries"][0]["count"] == 2
        assert data_stale["domain_summaries"][0]["verdict"] == "unavailable"

        # Verify source_freshness_states are serialized correctly
        stale_pub = next(
            pub for pub in data_stale["publications"]
            if pub["freshness_state"] == FreshnessState.STALE
        )
        assert stale_pub["source_freshness_states"] is not None
        assert "source1" in stale_pub["source_freshness_states"]
        source_snap = stale_pub["source_freshness_states"]["source1"]
        assert source_snap["source_asset_id"] == "source1"
        assert source_snap["freshness_state"] == "overdue"
        assert source_snap["covered_through"] == "2026-04-06"


def test_control_plane_api_confidence_source_freshness_and_quality_flags() -> None:
    from datetime import UTC, datetime

    from packages.platform.publication_confidence import FreshnessState
    from packages.storage.control_plane import PublicationConfidenceSnapshotCreate

    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seed_source_asset_graph(repository)
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

        now = datetime.now(UTC)

        # Record a snapshot with comprehensive source_freshness_states
        repository.record_publication_confidence_snapshot(
            (
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="snap-complete",
                    publication_key="fact_account_transaction",
                    assessed_at=now,
                    freshness_state=FreshnessState.DUE_SOON,
                    completeness_pct=95,
                    confidence_verdict="degraded",
                    quality_flags={"validation_errors": 1, "parse_failures": 0},
                    source_freshness_states={
                        "source_a": {
                            "source_asset_id": "source_a",
                            "freshness_state": "due_soon",
                            "last_ingest_at": now.isoformat(),
                            "covered_through": "2026-04-07",
                        },
                        "source_b": {
                            "source_asset_id": "source_b",
                            "freshness_state": "current",
                            "last_ingest_at": now.isoformat(),
                            "covered_through": "2026-04-07",
                        },
                    },
                ),
            )
        )

        response = client.get("/control/confidence")
        assert response.status_code == 200
        data = response.json()
        assert len(data["publications"]) == 1

        pub = data["publications"][0]
        assert pub["publication_key"] == "fact_account_transaction"
        assert pub["quality_flags"] == {"validation_errors": 1, "parse_failures": 0}
        assert pub["source_freshness_states"] is not None
        assert len(pub["source_freshness_states"]) == 2
        assert "source_a" in pub["source_freshness_states"]
        assert "source_b" in pub["source_freshness_states"]


def test_get_confidence_detail_returns_404_when_publication_not_found() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
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

        response = client.get("/control/confidence/nonexistent_publication")
        assert response.status_code == 404
        assert "No confidence snapshot found" in response.json()["detail"]


def test_get_confidence_detail_returns_snapshot_when_found() -> None:
    from packages.storage.control_plane import PublicationConfidenceSnapshotCreate
    import uuid

    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        now = datetime.now(UTC)
        seeded = seed_source_asset_graph(repository)

        # Create a confidence snapshot
        snapshot_create = PublicationConfidenceSnapshotCreate(
            snapshot_id=str(uuid.uuid4()),
            publication_key="fact_account_transaction",
            freshness_state="CURRENT",
            confidence_verdict="TRUSTWORTHY",
            completeness_pct=100,
            quality_flags={"validation_errors": 0, "parse_failures": 0},
            assessed_at=now,
            source_freshness_states={
                "source_a": {
                    "source_asset_id": "source_a",
                    "freshness_state": "CURRENT",
                    "last_ingest_at": now.isoformat(),
                    "covered_through": (now - timedelta(days=1)).date().isoformat(),
                }
            },
            contributing_run_ids=("run-123", "run-124"),
        )
        repository.record_publication_confidence_snapshot((snapshot_create,))

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

        response = client.get("/control/confidence/fact_account_transaction")
        assert response.status_code == 200
        data = response.json()
        assert data["publication_key"] == "fact_account_transaction"
        assert data["freshness_state"] == "CURRENT"
        assert data["confidence_verdict"] == "TRUSTWORTHY"
        assert data["completeness_pct"] == 100
        assert data["quality_flags"] == {"validation_errors": 0, "parse_failures": 0}
        assert data["source_freshness_states"] is not None
        assert "source_a" in data["source_freshness_states"]
        assert set(data["contributing_run_ids"]) == {"run-123", "run-124"}
