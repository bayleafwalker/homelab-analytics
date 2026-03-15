from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.worker.main import main
from packages.shared.settings import AppSettings
from packages.storage.ingestion_config import IngestionConfigRepository
from tests.control_plane_test_support import FIXED_DUE_AT, seed_source_asset_graph


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
        source_repository = IngestionConfigRepository(
            source_settings.resolved_config_database_path
        )
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
            "execution_schedules": 1,
            "local_users": 0,
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
            assert [record.schedule_id for record in target_repository.list_execution_schedules()] == [
                "bank_partner_poll"
            ]
            assert [record.lineage_id for record in target_repository.list_source_lineage()] == [
                "lineage-001"
            ]
            assert [
                record.publication_audit_id
                for record in target_repository.list_publication_audit()
            ] == ["publication-001"]
