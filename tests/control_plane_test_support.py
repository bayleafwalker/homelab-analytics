from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
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
    AssetCatalogStore,
    AuthAuditEventCreate,
    AuthAuditStore,
    ConfigCatalogStore,
    ConfiguredCsvBindingStore,
    ContractCatalogStore,
    ControlPlaneAdminStore,
    ControlPlaneStore,
    ExecutionScheduleCreate,
    ExecutionStore,
    ExternalRegistryStore,
    IngestionCatalogStore,
    PolicyDefinitionCreate,
    PolicyDefinitionUpdate,
    PublicationAuditCreate,
    PublicationAuditStore,
    SnapshotStore,
    SourceLineageCreate,
    SourceLineageStore,
    SourceRegistryStore,
    WorkerHeartbeatCreate,
)
from packages.storage.external_registry_catalog import (
    ExtensionRegistryRevisionCreate,
    ExtensionRegistrySourceCreate,
)
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionDefinitionCreate,
    PublicationDefinitionCreate,
    ReferenceFactCreate,
    SourceAssetCreate,
    SourceSystemCreate,
    TransformationPackageCreate,
)

FIXED_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
FIXED_DUE_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
FIXED_AUDIT_AT = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def assert_control_plane_protocol_conformance(store: object) -> None:
    assert isinstance(store, SourceRegistryStore)
    assert isinstance(store, ContractCatalogStore)
    assert isinstance(store, AssetCatalogStore)
    assert isinstance(store, ExternalRegistryStore)
    assert isinstance(store, ExecutionStore)
    assert isinstance(store, SourceLineageStore)
    assert isinstance(store, PublicationAuditStore)
    assert isinstance(store, AuthAuditStore)
    assert isinstance(store, SnapshotStore)
    assert isinstance(store, ConfiguredCsvBindingStore)
    assert isinstance(store, IngestionCatalogStore)
    assert isinstance(store, ConfigCatalogStore)
    assert isinstance(store, ControlPlaneAdminStore)
    assert isinstance(store, ControlPlaneStore)


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


def seed_reference_fact_graph(store: ControlPlaneStore) -> dict[str, Any]:
    store.create_reference_fact(
        ReferenceFactCreate(
            fact_id="ref-fact-001",
            entity_type="loan_policy",
            entity_key="mortgage-001",
            attribute="interest_margin",
            value="0.75",
            effective_from=date(2025, 1, 1),
            source="operator",
            created_by="user-admin-001",
            note="Initial manual entry.",
            created_at=FIXED_CREATED_AT,
        )
    )
    second_fact = store.create_reference_fact(
        ReferenceFactCreate(
            fact_id="ref-fact-002",
            entity_type="loan_policy",
            entity_key="mortgage-001",
            attribute="interest_margin",
            value="0.80",
            effective_from=date(2026, 1, 1),
            source="operator",
            created_by="user-admin-001",
            note="Updated margin after repricing.",
            created_at=FIXED_CREATED_AT + timedelta(days=1),
        )
    )
    first_fact_closed = store.get_reference_fact("ref-fact-001")

    return {
        "first_fact": first_fact_closed,
        "second_fact": second_fact,
    }


def seed_extension_registry_graph(store: ControlPlaneStore) -> dict[str, Any]:
    source = store.create_extension_registry_source(
        ExtensionRegistrySourceCreate(
            extension_registry_source_id="household_custom_modules",
            name="Household Custom Modules",
            source_kind="path",
            location="/srv/homelab/custom-modules",
            subdirectory="extensions",
            enabled=True,
            created_at=FIXED_CREATED_AT,
        )
    )
    revision = store.create_extension_registry_revision(
        ExtensionRegistryRevisionCreate(
            extension_registry_revision_id="extrev-001",
            extension_registry_source_id=source.extension_registry_source_id,
            resolved_ref="/srv/homelab/custom-modules/extensions",
            runtime_path="/srv/homelab/custom-modules/extensions",
            manifest_path="/srv/homelab/custom-modules/extensions/homelab-analytics.registry.json",
            manifest_digest="manifest-digest-001",
            manifest_version=1,
            content_fingerprint="fingerprint-001",
            import_paths=(".",),
            extension_modules=("household.extensions",),
            function_modules=("household.functions",),
            sync_status="validated",
            created_at=FIXED_CREATED_AT,
        )
    )
    activation = store.activate_extension_registry_revision(
        extension_registry_source_id=source.extension_registry_source_id,
        extension_registry_revision_id=revision.extension_registry_revision_id,
        activated_at=FIXED_CREATED_AT,
    )
    return {
        "extension_registry_source": source,
        "extension_registry_revision": revision,
        "extension_registry_activation": activation,
    }


