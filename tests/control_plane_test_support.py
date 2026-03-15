from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock, Thread
from typing import Any

from packages.pipelines.csv_validation import ColumnType
from packages.shared.auth import issue_service_token
from packages.storage.auth_store import (
    SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
    ServiceTokenCreate,
    UserRole,
)
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    ControlPlaneStore,
    ExecutionScheduleCreate,
    PublicationAuditCreate,
    SourceLineageCreate,
    WorkerHeartbeatCreate,
)
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionDefinitionCreate,
    SourceAssetCreate,
    SourceSystemCreate,
)

FIXED_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
FIXED_DUE_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
FIXED_AUDIT_AT = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def seed_source_asset_graph(
    store: ControlPlaneStore,
    *,
    include_schedule: bool = True,
    include_lineage: bool = True,
    include_audit: bool = True,
) -> dict[str, Any]:
    source_system = store.create_source_system(
        SourceSystemCreate(
            source_system_id="bank_partner_export",
            name="Bank Partner Export",
            source_type="file-drop",
            transport="filesystem",
            schedule_mode="manual",
            description="Bank partner CSV export.",
            created_at=FIXED_CREATED_AT,
        )
    )
    dataset_contract = store.create_dataset_contract(
        DatasetContractConfigCreate(
            dataset_contract_id="household_account_transactions_v1",
            dataset_name="household_account_transactions",
            version=1,
            allow_extra_columns=False,
            columns=(
                DatasetColumnConfig("booked_at", ColumnType.DATE),
                DatasetColumnConfig("account_id", ColumnType.STRING),
                DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                DatasetColumnConfig("amount", ColumnType.DECIMAL),
                DatasetColumnConfig("currency", ColumnType.STRING),
                DatasetColumnConfig("description", ColumnType.STRING, required=False),
            ),
            created_at=FIXED_CREATED_AT,
        )
    )
    column_mapping = store.create_column_mapping(
        ColumnMappingCreate(
            column_mapping_id="bank_partner_export_v1",
            source_system_id=source_system.source_system_id,
            dataset_contract_id=dataset_contract.dataset_contract_id,
            version=1,
            rules=(
                ColumnMappingRule("booked_at", source_column="booking_date"),
                ColumnMappingRule("account_id", source_column="account_number"),
                ColumnMappingRule("counterparty_name", source_column="payee"),
                ColumnMappingRule("amount", source_column="amount_eur"),
                ColumnMappingRule("currency", default_value="EUR"),
                ColumnMappingRule("description", source_column="memo"),
            ),
            created_at=FIXED_CREATED_AT,
        )
    )
    source_asset = store.create_source_asset(
        SourceAssetCreate(
            source_asset_id="bank_partner_transactions",
            source_system_id=source_system.source_system_id,
            dataset_contract_id=dataset_contract.dataset_contract_id,
            column_mapping_id=column_mapping.column_mapping_id,
            transformation_package_id="builtin_account_transactions",
            name="Bank Partner Transactions",
            asset_type="dataset",
            description="Canonical household account transactions.",
            created_at=FIXED_CREATED_AT,
        )
    )
    ingestion_definition = store.create_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id="bank_partner_watch_folder",
            source_asset_id=source_asset.source_asset_id,
            transport="filesystem",
            schedule_mode="watch-folder",
            source_path="/tmp/homelab/inbox",
            file_pattern="*.csv",
            processed_path="/tmp/homelab/processed",
            failed_path="/tmp/homelab/failed",
            poll_interval_seconds=30,
            enabled=True,
            source_name="folder-watch",
            created_at=FIXED_CREATED_AT,
        )
    )

    if include_schedule:
        store.create_execution_schedule(
            ExecutionScheduleCreate(
                schedule_id="bank_partner_poll",
                target_kind="ingestion_definition",
                target_ref=ingestion_definition.ingestion_definition_id,
                cron_expression="*/5 * * * *",
                timezone="UTC",
                enabled=True,
                max_concurrency=1,
                next_due_at=FIXED_DUE_AT,
                created_at=FIXED_CREATED_AT,
            )
        )
    if include_lineage:
        store.record_source_lineage(
            (
                SourceLineageCreate(
                    lineage_id="lineage-001",
                    input_run_id="run-001",
                    target_layer="transformation",
                    target_name="fact_account_transaction",
                    target_kind="fact",
                    row_count=2,
                    source_system="manual-upload",
                    source_run_id="run-001",
                    recorded_at=FIXED_CREATED_AT,
                ),
            )
        )
    if include_audit:
        store.record_publication_audit(
            (
                PublicationAuditCreate(
                    publication_audit_id="publication-001",
                    run_id="run-001",
                    publication_key="mart_monthly_cashflow",
                    relation_name="mart_monthly_cashflow",
                    status="published",
                    published_at=FIXED_CREATED_AT,
                ),
            )
        )

    return {
        "source_system": source_system,
        "dataset_contract": dataset_contract,
        "column_mapping": column_mapping,
        "source_asset": source_asset,
        "ingestion_definition": ingestion_definition,
    }


