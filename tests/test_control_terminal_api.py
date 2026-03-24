from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.auth import hash_password, issue_service_token
from packages.storage.auth_store import LocalUserCreate, ServiceTokenCreate, UserRole
from packages.storage.control_plane import WorkerHeartbeatCreate
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    IngestionConfigRepository,
)
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import FIXED_CREATED_AT, FIXED_DUE_AT, seed_source_asset_graph


def _build_client(temp_dir: str, repository: IngestionConfigRepository) -> tuple[TestClient, IngestionConfigRepository]:
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
    return client, repository


def test_control_terminal_api_lists_manifest_and_executes_allowlisted_commands() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seed_source_asset_graph(repository)
        repository.create_local_user(
            LocalUserCreate(
                user_id="user-terminal-admin",
                username="terminal-admin",
                password_hash=hash_password("retro-terminal"),
                role=UserRole.ADMIN,
                created_at=FIXED_CREATED_AT,
            )
        )
        issued_token = issue_service_token("terminal-reader")
        repository.create_service_token(
            ServiceTokenCreate(
                token_id=issued_token.token_id,
                token_name="terminal-reader",
                token_secret_hash=issued_token.token_secret_hash,
                role=UserRole.READER,
                scopes=("reports:read",),
                created_at=FIXED_CREATED_AT,
            )
        )
        repository.record_worker_heartbeat(
            WorkerHeartbeatCreate(
                worker_id="worker-alpha",
                status="idle",
                observed_at=FIXED_DUE_AT,
            )
        )
        repository.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)
        client, _ = _build_client(temp_dir, repository)

        ingest = client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "terminal-seed",
            },
        )
        assert ingest.status_code == 201

        commands_response = client.get("/control/terminal/commands")
        assert commands_response.status_code == 200
        commands = {entry["name"]: entry for entry in commands_response.json()["commands"]}
        assert set(commands) == {
            "help",
            "status",
            "runs",
            "dispatches",
            "heartbeats",
            "freshness",
            "schedules",
            "tokens",
            "audit",
            "publication-audit",
            "users",
            "source-systems",
            "source-assets",
            "ingestion-definitions",
            "publication-definitions",
            "lineage",
            "verify-config",
            "enqueue-due",
        }
        assert commands["enqueue-due"]["mutating"] is True
        assert commands["help"]["mutating"] is False

        command_lines = (
            "help",
            "status",
            "runs 1",
            "dispatches enqueued",
            "heartbeats",
            "freshness",
            "schedules 1",
            "tokens 1",
            "audit 5",
            "publication-audit 1",
            "users 1",
            "source-systems 1",
            "source-assets 1",
            "ingestion-definitions 1",
            "publication-definitions 1",
            "lineage 1",
            "verify-config",
            "enqueue-due 1",
        )
        for command_line in command_lines:
            response = client.post(
                "/control/terminal/execute",
                json={"command_line": command_line},
            )
            assert response.status_code == 200, command_line
            execution = response.json()["execution"]
            assert execution["status"] == "succeeded", command_line
            assert execution["exit_code"] == 0, command_line
            assert execution["normalized_command"] == command_line

        verify_config = client.post(
            "/control/terminal/execute",
            json={"command_line": "verify-config"},
        )
        report = verify_config.json()["execution"]["result"]["report"]
        assert report["passed"] is True

        runs = client.post(
            "/control/terminal/execute",
            json={"command_line": "runs 1"},
        )
        assert runs.json()["execution"]["result"]["limit"] == 1

        dispatches = client.post(
            "/control/terminal/execute",
            json={"command_line": "dispatches enqueued"},
        )
        assert dispatches.json()["execution"]["result"]["status"] == "enqueued"

        schedules = client.post(
            "/control/terminal/execute",
            json={"command_line": "schedules 1"},
        )
        assert schedules.json()["execution"]["result"]["limit"] == 1

        tokens = client.post(
            "/control/terminal/execute",
            json={"command_line": "tokens 1"},
        )
        assert tokens.json()["execution"]["result"]["limit"] == 1

        publication_audit = client.post(
            "/control/terminal/execute",
            json={"command_line": "publication-audit 1"},
        )
        assert publication_audit.json()["execution"]["result"]["limit"] == 1

        users = client.post(
            "/control/terminal/execute",
            json={"command_line": "users 1"},
        )
        assert users.json()["execution"]["result"]["limit"] == 1

        source_systems = client.post(
            "/control/terminal/execute",
            json={"command_line": "source-systems 1"},
        )
        assert source_systems.json()["execution"]["result"]["limit"] == 1

        source_assets = client.post(
            "/control/terminal/execute",
            json={"command_line": "source-assets 1"},
        )
        assert source_assets.json()["execution"]["result"]["limit"] == 1

        ingestion_definitions = client.post(
            "/control/terminal/execute",
            json={"command_line": "ingestion-definitions 1"},
        )
        assert ingestion_definitions.json()["execution"]["result"]["limit"] == 1

        publication_definitions = client.post(
            "/control/terminal/execute",
            json={"command_line": "publication-definitions 1"},
        )
        assert publication_definitions.json()["execution"]["result"]["limit"] == 1

        lineage = client.post(
            "/control/terminal/execute",
            json={"command_line": "lineage 1"},
        )
        assert lineage.json()["execution"]["result"]["limit"] == 1


