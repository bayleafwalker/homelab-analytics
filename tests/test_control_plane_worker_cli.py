from __future__ import annotations

import io
import json
import logging
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.worker.main import (
    _watch_schedule_dispatches,
    build_extension_registry,
    build_pipeline_registries,
    build_service,
    main,
)
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.shared.settings import AppSettings
from packages.storage.ingestion_config import (
    IngestionConfigRepository,
    IngestionDefinitionCreate,
)
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import (
    FIXED_CREATED_AT,
    FIXED_DUE_AT,
    seed_source_asset_graph,
)


def _build_settings(temp_dir: str) -> AppSettings:
    return AppSettings(
        data_dir=Path(temp_dir),
        landing_root=Path(temp_dir) / "landing",
        metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
        account_transactions_inbox_dir=Path(temp_dir) / "inbox" / "account-transactions",
        processed_files_dir=Path(temp_dir) / "processed" / "account-transactions",
        failed_files_dir=Path(temp_dir) / "failed" / "account-transactions",
        api_host="127.0.0.1",
        api_port=8080,
        web_host="127.0.0.1",
        web_port=8081,
        worker_poll_interval_seconds=30,
    )


def test_worker_cli_lists_enqueues_and_marks_schedule_dispatches() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        repository = IngestionConfigRepository(settings.resolved_config_database_path)
        seed_source_asset_graph(repository)

        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = main(
            ["list-execution-schedules"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["execution_schedules"] == [
            {
                "schedule_id": "bank_partner_poll",
                "target_kind": "ingestion_definition",
                "target_ref": "bank_partner_watch_folder",
                "cron_expression": "*/5 * * * *",
                "timezone": "UTC",
                "enabled": True,
                "archived": False,
                "max_concurrency": 1,
                "next_due_at": FIXED_DUE_AT.isoformat(),
                "last_enqueued_at": None,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ]

        stdout = io.StringIO()
        exit_code = main(
            ["enqueue-due-schedules", "--as-of", FIXED_DUE_AT.isoformat()],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        dispatch_payload = json.loads(stdout.getvalue())
        dispatch_id = dispatch_payload["dispatches"][0]["dispatch_id"]
        assert dispatch_payload["dispatches"][0]["schedule_id"] == "bank_partner_poll"

        stdout = io.StringIO()
        exit_code = main(
            ["list-schedule-dispatches", "--status", "enqueued"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["dispatches"][0]["dispatch_id"] == dispatch_id

        stdout = io.StringIO()
        exit_code = main(
            ["mark-schedule-dispatch", dispatch_id, "--status", "completed"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["dispatch"]["status"] == "completed"


def test_worker_cli_exports_and_imports_control_plane_snapshots() -> None:
    with TemporaryDirectory() as source_dir:
        source_settings = _build_settings(source_dir)
        source_repository = IngestionConfigRepository(source_settings.resolved_config_database_path)
        seed_source_asset_graph(source_repository)
        export_path = Path(source_dir) / "control-plane.json"
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = main(
            ["export-control-plane", str(export_path)],
            stdout=stdout,
            stderr=stderr,
            settings=source_settings,
        )
        assert exit_code == 0
        assert export_path.exists()
        assert json.loads(stdout.getvalue())["snapshot"] == {
            "source_systems": 1,
            "dataset_contracts": 1,
            "column_mappings": 1,
            "source_assets": 1,
            "ingestion_definitions": 1,
            "extension_registry_sources": 0,
            "extension_registry_revisions": 0,
            "extension_registry_activations": 0,
            "execution_schedules": 1,
            "source_lineage": 1,
            "publication_audit": 1,
            "auth_audit_events": 0,
            "local_users": 0,
            "service_tokens": 0,
        }

        with TemporaryDirectory() as target_dir:
            target_settings = _build_settings(target_dir)
            stdout = io.StringIO()
            exit_code = main(
                ["import-control-plane", str(export_path)],
                stdout=stdout,
                stderr=stderr,
                settings=target_settings,
            )
            assert exit_code == 0
            assert json.loads(stdout.getvalue())["imported"] is True

            target_repository = IngestionConfigRepository(
                target_settings.resolved_config_database_path
            )
            assert (
                target_repository.get_source_system("bank_partner_export").name
                == "Bank Partner Export"
            )
            assert [
                record.schedule_id for record in target_repository.list_execution_schedules()
            ] == ["bank_partner_poll"]
            assert [record.lineage_id for record in target_repository.list_source_lineage()] == [
                "lineage-001"
            ]
            assert [
                record.publication_audit_id for record in target_repository.list_publication_audit()
            ] == ["publication-001"]


def test_worker_cli_processes_enqueued_schedule_dispatch() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        repository = IngestionConfigRepository(settings.resolved_config_database_path)
        seeded = seed_source_asset_graph(repository)
        inbox_dir = Path(temp_dir) / "configured-inbox"
        processed_dir = Path(temp_dir) / "configured-processed"
        failed_dir = Path(temp_dir) / "configured-failed"
        inbox_dir.mkdir()
        (inbox_dir / "valid.csv").write_text(
            (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_text()
        )

        repository.update_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id=seeded["ingestion_definition"].ingestion_definition_id,
                source_asset_id=seeded["source_asset"].source_asset_id,
                transport="filesystem",
                schedule_mode="watch-folder",
                source_path=str(inbox_dir),
                file_pattern="*.csv",
                processed_path=str(processed_dir),
                failed_path=str(failed_dir),
                poll_interval_seconds=30,
                enabled=True,
                source_name="folder-watch",
                created_at=FIXED_CREATED_AT,
            )
        )
        dispatch_id = repository.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)[0].dispatch_id

        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = main(
            ["process-schedule-dispatch", dispatch_id],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )

        assert exit_code == 0
        payload = json.loads(stdout.getvalue())
        assert payload["dispatch"]["dispatch_id"] == dispatch_id
        assert payload["dispatch"]["status"] == "completed"
        assert payload["dispatch"]["started_at"] is not None
        assert payload["dispatch"]["completed_at"] is not None
        assert payload["dispatch"]["failure_reason"] is None
        assert payload["dispatch"]["run_ids"]
        assert payload["dispatch"]["worker_detail"]
        assert payload["dispatch"]["claimed_by_worker_id"] is not None
        assert payload["result"]["processed_files"] == 1
        assert len(payload["promotions"]) == len(payload["dispatch"]["run_ids"])
        assert payload["worker_heartbeat"]["status"] == "idle"

        stored_dispatch = repository.get_schedule_dispatch(dispatch_id)
        assert stored_dispatch.status == "completed"
        assert stored_dispatch.run_ids
        assert stored_dispatch.failure_reason is None
        assert stored_dispatch.worker_detail is not None
        assert stored_dispatch.claimed_by_worker_id is not None
        assert (
            repository.list_worker_heartbeats()[0].worker_id == stored_dispatch.claimed_by_worker_id
        )
        assert len(list(processed_dir.iterdir())) == 1
        assert list(failed_dir.iterdir()) == []


def test_worker_cli_watch_loop_enqueues_claims_and_processes_dispatches() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        repository = IngestionConfigRepository(settings.resolved_config_database_path)
        seeded = seed_source_asset_graph(repository)
        inbox_dir = Path(temp_dir) / "watch-inbox"
        processed_dir = Path(temp_dir) / "watch-processed"
        failed_dir = Path(temp_dir) / "watch-failed"
        inbox_dir.mkdir()
        (inbox_dir / "valid.csv").write_text(
            (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_text()
        )

        repository.update_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id=seeded["ingestion_definition"].ingestion_definition_id,
                source_asset_id=seeded["source_asset"].source_asset_id,
                transport="filesystem",
                schedule_mode="watch-folder",
                source_path=str(inbox_dir),
                file_pattern="*.csv",
                processed_path=str(processed_dir),
                failed_path=str(failed_dir),
                poll_interval_seconds=30,
                enabled=True,
                source_name="folder-watch",
                created_at=FIXED_CREATED_AT,
            )
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = main(
            [
                "watch-schedule-dispatches",
                "--worker-id",
                "worker-loop",
                "--max-iterations",
                "1",
            ],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )

        assert exit_code == 0
        payload = json.loads(stdout.getvalue())
        assert payload["worker_id"] == "worker-loop"
        assert payload["dispatch"]["status"] == "completed"
        assert payload["dispatch"]["claimed_by_worker_id"] == "worker-loop"
        assert payload["worker_heartbeat"]["worker_id"] == "worker-loop"
        assert payload["worker_heartbeat"]["status"] == "idle"
        assert len(payload["enqueued_dispatches"]) == 1
        assert len(list(processed_dir.iterdir())) == 1
        assert repository.list_worker_heartbeats()[0].worker_id == "worker-loop"

        stdout = io.StringIO()
        exit_code = main(
            ["list-worker-heartbeats"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["workers"][0]["worker_id"] == "worker-loop"


def test_worker_cli_renews_schedule_dispatch_leases_for_long_running_work(
    monkeypatch,
) -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        repository = IngestionConfigRepository(settings.resolved_config_database_path)
        seeded = seed_source_asset_graph(repository)
        inbox_dir = Path(temp_dir) / "slow-inbox"
        processed_dir = Path(temp_dir) / "slow-processed"
        failed_dir = Path(temp_dir) / "slow-failed"
        inbox_dir.mkdir()
        (inbox_dir / "valid.csv").write_text(
            (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_text()
        )

        repository.update_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id=seeded["ingestion_definition"].ingestion_definition_id,
                source_asset_id=seeded["source_asset"].source_asset_id,
                transport="filesystem",
                schedule_mode="watch-folder",
                source_path=str(inbox_dir),
                file_pattern="*.csv",
                processed_path=str(processed_dir),
                failed_path=str(failed_dir),
                poll_interval_seconds=30,
                enabled=True,
                source_name="folder-watch",
                created_at=FIXED_CREATED_AT,
            )
        )
        dispatch_id = repository.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)[0].dispatch_id

        original_process = ConfiguredIngestionDefinitionService.process_ingestion_definition

        def slow_process(self, ingestion_definition_id: str):
            time.sleep(1.2)
            return original_process(self, ingestion_definition_id)

        monkeypatch.setattr(
            ConfiguredIngestionDefinitionService,
            "process_ingestion_definition",
            slow_process,
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = main(
            [
                "process-schedule-dispatch",
                dispatch_id,
                "--worker-id",
                "worker-slow",
                "--lease-seconds",
                "1",
            ],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )

        assert exit_code == 0
        payload = json.loads(stdout.getvalue())
        assert payload["dispatch"]["status"] == "completed"
        assert payload["lease_renewals"] >= 1


def test_worker_cli_watch_loop_recovers_stale_dispatches_before_processing() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        repository = IngestionConfigRepository(settings.resolved_config_database_path)
        seeded = seed_source_asset_graph(repository)
        inbox_dir = Path(temp_dir) / "recover-inbox"
        processed_dir = Path(temp_dir) / "recover-processed"
        failed_dir = Path(temp_dir) / "recover-failed"
        inbox_dir.mkdir()
        (inbox_dir / "valid.csv").write_text(
            (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_text()
        )

        repository.update_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id=seeded["ingestion_definition"].ingestion_definition_id,
                source_asset_id=seeded["source_asset"].source_asset_id,
                transport="filesystem",
                schedule_mode="watch-folder",
                source_path=str(inbox_dir),
                file_pattern="*.csv",
                processed_path=str(processed_dir),
                failed_path=str(failed_dir),
                poll_interval_seconds=30,
                enabled=True,
                source_name="folder-watch",
                created_at=FIXED_CREATED_AT,
            )
        )
        stale_dispatch = repository.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)[0]
        repository.claim_schedule_dispatch(
            stale_dispatch.dispatch_id,
            worker_id="worker-dead",
            claimed_at=FIXED_DUE_AT,
            lease_seconds=1,
            worker_detail="worker-dead",
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = main(
            [
                "watch-schedule-dispatches",
                "--worker-id",
                "worker-recover",
                "--max-iterations",
                "1",
            ],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )

        assert exit_code == 0
        payload = json.loads(stdout.getvalue())
        assert len(payload["recovered_dispatches"]) == 1
        assert payload["recovered_dispatches"][0]["stale_dispatch"]["dispatch_id"] == (
            stale_dispatch.dispatch_id
        )
        assert payload["dispatch"]["status"] == "completed"
        assert payload["dispatch"]["dispatch_id"] != stale_dispatch.dispatch_id
        assert repository.get_schedule_dispatch(stale_dispatch.dispatch_id).status == "failed"
        assert len(list(processed_dir.iterdir())) == 1


def test_watch_schedule_dispatches_records_stopped_heartbeat_on_shutdown() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        service = build_service(settings)
        repository = IngestionConfigRepository(settings.resolved_config_database_path)
        configured_definition_service = ConfiguredIngestionDefinitionService(
            landing_root=settings.landing_root,
            metadata_repository=service.metadata_repository,
            config_repository=repository,
            blob_store=service.blob_store,
        )
        extension_registry = build_extension_registry(settings)
        pipeline_registries = build_pipeline_registries(settings)
        shutdown_event = threading.Event()
        shutdown_event.set()
        stdout = io.StringIO()

        exit_code = _watch_schedule_dispatches(
            output=stdout,
            settings=settings,
            config_repository=repository,
            service=service,
            configured_definition_service=configured_definition_service,
            extension_registry=extension_registry,
            promotion_handler_registry=pipeline_registries.promotion_handler_registry,
            transformation_domain_registry=(
                pipeline_registries.transformation_domain_registry
            ),
            publication_refresh_registry=pipeline_registries.publication_refresh_registry,
            logger=logging.getLogger("test.worker.shutdown"),
            worker_id="worker-stop",
            lease_seconds=30,
            shutdown_event=shutdown_event,
        )

        assert exit_code == 0
        payload = json.loads(stdout.getvalue())
        assert payload["worker_heartbeat"]["status"] == "stopped"
        assert repository.list_worker_heartbeats()[0].status == "stopped"