def assert_control_plane_store_round_trip(store: ControlPlaneStore) -> None:
    seeded = seed_source_asset_graph(store)

    assert (
        store.get_source_system(seeded["source_system"].source_system_id)
        == seeded["source_system"]
    )
    assert (
        store.get_dataset_contract(seeded["dataset_contract"].dataset_contract_id)
        == seeded["dataset_contract"]
    )
    assert (
        store.get_column_mapping(seeded["column_mapping"].column_mapping_id)
        == seeded["column_mapping"]
    )
    assert (
        store.get_source_asset(seeded["source_asset"].source_asset_id)
        == seeded["source_asset"]
    )
    assert (
        store.get_ingestion_definition(
            seeded["ingestion_definition"].ingestion_definition_id
        )
        == seeded["ingestion_definition"]
    )
    assert store.find_source_asset_by_binding(
        source_system_id=seeded["source_system"].source_system_id,
        dataset_contract_id=seeded["dataset_contract"].dataset_contract_id,
        column_mapping_id=seeded["column_mapping"].column_mapping_id,
    ) == seeded["source_asset"]
    assert (
        store.get_transformation_package("builtin_account_transactions").handler_key
        == "account_transactions"
    )
    assert "mart_monthly_cashflow" in {
        record.publication_key
        for record in store.list_publication_definitions(
            transformation_package_id="builtin_account_transactions"
        )
    }
    assert (
        store.get_execution_schedule("bank_partner_poll").target_ref
        == seeded["ingestion_definition"].ingestion_definition_id
    )
    assert [
        record.schedule_id for record in store.list_execution_schedules(enabled_only=True)
    ] == ["bank_partner_poll"]

    snapshot = store.export_snapshot()
    assert any(
        record.source_asset_id == seeded["source_asset"].source_asset_id
        for record in snapshot.source_assets
    )
    assert any(record.schedule_id == "bank_partner_poll" for record in snapshot.execution_schedules)
    assert any(record.lineage_id == "lineage-001" for record in snapshot.source_lineage)
    assert any(
        record.publication_audit_id == "publication-001"
        for record in snapshot.publication_audit
    )
    assert snapshot.auth_audit_events == ()


def assert_auth_audit_behaviour(store: ControlPlaneStore) -> None:
    store.record_auth_audit_events(
        (
            AuthAuditEventCreate(
                event_id="auth-001",
                event_type="login_failed",
                success=False,
                subject_username="ReaderOne",
                remote_addr="127.0.0.1",
                detail="Invalid password.",
                occurred_at=FIXED_AUDIT_AT,
            ),
            AuthAuditEventCreate(
                event_id="auth-002",
                event_type="login_succeeded",
                success=True,
                actor_user_id="user-admin-001",
                actor_username="admin",
                subject_user_id="user-reader-001",
                subject_username="readerone",
                remote_addr="127.0.0.1",
                occurred_at=FIXED_AUDIT_AT.replace(minute=5),
            ),
        )
    )

    all_events = store.list_auth_audit_events()
    assert [event.event_id for event in all_events] == ["auth-002", "auth-001"]

    failed_events = store.list_auth_audit_events(
        event_type="login_failed",
        success=False,
        subject_username="readerone",
        since=FIXED_AUDIT_AT,
        limit=5,
    )
    assert [event.event_id for event in failed_events] == ["auth-001"]


