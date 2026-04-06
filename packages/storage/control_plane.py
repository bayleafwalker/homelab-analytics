from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from packages.storage.auth_store import AuthStore

if TYPE_CHECKING:
    from packages.pipelines.promotion_registry import PromotionHandlerRegistry
    from packages.shared.extensions import ExtensionRegistry
    from packages.storage.auth_store import LocalUserRecord, ServiceTokenRecord
    from packages.storage.external_registry_catalog import (
        ExtensionRegistryActivationRecord,
        ExtensionRegistryRevisionCreate,
        ExtensionRegistryRevisionRecord,
        ExtensionRegistrySourceCreate,
        ExtensionRegistrySourceRecord,
    )
    from packages.storage.ingestion_catalog import (
        ColumnMappingCreate,
        ColumnMappingRecord,
        DatasetContractConfigCreate,
        DatasetContractConfigRecord,
        IngestionDefinitionCreate,
        IngestionDefinitionRecord,
        PublicationDefinitionCreate,
        PublicationDefinitionRecord,
        ReferenceFactCreate,
        ReferenceFactRecord,
        SourceAssetCreate,
        SourceAssetRecord,
        SourceFreshnessConfigCreate,
        SourceFreshnessConfigRecord,
        SourceSystemCreate,
        SourceSystemRecord,
        TransformationPackageCreate,
        TransformationPackageRecord,
    )


@dataclass(frozen=True)
class ExecutionScheduleCreate:
    schedule_id: str
    target_kind: str
    target_ref: str
    cron_expression: str
    timezone: str = "UTC"
    enabled: bool = True
    archived: bool = False
    max_concurrency: int = 1
    next_due_at: datetime | None = None
    last_enqueued_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ExecutionScheduleRecord:
    schedule_id: str
    target_kind: str
    target_ref: str
    cron_expression: str
    timezone: str
    enabled: bool
    archived: bool
    max_concurrency: int
    next_due_at: datetime | None
    last_enqueued_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ScheduleDispatchRecord:
    dispatch_id: str
    schedule_id: str
    target_kind: str
    target_ref: str
    enqueued_at: datetime
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    run_ids: tuple[str, ...] = ()
    failure_reason: str | None = None
    worker_detail: str | None = None
    claimed_by_worker_id: str | None = None
    claimed_at: datetime | None = None
    claim_expires_at: datetime | None = None


@dataclass(frozen=True)
class ScheduleDispatchRecoveryRecord:
    stale_dispatch: ScheduleDispatchRecord
    replacement_dispatch: ScheduleDispatchRecord | None
    recovered_at: datetime
    recovered_by_worker_id: str | None = None


@dataclass(frozen=True)
class WorkerHeartbeatCreate:
    worker_id: str
    status: str
    active_dispatch_id: str | None = None
    detail: str | None = None
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class WorkerHeartbeatRecord:
    worker_id: str
    status: str
    active_dispatch_id: str | None
    detail: str | None
    observed_at: datetime


@dataclass(frozen=True)
class SourceLineageCreate:
    lineage_id: str
    input_run_id: str | None
    target_layer: str
    target_name: str
    target_kind: str
    row_count: int | None = None
    source_system: str | None = None
    source_run_id: str | None = None
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SourceLineageRecord:
    lineage_id: str
    input_run_id: str | None
    target_layer: str
    target_name: str
    target_kind: str
    row_count: int | None
    source_system: str | None
    source_run_id: str | None
    recorded_at: datetime


@dataclass(frozen=True)
class PublicationAuditCreate:
    publication_audit_id: str
    run_id: str | None
    publication_key: str
    relation_name: str
    status: str
    published_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PublicationAuditRecord:
    publication_audit_id: str
    run_id: str | None
    publication_key: str
    relation_name: str
    status: str
    published_at: datetime


@dataclass(frozen=True)
class PublicationConfidenceSnapshotCreate:
    snapshot_id: str
    publication_key: str
    assessed_at: datetime
    freshness_state: str
    completeness_pct: int
    confidence_verdict: str
    quality_flags: dict | None = None
    contributing_run_ids: tuple[str, ...] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PublicationConfidenceSnapshotRecord:
    snapshot_id: str
    publication_key: str
    assessed_at: datetime
    freshness_state: str
    completeness_pct: int
    confidence_verdict: str
    quality_flags: dict | None
    contributing_run_ids: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True)
