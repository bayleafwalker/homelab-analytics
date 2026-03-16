from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from packages.storage.auth_store import (
    LocalUserCreate,
    ServiceTokenCreate,
)
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    ControlPlaneSnapshot,
    ExecutionScheduleCreate,
    PublicationAuditCreate,
    SourceLineageCreate,
)
from packages.storage.ingestion_catalog import (
    _BUILTIN_PUBLICATION_DEFINITIONS,
    _BUILTIN_TRANSFORMATION_PACKAGES,
    ColumnMappingCreate,
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    IngestionDefinitionRecord,
    PublicationDefinitionCreate,
    PublicationDefinitionRecord,
    RequestHeaderSecretRef,
    SourceAssetCreate,
    SourceAssetRecord,
    SourceSystemCreate,
    SourceSystemRecord,
    TransformationPackageCreate,
    TransformationPackageRecord,
    allowed_publication_keys,
    resolve_dataset_contract,
    validate_publication_key,
)
from packages.storage.sqlite_asset_definition_catalog import (
    SQLiteAssetDefinitionCatalogMixin,
)
from packages.storage.sqlite_auth_control_plane import SQLiteAuthControlPlaneMixin
from packages.storage.sqlite_control_plane_schema import (
    initialize_sqlite_control_plane_schema,
)
from packages.storage.sqlite_execution_control_plane import (
    SQLiteExecutionControlPlaneMixin,
)
from packages.storage.sqlite_provenance_control_plane import (
    SQLiteProvenanceControlPlaneMixin,
)
from packages.storage.sqlite_source_contract_catalog import (
    SQLiteSourceContractCatalogMixin,
)

__all__ = [
    "ColumnMappingCreate",
    "ColumnMappingRecord",
    "ColumnMappingRule",
    "DatasetColumnConfig",
    "DatasetContractConfigCreate",
    "DatasetContractConfigRecord",
    "IngestionConfigRepository",
    "IngestionDefinitionCreate",
    "IngestionDefinitionRecord",
    "PublicationDefinitionCreate",
    "PublicationDefinitionRecord",
    "RequestHeaderSecretRef",
    "SourceAssetCreate",
    "SourceAssetRecord",
    "SourceSystemCreate",
    "SourceSystemRecord",
    "TransformationPackageCreate",
    "TransformationPackageRecord",
    "allowed_publication_keys",
    "resolve_dataset_contract",
    "validate_publication_key",
    "_BUILTIN_PUBLICATION_DEFINITIONS",
    "_BUILTIN_TRANSFORMATION_PACKAGES",
]