def assert_control_plane_store_round_trip(store: ControlPlaneStore) -> None:
    seeded = seed_source_asset_graph(store)
    registry_seeded = seed_extension_registry_graph(store)
    reference_seeded = seed_reference_fact_graph(store)

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
    assert (
        store.get_extension_registry_source(
            registry_seeded["extension_registry_source"].extension_registry_source_id
        )
        == registry_seeded["extension_registry_source"]
    )
    assert (
        store.get_extension_registry_revision(
            registry_seeded["extension_registry_revision"].extension_registry_revision_id
        )
        == registry_seeded["extension_registry_revision"]
    )
    assert (
        store.get_extension_registry_activation(
            registry_seeded["extension_registry_source"].extension_registry_source_id
        )
        == registry_seeded["extension_registry_activation"]
    )
    assert (
        store.get_reference_fact(reference_seeded["first_fact"].fact_id)
        == reference_seeded["first_fact"]
    )
    assert (
        store.get_reference_fact(reference_seeded["second_fact"].fact_id)
        == reference_seeded["second_fact"]
    )
    assert [fact.fact_id for fact in store.list_reference_facts(include_closed=False)] == [
        "ref-fact-002"
    ]
    assert [
        record.schedule_id for record in store.list_execution_schedules(enabled_only=True)
    ] == ["bank_partner_poll"]

    snapshot = store.export_snapshot()
    assert any(
        record.source_asset_id == seeded["source_asset"].source_asset_id
        for record in snapshot.source_assets
    )
    assert any(
        record.extension_registry_source_id
        == registry_seeded["extension_registry_source"].extension_registry_source_id
        for record in snapshot.extension_registry_sources
    )
    assert any(
        record.extension_registry_revision_id
        == registry_seeded["extension_registry_revision"].extension_registry_revision_id
        for record in snapshot.extension_registry_revisions
    )
    assert any(
        record.extension_registry_source_id
        == registry_seeded["extension_registry_activation"].extension_registry_source_id
        for record in snapshot.extension_registry_activations
    )
    assert any(record.fact_id == "ref-fact-001" for record in snapshot.reference_facts)
    assert any(record.fact_id == "ref-fact-002" for record in snapshot.reference_facts)
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

    custom_transformation_package = store.create_transformation_package(
        TransformationPackageCreate(
            transformation_package_id="custom_household_costs",
            name="Custom household costs",
            handler_key="custom.household_costs",
            version=1,
            description="Custom household cost transforms.",
            created_at=FIXED_CREATED_AT,
        )
    )
    updated_transformation_package = store.update_transformation_package(
        TransformationPackageCreate(
            transformation_package_id=custom_transformation_package.transformation_package_id,
            name="Custom household costs v2",
            handler_key="custom.household_costs.v2",
            version=2,
            description="Updated custom household cost transforms.",
            archived=custom_transformation_package.archived,
            created_at=custom_transformation_package.created_at,
        )
    )
    assert updated_transformation_package.version == 2
    assert updated_transformation_package.archived is False

    custom_publication_definition = store.create_publication_definition(
        PublicationDefinitionCreate(
            publication_definition_id="custom_household_costs_monthly",
            transformation_package_id=updated_transformation_package.transformation_package_id,
            publication_key="mart_monthly_cashflow",
            name="Custom household costs monthly",
            description="Custom household costs publication.",
            created_at=FIXED_CREATED_AT,
        )
    )
    updated_publication_definition = store.update_publication_definition(
        PublicationDefinitionCreate(
            publication_definition_id=(
                custom_publication_definition.publication_definition_id
            ),
            transformation_package_id=(
                custom_publication_definition.transformation_package_id
            ),
            publication_key=custom_publication_definition.publication_key,
            name="Custom household costs monthly v2",
            description="Updated custom household costs publication.",
            archived=custom_publication_definition.archived,
            created_at=custom_publication_definition.created_at,
        )
    )
    assert updated_publication_definition.name == "Custom household costs monthly v2"
    assert updated_publication_definition.archived is False

    try:
        store.set_transformation_package_archived_state(
            updated_transformation_package.transformation_package_id,
            archived=True,
        )
    except ValueError as exc:
        assert "publication definitions" in str(exc)
    else:
        raise AssertionError(
            "Expected active publication definitions to block transformation package archival"
        )

    archived_publication_definition = store.set_publication_definition_archived_state(
        updated_publication_definition.publication_definition_id,
        archived=True,
    )
    assert archived_publication_definition.archived is True
    assert (
        store.list_publication_definitions(
            transformation_package_id=updated_transformation_package.transformation_package_id
        )
        == []
    )
    assert {
        record.publication_definition_id
        for record in store.list_publication_definitions(include_archived=True)
    } >= {archived_publication_definition.publication_definition_id}

    archived_transformation_package = store.set_transformation_package_archived_state(
        updated_transformation_package.transformation_package_id,
        archived=True,
    )
    assert archived_transformation_package.archived is True
    assert {
        record.transformation_package_id
        for record in store.list_transformation_packages()
    }.isdisjoint({archived_transformation_package.transformation_package_id})
    assert {
        record.transformation_package_id
        for record in store.list_transformation_packages(include_archived=True)
    } >= {archived_transformation_package.transformation_package_id}

    try:
        store.set_publication_definition_archived_state(
            archived_publication_definition.publication_definition_id,
            archived=False,
        )
    except ValueError as exc:
        assert "archived" in str(exc)
    else:
        raise AssertionError(
            "Expected archived transformation packages to block publication restoration"
        )

    restored_transformation_package = store.set_transformation_package_archived_state(
        archived_transformation_package.transformation_package_id,
        archived=False,
    )
    assert restored_transformation_package.archived is False
    restored_publication_definition = store.set_publication_definition_archived_state(
        archived_publication_definition.publication_definition_id,
        archived=False,
    )
    assert restored_publication_definition.archived is False

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