class AuthAuditEventCreate:
    event_id: str
    event_type: str
    success: bool
    actor_user_id: str | None = None
    actor_username: str | None = None
    subject_user_id: str | None = None
    subject_username: str | None = None
    remote_addr: str | None = None
    user_agent: str | None = None
    detail: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class AuthAuditEventRecord:
    event_id: str
    event_type: str
    success: bool
    actor_user_id: str | None
    actor_username: str | None
    subject_user_id: str | None
    subject_username: str | None
    remote_addr: str | None
    user_agent: str | None
    detail: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class ControlPlaneSnapshot:
    source_systems: tuple["SourceSystemRecord", ...]
    dataset_contracts: tuple["DatasetContractConfigRecord", ...]
    column_mappings: tuple["ColumnMappingRecord", ...]
    transformation_packages: tuple["TransformationPackageRecord", ...]
    publication_definitions: tuple["PublicationDefinitionRecord", ...]
    source_assets: tuple["SourceAssetRecord", ...]
    ingestion_definitions: tuple["IngestionDefinitionRecord", ...]
    source_freshness_configs: tuple["SourceFreshnessConfigRecord", ...] = ()
    reference_facts: tuple["ReferenceFactRecord", ...] = ()
    extension_registry_sources: tuple["ExtensionRegistrySourceRecord", ...] = ()
    extension_registry_revisions: tuple["ExtensionRegistryRevisionRecord", ...] = ()
    extension_registry_activations: tuple["ExtensionRegistryActivationRecord", ...] = ()
    execution_schedules: tuple[ExecutionScheduleRecord, ...] = ()
    source_lineage: tuple[SourceLineageRecord, ...] = ()
    publication_audit: tuple[PublicationAuditRecord, ...] = ()
    auth_audit_events: tuple[AuthAuditEventRecord, ...] = ()
    local_users: tuple["LocalUserRecord", ...] = ()
    service_tokens: tuple["ServiceTokenRecord", ...] = ()


@runtime_checkable
class SourceRegistryStore(Protocol):
    def create_source_system(self, source_system: "SourceSystemCreate") -> "SourceSystemRecord":
        ...

    def update_source_system(self, source_system: "SourceSystemCreate") -> "SourceSystemRecord":
        ...

    def get_source_system(self, source_system_id: str) -> "SourceSystemRecord":
        ...

    def list_source_systems(self) -> list["SourceSystemRecord"]:
        ...