def assert_service_token_behaviour(store: ControlPlaneStore) -> None:
    issued_token = issue_service_token("token-001")
    created = store.create_service_token(
        ServiceTokenCreate(
            token_id=issued_token.token_id,
            token_name="home-assistant",
            token_secret_hash=issued_token.token_secret_hash,
            role=UserRole.OPERATOR,
            scopes=(
                SERVICE_TOKEN_SCOPE_REPORTS_READ,
                SERVICE_TOKEN_SCOPE_INGEST_WRITE,
            ),
            expires_at=FIXED_CREATED_AT + timedelta(days=30),
            created_at=FIXED_CREATED_AT,
        )
    )

    assert created.token_name == "home-assistant"
    assert created.scopes == (
        SERVICE_TOKEN_SCOPE_REPORTS_READ,
        SERVICE_TOKEN_SCOPE_INGEST_WRITE,
    )
    assert [record.token_id for record in store.list_service_tokens()] == ["token-001"]

    used = store.record_service_token_use(
        "token-001",
        used_at=FIXED_CREATED_AT + timedelta(hours=6),
    )
    assert used.last_used_at == FIXED_CREATED_AT + timedelta(hours=6)

    revoked = store.revoke_service_token(
        "token-001",
        revoked_at=FIXED_CREATED_AT + timedelta(days=2),
    )
    assert revoked.revoked_at == FIXED_CREATED_AT + timedelta(days=2)
    assert store.list_service_tokens() == []
    assert store.list_service_tokens(include_revoked=True)[0].token_secret_hash == issued_token.token_secret_hash
    assert any(
        record.token_id == "token-001" for record in store.export_snapshot().service_tokens
    )