def assert_policy_registry_behaviour(store: ControlPlaneStore) -> None:
    """Full CRUD round-trip for the policy definition registry."""
    created = store.create_policy_definition(
        PolicyDefinitionCreate(
            policy_id="policy-contract-1",
            display_name="Net cashflow below zero",
            policy_kind="threshold",
            rule_schema_version="1.0",
            rule_document='{"rule_kind": "publication_value_comparison"}',
            description="Contract-test policy",
            creator="contract-suite",
            source_kind="operator",
            created_at=FIXED_CREATED_AT,
            updated_at=FIXED_CREATED_AT,
        )
    )
    assert created.policy_id == "policy-contract-1"
    assert created.enabled is True
    assert created.created_at == FIXED_CREATED_AT

    fetched = store.get_policy_definition("policy-contract-1")
    assert fetched == created

    listed = store.list_policy_definitions(source_kind="operator")
    assert "policy-contract-1" in [record.policy_id for record in listed]

    updated = store.update_policy_definition(
        "policy-contract-1",
        PolicyDefinitionUpdate(
            display_name="Net cashflow below zero (renamed)",
            enabled=False,
            updated_at=FIXED_AUDIT_AT,
        ),
    )
    assert updated.display_name == "Net cashflow below zero (renamed)"
    assert updated.enabled is False
    assert updated.updated_at == FIXED_AUDIT_AT
    assert store.list_policy_definitions(enabled_only=True) == [
        record
        for record in store.list_policy_definitions(enabled_only=True)
        if record.policy_id != "policy-contract-1"
    ]

    store.delete_policy_definition("policy-contract-1")
    try:
        store.get_policy_definition("policy-contract-1")
    except KeyError:
        pass
    else:  # pragma: no cover - defends the contract
        raise AssertionError("expected KeyError after delete")

    for operation in (
        lambda: store.get_policy_definition("missing-policy"),
        lambda: store.update_policy_definition(
            "missing-policy", PolicyDefinitionUpdate(display_name="x")
        ),
        lambda: store.delete_policy_definition("missing-policy"),
    ):
        try:
            operation()
        except KeyError:
            continue
        raise AssertionError("expected KeyError for unknown policy id")