@runtime_checkable
class ContractCatalogStore(Protocol):
    def create_dataset_contract(
        self, dataset_contract: "DatasetContractConfigCreate"
    ) -> "DatasetContractConfigRecord":
        ...

    def get_dataset_contract(self, dataset_contract_id: str) -> "DatasetContractConfigRecord":
        ...

    def list_dataset_contracts(
        self,
        *,
        include_archived: bool = False,
    ) -> list["DatasetContractConfigRecord"]:
        ...

    def set_dataset_contract_archived_state(
        self,
        dataset_contract_id: str,
        *,
        archived: bool,
    ) -> "DatasetContractConfigRecord":
        ...

    def create_column_mapping(
        self, column_mapping: "ColumnMappingCreate"
    ) -> "ColumnMappingRecord":
        ...

    def get_column_mapping(self, column_mapping_id: str) -> "ColumnMappingRecord":
        ...

    def list_column_mappings(
        self,
        *,
        include_archived: bool = False,
    ) -> list["ColumnMappingRecord"]:
        ...

    def set_column_mapping_archived_state(
        self,
        column_mapping_id: str,
        *,
        archived: bool,
    ) -> "ColumnMappingRecord":
        ...

    def create_transformation_package(
        self,
        transformation_package: "TransformationPackageCreate",
        *,
        extension_registry: "ExtensionRegistry | None" = None,
        promotion_handler_registry: "PromotionHandlerRegistry | None" = None,
    ) -> "TransformationPackageRecord":
        ...

    def update_transformation_package(
        self,
        transformation_package: "TransformationPackageCreate",
        *,
        extension_registry: "ExtensionRegistry | None" = None,
        promotion_handler_registry: "PromotionHandlerRegistry | None" = None,
    ) -> "TransformationPackageRecord":
        ...

    def get_transformation_package(
        self, transformation_package_id: str
    ) -> "TransformationPackageRecord":
        ...

    def list_transformation_packages(
        self,
        *,
        include_archived: bool = False,
    ) -> list["TransformationPackageRecord"]:
        ...

    def set_transformation_package_archived_state(
        self,
        transformation_package_id: str,
        *,
        archived: bool,
    ) -> "TransformationPackageRecord":
        ...

    def create_publication_definition(
        self,
        publication_definition: "PublicationDefinitionCreate",
        *,
        extension_registry: "ExtensionRegistry | None" = None,
        promotion_handler_registry: "PromotionHandlerRegistry | None" = None,
    ) -> "PublicationDefinitionRecord":
        ...

    def update_publication_definition(
        self,
        publication_definition: "PublicationDefinitionCreate",
        *,
        extension_registry: "ExtensionRegistry | None" = None,
        promotion_handler_registry: "PromotionHandlerRegistry | None" = None,
    ) -> "PublicationDefinitionRecord":
        ...

    def get_publication_definition(
        self, publication_definition_id: str
    ) -> "PublicationDefinitionRecord":
        ...

    def list_publication_definitions(
        self,
        *,
        transformation_package_id: str | None = None,
        include_archived: bool = False,
    ) -> list["PublicationDefinitionRecord"]:
        ...

    def set_publication_definition_archived_state(
        self,
        publication_definition_id: str,
        *,
        archived: bool,
    ) -> "PublicationDefinitionRecord":
        ...


@runtime_checkable
class AssetCatalogStore(Protocol):
    def create_source_asset(self, source_asset: "SourceAssetCreate") -> "SourceAssetRecord":
        ...

    def update_source_asset(self, source_asset: "SourceAssetCreate") -> "SourceAssetRecord":
        ...

    def get_source_asset(self, source_asset_id: str) -> "SourceAssetRecord":
        ...

    def list_source_assets(
        self,
        *,
        include_archived: bool = False,
    ) -> list["SourceAssetRecord"]:
        ...

    def set_source_asset_archived_state(
        self,
        source_asset_id: str,
        *,
        archived: bool,
    ) -> "SourceAssetRecord":
        ...

    def delete_source_asset(self, source_asset_id: str) -> None:
        ...

    def create_source_freshness_config(
        self,
        freshness_config: "SourceFreshnessConfigCreate",
    ) -> "SourceFreshnessConfigRecord":
        ...

    def update_source_freshness_config(
        self,
        freshness_config: "SourceFreshnessConfigCreate",
    ) -> "SourceFreshnessConfigRecord":
        ...

    def get_source_freshness_config(
        self,
        source_asset_id: str,
    ) -> "SourceFreshnessConfigRecord":
        ...

    def list_source_freshness_configs(self) -> list["SourceFreshnessConfigRecord"]:
        ...

    def delete_source_freshness_config(self, source_asset_id: str) -> None:
        ...

    def find_source_asset_by_binding(
        self,
        *,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
    ) -> "SourceAssetRecord | None":
        ...

    def create_ingestion_definition(
        self, ingestion_definition: "IngestionDefinitionCreate"
    ) -> "IngestionDefinitionRecord":
        ...

    def update_ingestion_definition(
        self, ingestion_definition: "IngestionDefinitionCreate"
    ) -> "IngestionDefinitionRecord":
        ...

    def get_ingestion_definition(self, ingestion_definition_id: str) -> "IngestionDefinitionRecord":
        ...

    def list_ingestion_definitions(
        self,
        *,
        enabled_only: bool = False,
        include_archived: bool = False,
    ) -> list["IngestionDefinitionRecord"]:
        ...

    def set_ingestion_definition_archived_state(
        self,
        ingestion_definition_id: str,
        *,
        archived: bool,
    ) -> "IngestionDefinitionRecord":
        ...

    def delete_ingestion_definition(self, ingestion_definition_id: str) -> None:
        ...