def assert_schedule_dispatch_behaviour(store: ControlPlaneStore) -> None:
    seeded = seed_source_asset_graph(
        store,
        include_schedule=False,
        include_lineage=False,
        include_audit=False,
    )
    target_ref = seeded["ingestion_definition"].ingestion_definition_id
    due_at = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    blocked_as_of = datetime(2026, 1, 1, 0, 6, tzinfo=UTC)

    store.create_execution_schedule(
        ExecutionScheduleCreate(
            schedule_id="enabled-schedule",
            target_kind="ingestion_definition",
            target_ref=target_ref,
            cron_expression="*/5 * * * *",
            timezone="UTC",
            enabled=True,
            max_concurrency=1,
            next_due_at=due_at,
            created_at=FIXED_CREATED_AT,
        )
    )
    store.create_execution_schedule(
        ExecutionScheduleCreate(
            schedule_id="disabled-schedule",
            target_kind="ingestion_definition",
            target_ref=target_ref,
            cron_expression="*/5 * * * *",
            timezone="UTC",
            enabled=False,
            max_concurrency=1,
            next_due_at=due_at,
            created_at=FIXED_CREATED_AT,
        )
    )

    first_dispatches = store.enqueue_due_execution_schedules(as_of=due_at)
    assert [dispatch.schedule_id for dispatch in first_dispatches] == ["enabled-schedule"]
    assert first_dispatches[0].started_at is None
    assert first_dispatches[0].run_ids == ()
    assert first_dispatches[0].failure_reason is None
    assert first_dispatches[0].worker_detail is None
    assert (
        store.get_execution_schedule("enabled-schedule").last_enqueued_at == due_at
    )
    assert (
        store.get_schedule_dispatch(first_dispatches[0].dispatch_id).dispatch_id
        == first_dispatches[0].dispatch_id
    )

    # Even when the schedule is due again, an active dispatch blocks a duplicate enqueue.
    assert store.enqueue_due_execution_schedules(as_of=blocked_as_of) == []
    assert store.list_schedule_dispatches(schedule_id="disabled-schedule") == []

    running = store.claim_schedule_dispatch(
        first_dispatches[0].dispatch_id,
        worker_id="worker-alpha",
        claimed_at=blocked_as_of,
        lease_seconds=300,
        worker_detail="worker-started",
    )
    assert running.status == "running"
    assert running.started_at == blocked_as_of
    assert running.worker_detail == "worker-started"
    assert running.claimed_by_worker_id == "worker-alpha"
    assert running.claimed_at == blocked_as_of
    assert running.claim_expires_at == datetime(2026, 1, 1, 0, 11, tzinfo=UTC)

    heartbeat = store.record_worker_heartbeat(
        WorkerHeartbeatCreate(
            worker_id="worker-alpha",
            status="running",
            active_dispatch_id=running.dispatch_id,
            detail="Processing enabled-schedule.",
            observed_at=blocked_as_of,
        )
    )
    assert heartbeat.worker_id == "worker-alpha"
    assert heartbeat.active_dispatch_id == running.dispatch_id
    assert store.list_worker_heartbeats()[0].worker_id == "worker-alpha"

    assert store.enqueue_due_execution_schedules(as_of=blocked_as_of) == []
    assert (
        store.claim_next_schedule_dispatch(
            worker_id="worker-beta",
            claimed_at=blocked_as_of,
            lease_seconds=300,
        )
        is None
    )

    failed = store.mark_schedule_dispatch_status(
        first_dispatches[0].dispatch_id,
        status="failed",
        completed_at=blocked_as_of,
        run_ids=("run-001",),
        failure_reason="boom",
        worker_detail="worker-failed",
    )
    assert failed.status == "failed"
    assert failed.run_ids == ("run-001",)
    assert failed.failure_reason == "boom"
    assert failed.worker_detail == "worker-failed"

    second_dispatches = store.enqueue_due_execution_schedules(as_of=blocked_as_of)
    assert [dispatch.schedule_id for dispatch in second_dispatches] == ["enabled-schedule"]
    assert (
        store.get_execution_schedule("enabled-schedule").next_due_at
        == datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    )
    second_running = store.claim_next_schedule_dispatch(
        worker_id="worker-beta",
        claimed_at=blocked_as_of,
        lease_seconds=300,
        worker_detail="worker-next",
    )
    assert second_running is not None
    assert second_running.dispatch_id == second_dispatches[0].dispatch_id
    assert second_running.claimed_by_worker_id == "worker-beta"
    completed = store.mark_schedule_dispatch_status(
        second_dispatches[0].dispatch_id,
        status="completed",
        started_at=blocked_as_of,
        completed_at=datetime(2026, 1, 1, 0, 7, tzinfo=UTC),
        run_ids=("run-002",),
        worker_detail="worker-completed",
    )
    assert completed.status == "completed"
    assert completed.run_ids == ("run-002",)
    assert completed.claimed_by_worker_id == "worker-beta"
    assert [
        dispatch.dispatch_id
        for dispatch in store.list_schedule_dispatches(
            schedule_id="enabled-schedule",
            status="completed",
        )
    ] == [second_dispatches[0].dispatch_id]
    assert [
        dispatch.dispatch_id
        for dispatch in store.list_schedule_dispatches(
            schedule_id="enabled-schedule",
            status="failed",
        )
    ] == [first_dispatches[0].dispatch_id]