def assert_decision_ledger_behaviour(store: Any) -> None:
    """Append-only decision ledger: create/get/list records and follow-ups."""
    from decimal import Decimal

    from packages.storage.decision_ledger import (
        DecisionActor,
        DecisionFollowUpCreate,
        DecisionLedgerStore,
        DecisionRecordCreate,
    )

    assert isinstance(store, DecisionLedgerStore)
    actor = DecisionActor(
        actor="operator-a",
        actor_role="operator",
        actor_auth_provider="local",
        actor_authenticated=True,
    )
    created_at = datetime(2026, 2, 3, 9, 30, tzinfo=UTC)
    record = store.create_decision_record(
        DecisionRecordCreate(
            decision_id="dec-contract-1",
            decision_key="kotiakku_battery_plan_review",
            decision_version="1.0.0",
            subject_publication_key="mart_battery_plan_outcome",
            subject_schema_version="1.0.0",
            subject_period="2026-01",
            subject_row_ref="bpo_contract",
            subject_verdict="insufficient_evidence",
            lineage_reference='{"source_run_ids":["run-1"]}',
            evidence_snapshot='{"outcome":{}}',
            outcome="defer_pending_evidence",
            is_non_decision=True,
            rationale="Coverage incomplete.",
            evidence_gaps_acknowledged='["measurement_window_coverage_incomplete"]',
            uncertainty=None,
            actor=actor,
            follow_up_due_on=date(2026, 3, 20),
            created_at=created_at,
        )
    )
    assert record.decision_id == "dec-contract-1"
    assert record.is_non_decision is True
    assert record.actor == actor
    assert record.follow_up_due_on == date(2026, 3, 20)
    assert record.created_at == created_at
    assert record.created_at.tzinfo is not None
    assert store.get_decision_record("dec-contract-1") == record
    assert store.list_decision_records(decision_key="kotiakku_battery_plan_review") == [record]
    assert store.list_decision_records(subject_period="2025-12") == []

    follow_up = store.add_decision_follow_up(
        DecisionFollowUpCreate(
            follow_up_id="fup-contract-1",
            decision_id="dec-contract-1",
            observed_at=datetime(2026, 3, 21, 8, tzinfo=UTC),
            observation_period="2026-02",
            realized_result="February bill matched the prior contract.",
            realized_value_eur=Decimal("12.5000"),
            realized_value_status="observed",
            evidence_effect="preserved_non_decision",
            notes=None,
            actor=actor,
            created_at=datetime(2026, 3, 21, 8, 5, tzinfo=UTC),
        )
    )
    assert follow_up.realized_value_eur == Decimal("12.5")
    assert follow_up.observed_at == datetime(2026, 3, 21, 8, tzinfo=UTC)
    assert store.list_decision_follow_ups("dec-contract-1") == [follow_up]
    try:
        store.get_decision_record("missing")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown decision")
    try:
        store.add_decision_follow_up(
            DecisionFollowUpCreate(
                follow_up_id="fup-orphan",
                decision_id="missing",
                observed_at=datetime(2026, 3, 21, tzinfo=UTC),
                observation_period=None,
                realized_result="x",
                realized_value_eur=None,
                realized_value_status=None,
                evidence_effect="inconclusive",
                notes=None,
                actor=actor,
            )
        )
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for follow-up on unknown decision")
    _assert_decision_commitment_lifecycle(store, actor)