@runtime_checkable
class ExternalRegistryStore(Protocol):
    def create_extension_registry_source(
        self,
        source: "ExtensionRegistrySourceCreate",
    ) -> "ExtensionRegistrySourceRecord":
        ...

    def update_extension_registry_source(
        self,
        source: "ExtensionRegistrySourceCreate",
    ) -> "ExtensionRegistrySourceRecord":
        ...

    def get_extension_registry_source(
        self,
        extension_registry_source_id: str,
    ) -> "ExtensionRegistrySourceRecord":
        ...

    def list_extension_registry_sources(
        self,
        *,
        include_archived: bool = False,
    ) -> list["ExtensionRegistrySourceRecord"]:
        ...

    def set_extension_registry_source_archived_state(
        self,
        extension_registry_source_id: str,
        *,
        archived: bool,
    ) -> "ExtensionRegistrySourceRecord":
        ...

    def create_extension_registry_revision(
        self,
        revision: "ExtensionRegistryRevisionCreate",
    ) -> "ExtensionRegistryRevisionRecord":
        ...

    def get_extension_registry_revision(
        self,
        extension_registry_revision_id: str,
    ) -> "ExtensionRegistryRevisionRecord":
        ...

    def list_extension_registry_revisions(
        self,
        *,
        extension_registry_source_id: str | None = None,
    ) -> list["ExtensionRegistryRevisionRecord"]:
        ...

    def activate_extension_registry_revision(
        self,
        *,
        extension_registry_source_id: str,
        extension_registry_revision_id: str,
        activated_at: datetime | None = None,
    ) -> "ExtensionRegistryActivationRecord":
        ...

    def get_extension_registry_activation(
        self,
        extension_registry_source_id: str,
    ) -> "ExtensionRegistryActivationRecord | None":
        ...

    def list_extension_registry_activations(
        self,
    ) -> list["ExtensionRegistryActivationRecord"]:
        ...