def assert_control_plane_store_update_behaviour(store: ControlPlaneStore) -> None:
    seeded = seed_source_asset_graph(store)

    archived_contract = store.set_dataset_contract_archived_state(
        seeded["dataset_contract"].dataset_contract_id,
        archived=True,
    )
    assert archived_contract.archived is True
    assert store.list_dataset_contracts() == []
    assert store.list_dataset_contracts(include_archived=True)[0].dataset_contract_id == (
        seeded["dataset_contract"].dataset_contract_id
    )

    restored_contract = store.set_dataset_contract_archived_state(
        seeded["dataset_contract"].dataset_contract_id,
        archived=False,
    )
    assert restored_contract.archived is False

    archived_mapping = store.set_column_mapping_archived_state(
        seeded["column_mapping"].column_mapping_id,
        archived=True,
    )
    assert archived_mapping.archived is True
    assert store.list_column_mappings() == []
    assert store.list_column_mappings(include_archived=True)[0].column_mapping_id == (
        seeded["column_mapping"].column_mapping_id
    )

    restored_mapping = store.set_column_mapping_archived_state(
        seeded["column_mapping"].column_mapping_id,
        archived=False,
    )
    assert restored_mapping.archived is False

    updated_source_system = store.update_source_system(
        SourceSystemCreate(
            source_system_id=seeded["source_system"].source_system_id,
            name="Bank Partner Export v2",
            source_type="api",
            transport="https",
            schedule_mode="scheduled",
            description="Updated control-plane source system.",
            enabled=False,
            created_at=seeded["source_system"].created_at,
        )
    )
    assert updated_source_system.name == "Bank Partner Export v2"
    assert updated_source_system.enabled is False

    restored_source_system = store.update_source_system(
        SourceSystemCreate(
            source_system_id=seeded["source_system"].source_system_id,
            name=updated_source_system.name,
            source_type=updated_source_system.source_type,
            transport=updated_source_system.transport,
            schedule_mode=updated_source_system.schedule_mode,
            description=updated_source_system.description,
            enabled=True,
            created_at=updated_source_system.created_at,
        )
    )
    assert restored_source_system.enabled is True

    updated_source_asset = store.update_source_asset(
        SourceAssetCreate(
            source_asset_id=seeded["source_asset"].source_asset_id,
            source_system_id=seeded["source_asset"].source_system_id,
            dataset_contract_id=seeded["source_asset"].dataset_contract_id,
            column_mapping_id=seeded["source_asset"].column_mapping_id,
            transformation_package_id=seeded["source_asset"].transformation_package_id,
            name="Bank Partner Transactions v2",
            asset_type=seeded["source_asset"].asset_type,
            description="Updated source asset.",
            enabled=False,
            created_at=seeded["source_asset"].created_at,
        )
    )
    assert updated_source_asset.enabled is False
    assert (
        store.find_source_asset_by_binding(
            source_system_id=seeded["source_system"].source_system_id,
            dataset_contract_id=seeded["dataset_contract"].dataset_contract_id,
            column_mapping_id=seeded["column_mapping"].column_mapping_id,
        )
        is None
    )

    restored_source_asset = store.update_source_asset(
        SourceAssetCreate(
            source_asset_id=updated_source_asset.source_asset_id,
            source_system_id=updated_source_asset.source_system_id,
            dataset_contract_id=updated_source_asset.dataset_contract_id,
            column_mapping_id=updated_source_asset.column_mapping_id,
            transformation_package_id=updated_source_asset.transformation_package_id,
            name=updated_source_asset.name,
            asset_type=updated_source_asset.asset_type,
            description=updated_source_asset.description,
            enabled=True,
            created_at=updated_source_asset.created_at,
        )
    )
    assert restored_source_asset.enabled is True

    archived_source_asset = store.set_source_asset_archived_state(
        restored_source_asset.source_asset_id,
        archived=True,
    )
    assert archived_source_asset.archived is True
    assert archived_source_asset.enabled is False
    assert {
        record.source_asset_id for record in store.list_source_assets(include_archived=True)
    } >= {archived_source_asset.source_asset_id}
    assert (
        store.find_source_asset_by_binding(
            source_system_id=seeded["source_system"].source_system_id,
            dataset_contract_id=seeded["dataset_contract"].dataset_contract_id,
            column_mapping_id=seeded["column_mapping"].column_mapping_id,
        )
        is None
    )
    try:
        store.create_ingestion_definition(
            IngestionDefinitionCreate(
                ingestion_definition_id="archived-source-asset-definition",
                source_asset_id=archived_source_asset.source_asset_id,
                transport="filesystem",
                schedule_mode="watch-folder",
                source_path="/tmp/homelab/inbox",
                file_pattern="*.csv",
                processed_path="/tmp/homelab/processed",
                failed_path="/tmp/homelab/failed",
                poll_interval_seconds=30,
                enabled=True,
                source_name="folder-watch",
                created_at=FIXED_CREATED_AT,
            )
        )
    except ValueError as exc:
        assert "archived" in str(exc)
    else:
        raise AssertionError("Expected archived source assets to reject new ingestion definitions")
    try:
        store.delete_source_asset(archived_source_asset.source_asset_id)
    except ValueError as exc:
        assert "ingestion definitions" in str(exc)
    else:
        raise AssertionError("Expected source asset deletion to enforce dependencies")

    restored_source_asset = store.set_source_asset_archived_state(
        archived_source_asset.source_asset_id,
        archived=False,
    )
    assert restored_source_asset.archived is False

    orphan_source_asset = store.create_source_asset(
        SourceAssetCreate(
            source_asset_id="bank_partner_transactions_orphan",
            source_system_id=seeded["source_asset"].source_system_id,
            dataset_contract_id=seeded["source_asset"].dataset_contract_id,
            column_mapping_id=seeded["source_asset"].column_mapping_id,
            transformation_package_id=seeded["source_asset"].transformation_package_id,
            name="Bank Partner Transactions Orphan",
            asset_type=seeded["source_asset"].asset_type,
            description="Temporary asset for delete contract coverage.",
            enabled=False,
            created_at=FIXED_CREATED_AT,
        )
    )
    orphan_source_asset = store.set_source_asset_archived_state(
        orphan_source_asset.source_asset_id,
        archived=True,
    )
    store.delete_source_asset(orphan_source_asset.source_asset_id)
    try:
        store.get_source_asset(orphan_source_asset.source_asset_id)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected archived source asset deletion to remove the record")

    updated_definition = store.update_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id=seeded["ingestion_definition"].ingestion_definition_id,
            source_asset_id=restored_source_asset.source_asset_id,
            transport="filesystem",
            schedule_mode="watch-folder",
            source_path="/tmp/homelab/updated-inbox",
            file_pattern="*.txt",
            processed_path="/tmp/homelab/updated-processed",
            failed_path="/tmp/homelab/updated-failed",
            poll_interval_seconds=120,
            enabled=False,
            source_name="folder-watch-v2",
            created_at=seeded["ingestion_definition"].created_at,
        )
    )
    assert updated_definition.source_path == "/tmp/homelab/updated-inbox"
    assert updated_definition.enabled is False
    assert store.list_ingestion_definitions(enabled_only=True) == []

    restored_definition = store.update_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id=updated_definition.ingestion_definition_id,
            source_asset_id=updated_definition.source_asset_id,
            transport=updated_definition.transport,
            schedule_mode=updated_definition.schedule_mode,
            source_path=updated_definition.source_path,
            file_pattern=updated_definition.file_pattern,
            processed_path=updated_definition.processed_path,
            failed_path=updated_definition.failed_path,
            poll_interval_seconds=updated_definition.poll_interval_seconds,
            request_url=updated_definition.request_url,
            request_method=updated_definition.request_method,
            request_headers=updated_definition.request_headers,
            request_timeout_seconds=updated_definition.request_timeout_seconds,
            response_format=updated_definition.response_format,
            output_file_name=updated_definition.output_file_name,
            enabled=True,
            source_name=updated_definition.source_name,
            created_at=updated_definition.created_at,
        )
    )
    assert restored_definition.enabled is True

    archived_definition = store.set_ingestion_definition_archived_state(
        restored_definition.ingestion_definition_id,
        archived=True,
    )
    assert archived_definition.archived is True
    assert archived_definition.enabled is False
    assert {
        record.ingestion_definition_id
        for record in store.list_ingestion_definitions(include_archived=True)
    } >= {archived_definition.ingestion_definition_id}
    try:
        store.create_execution_schedule(
            ExecutionScheduleCreate(
                schedule_id="archived-definition-schedule",
                target_kind="ingestion_definition",
                target_ref=archived_definition.ingestion_definition_id,
                cron_expression="*/5 * * * *",
                timezone="UTC",
                enabled=True,
                max_concurrency=1,
                next_due_at=FIXED_DUE_AT,
                created_at=FIXED_CREATED_AT,
            )
        )
    except ValueError as exc:
        assert "archived" in str(exc)
    else:
        raise AssertionError("Expected archived ingestion definitions to reject schedules")
    try:
        store.delete_ingestion_definition(archived_definition.ingestion_definition_id)
    except ValueError as exc:
        assert "schedules" in str(exc)
    else:
        raise AssertionError("Expected ingestion definition deletion to enforce schedules")

    restored_definition = store.set_ingestion_definition_archived_state(
        archived_definition.ingestion_definition_id,
        archived=False,
    )
    assert restored_definition.archived is False

    orphan_definition = store.create_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id="bank_partner_http_once",
            source_asset_id=restored_source_asset.source_asset_id,
            transport="filesystem",
            schedule_mode="watch-folder",
            source_path="/tmp/homelab/orphan-inbox",
            file_pattern="*.csv",
            processed_path="/tmp/homelab/orphan-processed",
            failed_path="/tmp/homelab/orphan-failed",
            poll_interval_seconds=15,
            enabled=False,
            source_name="folder-watch-orphan",
            created_at=FIXED_CREATED_AT,
        )
    )
    orphan_definition = store.set_ingestion_definition_archived_state(
        orphan_definition.ingestion_definition_id,
        archived=True,
    )
    store.delete_ingestion_definition(orphan_definition.ingestion_definition_id)
    try:
        store.get_ingestion_definition(orphan_definition.ingestion_definition_id)
    except KeyError:
        pass
    else:
        raise AssertionError(
            "Expected archived ingestion definition deletion to remove the record"
        )

    existing_schedule = store.get_execution_schedule("bank_partner_poll")
    updated_schedule = store.update_execution_schedule(
        ExecutionScheduleCreate(
            schedule_id=existing_schedule.schedule_id,
            target_kind=existing_schedule.target_kind,
            target_ref=existing_schedule.target_ref,
            cron_expression="0 * * * *",
            timezone="UTC",
            enabled=True,
            max_concurrency=2,
            next_due_at=existing_schedule.next_due_at,
            last_enqueued_at=existing_schedule.last_enqueued_at,
            created_at=existing_schedule.created_at,
        )
    )
    assert updated_schedule.cron_expression == "0 * * * *"
    assert updated_schedule.max_concurrency == 2

    manual_dispatch = store.create_schedule_dispatch(
        updated_schedule.schedule_id,
        enqueued_at=FIXED_DUE_AT,
    )
    assert manual_dispatch.schedule_id == updated_schedule.schedule_id
    assert manual_dispatch.status == "enqueued"
    assert (
        store.get_execution_schedule(updated_schedule.schedule_id).last_enqueued_at
        == FIXED_DUE_AT
    )

    second_dispatch = store.create_schedule_dispatch(
        updated_schedule.schedule_id,
        enqueued_at=FIXED_DUE_AT,
    )
    assert second_dispatch.dispatch_id != manual_dispatch.dispatch_id

    try:
        store.create_schedule_dispatch(
            updated_schedule.schedule_id,
            enqueued_at=FIXED_DUE_AT,
        )
    except ValueError as exc:
        assert "max_concurrency" in str(exc)
    else:
        raise AssertionError("Expected create_schedule_dispatch to enforce max_concurrency")

    disabled_schedule = store.update_execution_schedule(
        ExecutionScheduleCreate(
            schedule_id=updated_schedule.schedule_id,
            target_kind=updated_schedule.target_kind,
            target_ref=updated_schedule.target_ref,
            cron_expression=updated_schedule.cron_expression,
            timezone=updated_schedule.timezone,
            enabled=False,
            max_concurrency=updated_schedule.max_concurrency,
            next_due_at=updated_schedule.next_due_at,
            last_enqueued_at=updated_schedule.last_enqueued_at,
            created_at=updated_schedule.created_at,
        )
    )
    assert disabled_schedule.enabled is False
    try:
        store.create_schedule_dispatch(disabled_schedule.schedule_id)
    except ValueError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("Expected create_schedule_dispatch to reject disabled schedules")

    archived_schedule = store.set_execution_schedule_archived_state(
        disabled_schedule.schedule_id,
        archived=True,
    )
    assert archived_schedule.archived is True
    assert archived_schedule.enabled is False
    assert {
        record.schedule_id
        for record in store.list_execution_schedules(include_archived=True)
    } >= {archived_schedule.schedule_id}
    try:
        store.create_schedule_dispatch(archived_schedule.schedule_id)
    except ValueError as exc:
        assert "archived" in str(exc)
    else:
        raise AssertionError("Expected archived schedules to reject manual dispatch")
    try:
        store.delete_execution_schedule(archived_schedule.schedule_id)
    except ValueError as exc:
        assert "dispatch history" in str(exc)
    else:
        raise AssertionError("Expected schedule deletion to enforce dispatch history")

    orphan_schedule = store.create_execution_schedule(
        ExecutionScheduleCreate(
            schedule_id="bank_partner_manual_retry",
            target_kind="ingestion_definition",
            target_ref=restored_definition.ingestion_definition_id,
            cron_expression="0 6 * * *",
            timezone="UTC",
            enabled=False,
            max_concurrency=1,
            next_due_at=FIXED_DUE_AT,
            created_at=FIXED_CREATED_AT,
        )
    )
    orphan_schedule = store.set_execution_schedule_archived_state(
        orphan_schedule.schedule_id,
        archived=True,
    )
    store.delete_execution_schedule(orphan_schedule.schedule_id)
    try:
        store.get_execution_schedule(orphan_schedule.schedule_id)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected archived schedule deletion to remove the record")