def test_control_terminal_api_rejects_invalid_commands_and_shapes_failed_verify_config() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seeded = seed_source_asset_graph(repository)
        repository.create_column_mapping(
            ColumnMappingCreate(
                column_mapping_id="bank_partner_export_v2",
                source_system_id=seeded["source_system"].source_system_id,
                dataset_contract_id=seeded["dataset_contract"].dataset_contract_id,
                version=2,
                rules=(
                    ColumnMappingRule("amount", source_column="amount_eur"),
                    ColumnMappingRule("not_in_contract", default_value="bad"),
                ),
                created_at=FIXED_CREATED_AT,
            )
        )
        client, _ = _build_client(temp_dir, repository)

        rejected = client.post(
            "/control/terminal/execute",
            json={"command_line": "shell ls"},
        )
        assert rejected.status_code == 400
        rejected_execution = rejected.json()["execution"]
        assert rejected_execution["status"] == "rejected"
        assert rejected_execution["exit_code"] == 2
        assert "Unsupported command" in rejected_execution["stderr_lines"][0]

        verify_config = client.post(
            "/control/terminal/execute",
            json={"command_line": "verify-config"},
        )
        assert verify_config.status_code == 200
        execution = verify_config.json()["execution"]
        assert execution["status"] == "failed"
        assert execution["exit_code"] == 1
        assert execution["result"]["report"]["passed"] is False
        assert execution["stderr_lines"]
        assert any("unknown_target_column" in line for line in execution["stderr_lines"])


def test_control_terminal_api_records_audit_events_for_mutating_and_rejected_commands() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seed_source_asset_graph(repository)
        client, repository = _build_client(temp_dir, repository)

        succeeded = client.post(
            "/control/terminal/execute",
            json={"command_line": "enqueue-due 1"},
        )
        assert succeeded.status_code == 200

        rejected = client.post(
            "/control/terminal/execute",
            json={"command_line": "shell ls"},
        )
        assert rejected.status_code == 400

        events = repository.list_auth_audit_events(limit=10)
        event_types = [event.event_type for event in events]
        assert "terminal_command_succeeded" in event_types
        assert "terminal_command_rejected" in event_types

        enqueue_event = next(event for event in events if event.event_type == "terminal_command_succeeded")
        assert enqueue_event.detail is not None
        assert "command=enqueue-due 1" in enqueue_event.detail
        assert "mutating=true" in enqueue_event.detail

        rejected_event = next(event for event in events if event.event_type == "terminal_command_rejected")
        assert rejected_event.detail is not None
        assert "command=shell ls" in rejected_event.detail
        assert "Unsupported command: shell" in rejected_event.detail