@runtime_checkable
class ExecutionStore(Protocol):
    def create_execution_schedule(
        self, schedule: ExecutionScheduleCreate
    ) -> ExecutionScheduleRecord:
        ...

    def update_execution_schedule(
        self, schedule: ExecutionScheduleCreate
    ) -> ExecutionScheduleRecord:
        ...

    def get_execution_schedule(self, schedule_id: str) -> ExecutionScheduleRecord:
        ...

    def list_execution_schedules(
        self,
        *,
        enabled_only: bool = False,
        include_archived: bool = False,
    ) -> list[ExecutionScheduleRecord]:
        ...

    def set_execution_schedule_archived_state(
        self,
        schedule_id: str,
        *,
        archived: bool,
    ) -> ExecutionScheduleRecord:
        ...

    def delete_execution_schedule(self, schedule_id: str) -> None:
        ...

    def enqueue_due_execution_schedules(
        self,
        *,
        as_of: datetime | None = None,
        limit: int | None = None,
    ) -> list[ScheduleDispatchRecord]:
        ...

    def list_schedule_dispatches(
        self,
        *,
        schedule_id: str | None = None,
        status: str | None = None,
    ) -> list[ScheduleDispatchRecord]:
        ...

    def get_schedule_dispatch(self, dispatch_id: str) -> ScheduleDispatchRecord:
        ...

    def create_schedule_dispatch(
        self,
        schedule_id: str,
        *,
        enqueued_at: datetime | None = None,
    ) -> ScheduleDispatchRecord:
        ...

    def claim_schedule_dispatch(
        self,
        dispatch_id: str,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord:
        ...

    def claim_next_schedule_dispatch(
        self,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord | None:
        ...

    def renew_schedule_dispatch_claim(
        self,
        dispatch_id: str,
        *,
        worker_id: str,
        claimed_at: datetime | None = None,
        lease_seconds: int = 300,
        worker_detail: str | None = None,
    ) -> ScheduleDispatchRecord:
        ...

    def requeue_expired_schedule_dispatches(
        self,
        *,
        as_of: datetime | None = None,
        limit: int | None = None,
        recovered_by_worker_id: str | None = None,
    ) -> list[ScheduleDispatchRecoveryRecord]:
        ...

    def mark_schedule_dispatch_status(
        self,
        dispatch_id: str,
        *,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        run_ids: tuple[str, ...] | None = None,
        failure_reason: str | None = None,
        worker_detail: str | None = None,
        expected_status: str | None = None,
        expected_worker_id: str | None = None,
    ) -> ScheduleDispatchRecord:
        ...

    def record_worker_heartbeat(
        self,
        heartbeat: WorkerHeartbeatCreate,
    ) -> WorkerHeartbeatRecord:
        ...

    def list_worker_heartbeats(self) -> list[WorkerHeartbeatRecord]:
        ...


@runtime_checkable
class SourceLineageStore(Protocol):
    def record_source_lineage(
        self, entries: tuple[SourceLineageCreate, ...]
    ) -> list[SourceLineageRecord]:
        ...

    def list_source_lineage(
        self,
        *,
        input_run_id: str | None = None,
        target_layer: str | None = None,
        target_name: str | None = None,
        source_asset_id: str | None = None,
    ) -> list[SourceLineageRecord]:
        ...


@runtime_checkable
class PublicationAuditStore(Protocol):
    def record_publication_audit(
        self, entries: tuple[PublicationAuditCreate, ...]
    ) -> list[PublicationAuditRecord]:
        ...

    def list_publication_audit(
        self,
        *,
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> list[PublicationAuditRecord]:
        ...


@runtime_checkable
class AuthAuditStore(Protocol):
    def record_auth_audit_events(
        self, entries: tuple[AuthAuditEventCreate, ...]
    ) -> list[AuthAuditEventRecord]:
        ...

    def list_auth_audit_events(
        self,
        *,
        event_type: str | None = None,
        success: bool | None = None,
        actor_user_id: str | None = None,
        subject_user_id: str | None = None,
        subject_username: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[AuthAuditEventRecord]:
        ...


@runtime_checkable
class PublicationConfidenceSnapshotStore(Protocol):
    def record_publication_confidence_snapshot(
        self, entries: tuple[PublicationConfidenceSnapshotCreate, ...]
    ) -> list[PublicationConfidenceSnapshotRecord]:
        ...

    def list_publication_confidence_snapshots(
        self,
        *,
        publication_key: str | None = None,
        limit: int | None = None,
    ) -> list[PublicationConfidenceSnapshotRecord]:
        ...


@runtime_checkable
class SnapshotStore(Protocol):
    def export_snapshot(self) -> ControlPlaneSnapshot:
        ...

    def import_snapshot(self, snapshot: ControlPlaneSnapshot) -> None:
        ...


@runtime_checkable
class ConfiguredCsvBindingStore(
    SourceRegistryStore,
    ContractCatalogStore,
    Protocol,
):
    ...


@runtime_checkable
class IngestionCatalogStore(
    SourceRegistryStore,
    AssetCatalogStore,
    Protocol,
):
    ...


@runtime_checkable
class ConfigCatalogStore(
    SourceRegistryStore,
    ContractCatalogStore,
    AssetCatalogStore,
    ExternalRegistryStore,
    Protocol,
):
    def create_reference_fact(
        self,
        reference_fact: "ReferenceFactCreate",
    ) -> "ReferenceFactRecord":
        ...

    def close_reference_fact(
        self,
        fact_id: str,
        *,
        effective_to: date | None = None,
        closed_by: str | None = None,
        closed_at: datetime | None = None,
    ) -> "ReferenceFactRecord":
        ...

    def get_reference_fact(self, fact_id: str) -> "ReferenceFactRecord":
        ...

    def list_reference_facts(
        self,
        *,
        entity_type: str | None = None,
        entity_key: str | None = None,
        attribute: str | None = None,
        include_closed: bool = True,
    ) -> list["ReferenceFactRecord"]:
        ...

    ...


@runtime_checkable
class ControlPlaneAdminStore(
    ConfigCatalogStore,
    ExecutionStore,
    SourceLineageStore,
    PublicationAuditStore,
    PublicationConfidenceSnapshotStore,
    AuthAuditStore,
    Protocol,
):
    ...


@runtime_checkable
class ControlPlaneStore(
    ControlPlaneAdminStore,
    AuthStore,
    SnapshotStore,
    Protocol,
):
    ...