def assert_schedule_dispatch_resilience_behaviour(store: ControlPlaneStore) -> None:
    seed_source_asset_graph(store)

    dispatch = store.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)[0]
    running = store.claim_schedule_dispatch(
        dispatch.dispatch_id,
        worker_id="worker-alpha",
        claimed_at=FIXED_DUE_AT,
        lease_seconds=30,
        worker_detail="worker-alpha-running",
    )
    renewed_at = FIXED_DUE_AT + timedelta(seconds=10)
    renewed = store.renew_schedule_dispatch_claim(
        dispatch.dispatch_id,
        worker_id="worker-alpha",
        claimed_at=renewed_at,
        lease_seconds=30,
        worker_detail="worker-alpha-renewed",
    )
    assert renewed.claimed_at == renewed_at
    assert renewed.claim_expires_at == renewed_at + timedelta(seconds=30)
    assert renewed.worker_detail == "worker-alpha-renewed"

    recovered_at = FIXED_DUE_AT + timedelta(minutes=10)
    recoveries = store.requeue_expired_schedule_dispatches(
        as_of=recovered_at,
        recovered_by_worker_id="worker-reaper",
    )
    assert len(recoveries) == 1
    recovery = recoveries[0]
    assert recovery.stale_dispatch.dispatch_id == running.dispatch_id
    assert recovery.stale_dispatch.status == "failed"
    assert recovery.stale_dispatch.completed_at == recovered_at
    assert "Dispatch claim expired at" in (recovery.stale_dispatch.failure_reason or "")
    assert recovery.replacement_dispatch is not None
    assert recovery.replacement_dispatch.schedule_id == running.schedule_id
    assert recovery.replacement_dispatch.status == "enqueued"
    assert recovery.replacement_dispatch.worker_detail is not None

    stored_stale = store.get_schedule_dispatch(running.dispatch_id)
    assert stored_stale.status == "failed"
    assert stored_stale.claim_expires_at is None

    claimed_replacement = store.claim_next_schedule_dispatch(
        worker_id="worker-beta",
        claimed_at=recovered_at,
        lease_seconds=60,
    )
    assert claimed_replacement is not None
    assert claimed_replacement.dispatch_id == recovery.replacement_dispatch.dispatch_id
    try:
        store.mark_schedule_dispatch_status(
            running.dispatch_id,
            status="completed",
            completed_at=recovered_at,
            expected_status="running",
            expected_worker_id="worker-alpha",
        )
    except ValueError as exc:
        assert "Schedule dispatch" in str(exc)
    else:
        raise AssertionError("Expected stale dispatch completion to be rejected.")


