from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from packages.pipelines.csv_validation import ColumnType
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    ControlPlaneStore,
    ExecutionScheduleCreate,
    PublicationAuditCreate,
    SourceLineageCreate,
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
    assert (
        store.get_execution_schedule("enabled-schedule").last_enqueued_at == due_at
    )

    # Even when the schedule is due again, an active dispatch blocks a duplicate enqueue.
    assert store.enqueue_due_execution_schedules(as_of=blocked_as_of) == []
    assert store.list_schedule_dispatches(schedule_id="disabled-schedule") == []

    completed = store.mark_schedule_dispatch_status(
        first_dispatches[0].dispatch_id,
        status="completed",
        completed_at=blocked_as_of,
    )
    assert completed.status == "completed"

    second_dispatches = store.enqueue_due_execution_schedules(as_of=blocked_as_of)
    assert [dispatch.schedule_id for dispatch in second_dispatches] == ["enabled-schedule"]
    assert (
        store.get_execution_schedule("enabled-schedule").next_due_at
        == datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    )
    assert [
        dispatch.dispatch_id
        for dispatch in store.list_schedule_dispatches(
            schedule_id="enabled-schedule",
            status="completed",
        )
    ] == [first_dispatches[0].dispatch_id]


def assert_control_plane_store_update_behaviour(store: ControlPlaneStore) -> None:
    seeded = seed_source_asset_graph(store)

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