def _assert_decision_commitment_lifecycle(store: Any, actor: Any) -> None:
    """Commitment terms persist with the record; lifecycle events dedupe."""
    from packages.storage.decision_ledger import (
        DecisionCommitment,
        DecisionLifecycleEventCreate,
        DecisionRecordCreate,
    )

    created_at = datetime(2026, 2, 4, 9, 30, tzinfo=UTC)
    commitment = DecisionCommitment(
        decision_id="dec-contract-2",
        purpose="Keep the plan while economics justify it.",
        owner_role="operator",
        owner_principal=None,
        owner_verified=True,
        baseline='{"values":{}}',
        success_measure='{"key":"m"}',
        observation_window_start=date(2026, 3, 1),
        observation_window_end=date(2026, 3, 31),
        next_review_due_on=date(2026, 4, 14),
        review_cadence_days=30,
        review_triggers="[]",
        stop_conditions='[{"key":"purpose_expired"}]',
        stop_conditions_met="[]",
        evidence_fingerprint="evf_contract",
        evidence_components='{"source_windows":{}}',
        created_at=created_at,
    )
    record = store.create_decision_record(
        DecisionRecordCreate(
            decision_id="dec-contract-2",
            decision_key="kotiakku_battery_plan_review",
            decision_version="1.1.0",
            subject_publication_key="mart_battery_plan_outcome",
            subject_schema_version="1.0.0",
            subject_period="2026-01",
            subject_row_ref="bpo_contract_2",
            subject_verdict="no_benefit_estimated",
            lineage_reference="{}",
            evidence_snapshot="{}",
            outcome="keep_current_plan",
            is_non_decision=False,
            rationale="Estimate below cost but within tolerance.",
            evidence_gaps_acknowledged="[]",
            uncertainty=None,
            actor=actor,
            follow_up_due_on=date(2026, 4, 14),
            commitment=commitment,
            created_at=created_at,
        )
    )
    assert record.commitment == commitment
    assert store.get_decision_record("dec-contract-2").commitment == commitment
    legacy = store.get_decision_record("dec-contract-1")
    assert legacy.commitment is None

    event = DecisionLifecycleEventCreate(
        event_id="dle-contract-1",
        decision_id="dec-contract-2",
        event_kind="evidence_superseded",
        dedupe_key="dec-contract-2:evidence_superseded:evf_new",
        reason_code="evidence_superseded",
        reason="Tariff revised.",
        details='{"superseding_row_ref":"bpo_new"}',
        actor=actor,
        occurred_at=datetime(2026, 2, 10, tzinfo=UTC),
        created_at=datetime(2026, 2, 10, tzinfo=UTC),
    )
    stored, created = store.append_decision_lifecycle_event(event)
    assert created is True
    assert stored.event_id == "dle-contract-1"
    assert stored.occurred_at == datetime(2026, 2, 10, tzinfo=UTC)
    duplicate, created_again = store.append_decision_lifecycle_event(
        DecisionLifecycleEventCreate(
            **{**event.__dict__, "event_id": "dle-contract-dup"}
        )
    )
    assert created_again is False
    assert duplicate.event_id == "dle-contract-1"
    assert store.list_decision_lifecycle_events("dec-contract-2") == [stored]
    assert store.list_decision_lifecycle_events("dec-contract-1") == []
    try:
        store.append_decision_lifecycle_event(
            DecisionLifecycleEventCreate(
                **{**event.__dict__, "event_id": "dle-orphan", "decision_id": "missing",
                   "dedupe_key": "missing:x"}
            )
        )
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for an event on an unknown decision")