def assert_schedule_dispatch_claim_is_exclusive(store: ControlPlaneStore) -> None:
    seed_source_asset_graph(store)
    dispatch = store.enqueue_due_execution_schedules(as_of=FIXED_DUE_AT)[0]

    barrier = Barrier(3)
    lock = Lock()
    results: list[tuple[str, str | None]] = []
    errors: list[Exception] = []

    def claim(worker_id: str) -> None:
        barrier.wait()
        try:
            claimed = store.claim_next_schedule_dispatch(
                worker_id=worker_id,
                claimed_at=FIXED_DUE_AT,
                lease_seconds=60,
            )
        except Exception as exc:  # pragma: no cover - asserted below
            with lock:
                errors.append(exc)
            return
        with lock:
            results.append((worker_id, claimed.dispatch_id if claimed is not None else None))

    threads = [
        Thread(target=claim, args=("worker-alpha",)),
        Thread(target=claim, args=("worker-beta",)),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert errors == []
    claimed_results = [result for result in results if result[1] is not None]
    assert len(claimed_results) == 1
    assert claimed_results[0][1] == dispatch.dispatch_id
    stored_dispatch = store.get_schedule_dispatch(dispatch.dispatch_id)
    assert stored_dispatch.status == "running"
    assert stored_dispatch.claimed_by_worker_id == claimed_results[0][0]
