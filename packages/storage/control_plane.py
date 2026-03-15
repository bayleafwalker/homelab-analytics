from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from packages.shared.extensions import ExtensionRegistry
    from packages.storage.auth_store import LocalUserRecord
    from packages.storage.ingestion_config import (
        ColumnMappingCreate,
        ColumnMappingRecord,
        DatasetContractConfigCreate,
        DatasetContractConfigRecord,
        IngestionDefinitionCreate,
        IngestionDefinitionRecord,
        PublicationDefinitionCreate,
        PublicationDefinitionRecord,
        SourceAssetCreate,
        SourceAssetRecord,
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
    completed_at: datetime | None


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
    execution_schedules: tuple[ExecutionScheduleRecord, ...] = ()
    source_lineage: tuple[SourceLineageRecord, ...] = ()
    publication_audit: tuple[PublicationAuditRecord, ...] = ()
    auth_audit_events: tuple[AuthAuditEventRecord, ...] = ()
    local_users: tuple["LocalUserRecord", ...] = ()


class ControlPlaneStore(Protocol):
    def create_source_system(self, source_system: "SourceSystemCreate") -> "SourceSystemRecord":
        ...

    def update_source_system(self, source_system: "SourceSystemCreate") -> "SourceSystemRecord":
        ...

    def get_source_system(self, source_system_id: str) -> "SourceSystemRecord":
        ...

    def list_source_systems(self) -> list["SourceSystemRecord"]:
        ...

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
        self, transformation_package: "TransformationPackageCreate"
    ) -> "TransformationPackageRecord":
        ...

    def get_transformation_package(
        self, transformation_package_id: str
    ) -> "TransformationPackageRecord":
        ...

    def list_transformation_packages(self) -> list["TransformationPackageRecord"]:
        ...

    def create_publication_definition(
        self,
        publication_definition: "PublicationDefinitionCreate",
        *,
        extension_registry: "ExtensionRegistry | None" = None,
    ) -> "PublicationDefinitionRecord":
        ...

    def get_publication_definition(
        self, publication_definition_id: str
    ) -> "PublicationDefinitionRecord":
        ...

    def list_publication_definitions(
        self, *, transformation_package_id: str | None = None
    ) -> list["PublicationDefinitionRecord"]:
        ...

    def create_source_asset(self, source_asset: "SourceAssetCreate") -> "SourceAssetRecord":
        ...

    def update_source_asset(self, source_asset: "SourceAssetCreate") -> "SourceAssetRecord":
        ...

    def get_source_asset(self, source_asset_id: str) -> "SourceAssetRecord":
        ...

    def list_source_assets(self) -> list["SourceAssetRecord"]:
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
        self, *, enabled_only: bool = False
    ) -> list["IngestionDefinitionRecord"]:
        ...

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
        self, *, enabled_only: bool = False
    ) -> list[ExecutionScheduleRecord]:
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

    def create_schedule_dispatch(
        self,
        schedule_id: str,
        *,
        enqueued_at: datetime | None = None,
    ) -> ScheduleDispatchRecord:
        ...

    def mark_schedule_dispatch_status(
        self,
        dispatch_id: str,
        *,
        status: str,
        completed_at: datetime | None = None,
    ) -> ScheduleDispatchRecord:
        ...

    def record_source_lineage(
        self, entries: tuple[SourceLineageCreate, ...]
    ) -> list[SourceLineageRecord]:
        ...

    def list_source_lineage(
        self,
        *,
        input_run_id: str | None = None,
        target_layer: str | None = None,
    ) -> list[SourceLineageRecord]:
        ...

    def record_publication_audit(
        self, entries: tuple[PublicationAuditCreate, ...]
    ) -> list[PublicationAuditRecord]:
        ...

    def list_publication_audit(
        self, *, run_id: str | None = None, publication_key: str | None = None
    ) -> list[PublicationAuditRecord]:
        ...

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

    def export_snapshot(self) -> ControlPlaneSnapshot:
        ...

    def import_snapshot(self, snapshot: ControlPlaneSnapshot) -> None:
        ...


@runtime_checkable
class SourceLineageStore(Protocol):
    def record_source_lineage(
        self, entries: tuple[SourceLineageCreate, ...]
    ) -> list[SourceLineageRecord]:
        ...


@runtime_checkable
class PublicationAuditStore(Protocol):
    def record_publication_audit(
        self, entries: tuple[PublicationAuditCreate, ...]
    ) -> list[PublicationAuditRecord]:
        ...


@runtime_checkable
class AuthAuditStore(Protocol):
    def record_auth_audit_events(
        self, entries: tuple[AuthAuditEventCreate, ...]
    ) -> list[AuthAuditEventRecord]:
        ...