class IngestionConfigRepository(
    SQLiteSourceContractCatalogMixin,
    SQLiteAssetDefinitionCatalogMixin,
    SQLiteExecutionControlPlaneMixin,
    SQLiteProvenanceControlPlaneMixin,
    SQLiteAuthControlPlaneMixin,
):
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def export_snapshot(self) -> ControlPlaneSnapshot:
        return ControlPlaneSnapshot(
            source_systems=tuple(self.list_source_systems()),
            dataset_contracts=tuple(self.list_dataset_contracts(include_archived=True)),
            column_mappings=tuple(self.list_column_mappings(include_archived=True)),
            transformation_packages=tuple(self.list_transformation_packages()),
            publication_definitions=tuple(self.list_publication_definitions()),
            source_assets=tuple(self.list_source_assets(include_archived=True)),
            ingestion_definitions=tuple(
                self.list_ingestion_definitions(include_archived=True)
            ),
            execution_schedules=tuple(
                self.list_execution_schedules(include_archived=True)
            ),
            source_lineage=tuple(self.list_source_lineage()),
            publication_audit=tuple(self.list_publication_audit()),
            auth_audit_events=tuple(self.list_auth_audit_events()),
            local_users=tuple(self.list_local_users()),
            service_tokens=tuple(self.list_service_tokens(include_revoked=True)),
        )

    def import_snapshot(self, snapshot: ControlPlaneSnapshot) -> None:
        for source_system_record in snapshot.source_systems:
            try:
                self.create_source_system(
                    SourceSystemCreate(
                        source_system_id=source_system_record.source_system_id,
                        name=source_system_record.name,
                        source_type=source_system_record.source_type,
                        transport=source_system_record.transport,
                        schedule_mode=source_system_record.schedule_mode,
                        description=source_system_record.description,
                        enabled=source_system_record.enabled,
                        created_at=source_system_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for dataset_contract_record in snapshot.dataset_contracts:
            try:
                self.create_dataset_contract(
                    DatasetContractConfigCreate(
                        dataset_contract_id=dataset_contract_record.dataset_contract_id,
                        dataset_name=dataset_contract_record.dataset_name,
                        version=dataset_contract_record.version,
                        allow_extra_columns=dataset_contract_record.allow_extra_columns,
                        columns=dataset_contract_record.columns,
                        archived=False,
                        created_at=dataset_contract_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for column_mapping_record in snapshot.column_mappings:
            try:
                self.create_column_mapping(
                    ColumnMappingCreate(
                        column_mapping_id=column_mapping_record.column_mapping_id,
                        source_system_id=column_mapping_record.source_system_id,
                        dataset_contract_id=column_mapping_record.dataset_contract_id,
                        version=column_mapping_record.version,
                        rules=column_mapping_record.rules,
                        archived=False,
                        created_at=column_mapping_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for transformation_package_record in snapshot.transformation_packages:
            try:
                self.create_transformation_package(
                    TransformationPackageCreate(
                        transformation_package_id=transformation_package_record.transformation_package_id,
                        name=transformation_package_record.name,
                        handler_key=transformation_package_record.handler_key,
                        version=transformation_package_record.version,
                        description=transformation_package_record.description,
                        created_at=transformation_package_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for publication_definition_record in snapshot.publication_definitions:
            try:
                self.create_publication_definition(
                    PublicationDefinitionCreate(
                        publication_definition_id=publication_definition_record.publication_definition_id,
                        transformation_package_id=publication_definition_record.transformation_package_id,
                        publication_key=publication_definition_record.publication_key,
                        name=publication_definition_record.name,
                        description=publication_definition_record.description,
                        created_at=publication_definition_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for source_asset_record in snapshot.source_assets:
            try:
                self.create_source_asset(
                    SourceAssetCreate(
                        source_asset_id=source_asset_record.source_asset_id,
                        source_system_id=source_asset_record.source_system_id,
                        dataset_contract_id=source_asset_record.dataset_contract_id,
                        column_mapping_id=source_asset_record.column_mapping_id,
                        transformation_package_id=source_asset_record.transformation_package_id,
                        name=source_asset_record.name,
                        asset_type=source_asset_record.asset_type,
                        description=source_asset_record.description,
                        enabled=source_asset_record.enabled,
                        archived=False,
                        created_at=source_asset_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for ingestion_definition_record in snapshot.ingestion_definitions:
            try:
                self.create_ingestion_definition(
                    IngestionDefinitionCreate(
                        ingestion_definition_id=ingestion_definition_record.ingestion_definition_id,
                        source_asset_id=ingestion_definition_record.source_asset_id,
                        transport=ingestion_definition_record.transport,
                        schedule_mode=ingestion_definition_record.schedule_mode,
                        source_path=ingestion_definition_record.source_path,
                        file_pattern=ingestion_definition_record.file_pattern,
                        processed_path=ingestion_definition_record.processed_path,
                        failed_path=ingestion_definition_record.failed_path,
                        poll_interval_seconds=ingestion_definition_record.poll_interval_seconds,
                        request_url=ingestion_definition_record.request_url,
                        request_method=ingestion_definition_record.request_method,
                        request_headers=ingestion_definition_record.request_headers,
                        request_timeout_seconds=ingestion_definition_record.request_timeout_seconds,
                        response_format=ingestion_definition_record.response_format,
                        output_file_name=ingestion_definition_record.output_file_name,
                        enabled=ingestion_definition_record.enabled,
                        archived=False,
                        source_name=ingestion_definition_record.source_name,
                        created_at=ingestion_definition_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for execution_schedule_record in snapshot.execution_schedules:
            try:
                self.create_execution_schedule(
                    ExecutionScheduleCreate(
                        schedule_id=execution_schedule_record.schedule_id,
                        target_kind=execution_schedule_record.target_kind,
                        target_ref=execution_schedule_record.target_ref,
                        cron_expression=execution_schedule_record.cron_expression,
                        timezone=execution_schedule_record.timezone,
                        enabled=execution_schedule_record.enabled,
                        archived=False,
                        max_concurrency=execution_schedule_record.max_concurrency,
                        next_due_at=execution_schedule_record.next_due_at,
                        last_enqueued_at=execution_schedule_record.last_enqueued_at,
                        created_at=execution_schedule_record.created_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for source_asset_record in snapshot.source_assets:
            if source_asset_record.archived:
                self.set_source_asset_archived_state(
                    source_asset_record.source_asset_id,
                    archived=True,
                )
        for ingestion_definition_record in snapshot.ingestion_definitions:
            if ingestion_definition_record.archived:
                self.set_ingestion_definition_archived_state(
                    ingestion_definition_record.ingestion_definition_id,
                    archived=True,
                )
        for execution_schedule_record in snapshot.execution_schedules:
            if execution_schedule_record.archived:
                self.set_execution_schedule_archived_state(
                    execution_schedule_record.schedule_id,
                    archived=True,
                )
        for column_mapping_record in snapshot.column_mappings:
            if column_mapping_record.archived:
                self.set_column_mapping_archived_state(
                    column_mapping_record.column_mapping_id,
                    archived=True,
                )
        for dataset_contract_record in snapshot.dataset_contracts:
            if dataset_contract_record.archived:
                self.set_dataset_contract_archived_state(
                    dataset_contract_record.dataset_contract_id,
                    archived=True,
                )
        self.record_source_lineage(
            tuple(
                SourceLineageCreate(
                    lineage_id=record.lineage_id,
                    input_run_id=record.input_run_id,
                    target_layer=record.target_layer,
                    target_name=record.target_name,
                    target_kind=record.target_kind,
                    row_count=record.row_count,
                    source_system=record.source_system,
                    source_run_id=record.source_run_id,
                    recorded_at=record.recorded_at,
                )
                for record in snapshot.source_lineage
            )
        )
        self.record_publication_audit(
            tuple(
                PublicationAuditCreate(
                    publication_audit_id=record.publication_audit_id,
                    run_id=record.run_id,
                    publication_key=record.publication_key,
                    relation_name=record.relation_name,
                    status=record.status,
                    published_at=record.published_at,
                )
                for record in snapshot.publication_audit
            )
        )
        self.record_auth_audit_events(
            tuple(
                AuthAuditEventCreate(
                    event_id=record.event_id,
                    event_type=record.event_type,
                    success=record.success,
                    actor_user_id=record.actor_user_id,
                    actor_username=record.actor_username,
                    subject_user_id=record.subject_user_id,
                    subject_username=record.subject_username,
                    remote_addr=record.remote_addr,
                    user_agent=record.user_agent,
                    detail=record.detail,
                    occurred_at=record.occurred_at,
                )
                for record in snapshot.auth_audit_events
            )
        )
        for local_user_record in snapshot.local_users:
            try:
                self.create_local_user(
                    LocalUserCreate(
                        user_id=local_user_record.user_id,
                        username=local_user_record.username,
                        password_hash=local_user_record.password_hash,
                        role=local_user_record.role,
                        enabled=local_user_record.enabled,
                        created_at=local_user_record.created_at,
                        last_login_at=local_user_record.last_login_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue
        for service_token_record in snapshot.service_tokens:
            try:
                self.create_service_token(
                    ServiceTokenCreate(
                        token_id=service_token_record.token_id,
                        token_name=service_token_record.token_name,
                        token_secret_hash=service_token_record.token_secret_hash,
                        role=service_token_record.role,
                        scopes=service_token_record.scopes,
                        expires_at=service_token_record.expires_at,
                        created_at=service_token_record.created_at,
                        last_used_at=service_token_record.last_used_at,
                        revoked_at=service_token_record.revoked_at,
                    )
                )
            except sqlite3.IntegrityError:
                continue

    def _initialize(self) -> None:
        with self._connect() as connection:
            initialize_sqlite_control_plane_schema(connection)
            connection.commit()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)