def assert_action_proposal_store_behaviour(store: Any) -> None:
    """Durable proposal queue: CAS transitions, idempotency, append-only history.

    Runs against every ``ActionProposalStore`` (in-memory, SQLite, Postgres)
    through the registry, so all backends enforce the same lifecycle.
    """
    from packages.platform.action_proposals import (
        ActionProposal,
        ActionProposalRegistry,
        ActionProposalStore,
        ProposalConflictError,
        ProposalHistoryEvent,
        ProposalProvenance,
        ProposalTransitionError,
    )

    assert isinstance(store, ActionProposalStore)
    registry = ActionProposalRegistry(store=store)

    drafted = registry.register(
        policy_id="mcp:propose_action",
        policy_name="Lower office heating",
        verdict="notify",
        value="19.5",
        notification_id=None,
        adapter="platform",
        source_kind="agent",
        created_by="mcp-agent",
        metadata={"room": "office", "nested": {"a": 1}},
        provenance=ProposalProvenance(
            publication_keys=["monthly_cashflow", "energy_usage"],
            confidence_verdict_at_draft="degraded",
            freshness_state_at_draft="due_soon",
            assessed_at="2026-10-01T08:00:00+00:00",
            trust_source="server_stamped",
        ),
        idempotency_key="contract-key-0001",
        actor_auth_provider="service_token",
    )
    assert drafted.action_id == "agent_contract-key-0001"
    assert drafted.status == "pending"
    assert drafted.idempotency_key == "contract-key-0001"
    assert drafted.metadata == {"room": "office", "nested": {"a": 1}}
    assert drafted.provenance is not None
    assert drafted.provenance.publication_keys == ["monthly_cashflow", "energy_usage"]
    assert drafted.provenance.confidence_verdict_at_draft == "degraded"
    assert drafted.provenance.trust_source == "server_stamped"
    assert datetime.fromisoformat(drafted.created_at).tzinfo is not None
    assert [(e.kind, e.actor, e.actor_auth_provider) for e in drafted.history] == [
        ("drafted", "mcp-agent", "service_token")
    ]

    # Replays of the key refresh the pending proposal, never duplicate it.
    replay = registry.register(
        policy_id="mcp:propose_action",
        policy_name="Lower office heating",
        verdict="notify",
        value="19.0",
        notification_id=None,
        adapter="platform",
        source_kind="agent",
        created_by="mcp-agent",
        idempotency_key="contract-key-0001",
    )
    assert replay.action_id == drafted.action_id
    assert replay.value == "19.0"
    assert replay.created_at == drafted.created_at
    assert [e.kind for e in replay.history] == ["drafted", "refreshed"]
    assert len(registry.list_all()) == 1

    # Another drafter cannot reuse the key.
    try:
        registry.register(
            policy_id="x",
            policy_name="x",
            verdict="notify",
            value=None,
            notification_id=None,
            created_by="someone-else",
            idempotency_key="contract-key-0001",
        )
    except ProposalConflictError:
        pass
    else:
        raise AssertionError("expected ProposalConflictError for a foreign key replay")

    # Direct inserts collide on the action id and on the idempotency key.
    for duplicate in (
        ActionProposal(
            action_id=drafted.action_id,
            policy_id="x",
            policy_name="x",
            verdict="notify",
            value=None,
            notification_id="n",
        ),
        ActionProposal(
            action_id="other-id",
            policy_id="x",
            policy_name="x",
            verdict="notify",
            value=None,
            notification_id="n",
            idempotency_key="contract-key-0001",
        ),
    ):
        try:
            store.insert_action_proposal(duplicate)
        except ProposalConflictError:
            pass
        else:
            raise AssertionError("expected ProposalConflictError on duplicate insert")

    approved = registry.approve(
        drafted.action_id,
        resolved_by="operator-a",
        reason=" checked ",
        actor_auth_provider="oidc",
    )
    assert approved.status == "approved"
    assert approved.approved_at is not None
    assert approved.resolved_by == "operator-a"
    assert approved.resolution_reason == "checked"
    assert approved.history[-1] == ProposalHistoryEvent(
        kind="approved",
        at=approved.approved_at,
        actor="operator-a",
        reason="checked",
        actor_auth_provider="oidc",
    )

    # Second resolution is refused and leaves the decision intact.
    try:
        registry.dismiss(drafted.action_id, resolved_by="operator-b")
    except ProposalTransitionError as exc:
        assert exc.status == "approved"
    else:
        raise AssertionError("expected ProposalTransitionError on second resolution")
    # A stale compare-and-set writes nothing, not even an event.
    assert (
        store.update_action_proposal(
            approved,
            expected_status="pending",
            event=ProposalHistoryEvent(kind="dismissed", at=approved.created_at),
        )
        is False
    )

    # A key replay after resolution returns the decision unchanged.
    after = registry.register(
        policy_id="mcp:propose_action",
        policy_name="Lower office heating",
        verdict="notify",
        value="18.0",
        notification_id=None,
        created_by="mcp-agent",
        idempotency_key="contract-key-0001",
    )
    assert after == approved

    # Re-registering a resolved action id is refused unless reopening.
    gate = registry.register(
        policy_id="policy-1",
        policy_name="Gate",
        verdict="approval_required",
        value="on",
        notification_id="ha-gate-1",
        action_id="ha-gate-1",
        created_by="ha_action_dispatcher",
    )
    registry.dismiss(gate.action_id, resolved_by="ha_action_dispatcher", reason="cleared")
    try:
        registry.register(
            policy_id="policy-1",
            policy_name="Gate",
            verdict="approval_required",
            value="on",
            notification_id="ha-gate-1",
            action_id="ha-gate-1",
        )
    except ProposalTransitionError:
        pass
    else:
        raise AssertionError("expected ProposalTransitionError without reopen_resolved")
    reopened = registry.register(
        policy_id="policy-1",
        policy_name="Gate",
        verdict="approval_required",
        value="on",
        notification_id="ha-gate-1",
        action_id="ha-gate-1",
        created_by="ha_action_dispatcher",
        reopen_resolved=True,
    )
    assert reopened.status == "pending"
    assert reopened.resolved_by is None and reopened.dismissed_at is None
    assert [e.kind for e in reopened.history] == ["drafted", "dismissed", "reopened"]

    listed = registry.list_all()
    assert [p.action_id for p in listed] == ["ha-gate-1", drafted.action_id]
    assert registry.get_status() == {
        "tracked": 2,
        "pending": 1,
        "approved": 1,
        "dismissed": 0,
    }
    assert store.get_action_proposal("missing") is None
    assert store.find_action_proposal_by_idempotency_key("missing-key") is None
    try:
        registry.approve("missing")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown proposal")


def assert_action_proposal_resolution_is_exclusive(store: Any) -> None:
    """Concurrent resolvers on one proposal: exactly one wins."""
    from packages.platform.action_proposals import (
        ActionProposalRegistry,
        ProposalTransitionError,
    )

    registry = ActionProposalRegistry(store=store)
    proposal = registry.register(
        policy_id="race",
        policy_name="Race",
        verdict="notify",
        value=None,
        notification_id=None,
        adapter="platform",
        source_kind="agent",
        created_by="agent",
    )
    workers = 6
    barrier = Barrier(workers)
    outcomes: list[str] = []
    outcome_lock = Lock()

    def resolve(index: int) -> None:
        barrier.wait()
        try:
            if index % 2:
                registry.approve(proposal.action_id, resolved_by=f"op-{index}")
            else:
                registry.dismiss(proposal.action_id, resolved_by=f"op-{index}")
            result = "won"
        except ProposalTransitionError:
            result = "conflict"
        with outcome_lock:
            outcomes.append(result)

    threads = [Thread(target=resolve, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["conflict"] * (workers - 1) + ["won"]
    stored = registry.get(proposal.action_id)
    assert stored is not None
    assert [e.kind for e in stored.history].count("drafted") == 1
    assert len(stored.history) == 2


def assert_action_proposal_changes_feed(store: Any) -> None:
    """The changes feed serves every history event once, in commit order.

    Relative to the feed's current end, so it holds on a shared database.
    Concurrent writers draft, refresh and resolve; paging the feed with a
    small limit must then return each new event exactly once, with strictly
    increasing positions and each proposal's events in sequence order.
    """
    from packages.platform.action_proposals import (
        ActionProposalRegistry,
        ProposalTransitionError,
    )

    registry = ActionProposalRegistry(store=store)

    def feed_end() -> int:
        position = 0
        while True:
            page = registry.list_changes(after_position=position, limit=200)
            if not page:
                return position
            position = page[-1].position

    start = feed_end()
    workers = 6
    barrier = Barrier(workers)
    created: list[str] = []
    created_lock = Lock()

    def write(index: int) -> None:
        barrier.wait()
        proposal = registry.register(
            policy_id=f"feed-{index}",
            policy_name=f"Feed {index}",
            verdict="notify",
            value="1",
            notification_id=None,
            adapter="platform",
            source_kind="agent",
            created_by="agent",
        )
        registry.register(
            policy_id=f"feed-{index}",
            policy_name=f"Feed {index}",
            verdict="notify",
            value="2",
            notification_id=None,
            action_id=proposal.action_id,
            adapter="platform",
            source_kind="agent",
            created_by="agent",
        )
        try:
            if index % 2:
                registry.approve(proposal.action_id, resolved_by="operator")
            else:
                registry.dismiss(proposal.action_id, resolved_by="operator")
        except ProposalTransitionError:
            pass
        with created_lock:
            created.append(proposal.action_id)

    threads = [Thread(target=write, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    seen = []
    position = start
    while True:
        page = registry.list_changes(after_position=position, limit=4)
        if not page:
            break
        assert len(page) <= 4
        seen.extend(page)
        position = page[-1].position
    positions = [item.position for item in seen]
    assert positions == sorted(set(positions))
    assert len({item.event_id for item in seen}) == len(seen)
    assert {item.action_id for item in seen} == set(created)
    for action_id in created:
        stored = registry.get(action_id)
        assert stored is not None
        mine = [item for item in seen if item.action_id == action_id]
        assert [item.sequence for item in mine] == list(range(1, len(stored.history) + 1))
        assert [item.event.kind for item in mine] == [event.kind for event in stored.history]
        assert [item.event.kind for item in mine] == ["drafted", "refreshed", stored.status]
        assert all(item.adapter == "platform" and item.source_kind == "agent" for item in mine)
        narrowed = registry.list_changes(after_position=start, limit=50, action_id=action_id)
        assert [item.event_id for item in narrowed] == [item.event_id for item in mine]
    assert registry.list_changes(after_position=position, limit=10) == []
