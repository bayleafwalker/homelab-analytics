from __future__ import annotations

from datetime import UTC, datetime

import psycopg

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
    DatasetContractConfigCreate,
    IngestionDefinitionCreate,
    PublicationDefinitionCreate,
    SourceAssetCreate,
    SourceSystemCreate,
    TransformationPackageCreate,
)
from packages.storage.postgres_asset_definition_catalog import (
    PostgresAssetDefinitionCatalogMixin,
)
from packages.storage.postgres_auth_control_plane import (
    PostgresAuthControlPlaneMixin,
)
from packages.storage.postgres_execution_control_plane import (
    PostgresExecutionControlPlaneMixin,
)
from packages.storage.postgres_provenance_control_plane import (
    PostgresProvenanceControlPlaneMixin,
)
from packages.storage.postgres_source_contract_catalog import (
    PostgresSourceContractCatalogMixin,
)
from packages.storage.postgres_support import configure_search_path, initialize_schema


class PostgresIngestionConfigRepository(
    PostgresSourceContractCatalogMixin,
    PostgresAssetDefinitionCatalogMixin,
    PostgresExecutionControlPlaneMixin,
    PostgresProvenanceControlPlaneMixin,
    PostgresAuthControlPlaneMixin,
):
    def __init__(self, dsn: str, *, schema: str = "public") -> None:
        self.dsn = dsn
        self.schema = schema
        initialize_schema(dsn, schema)
        self._initialize()

    def _connect(self, *, row_factory=None):
        connection = psycopg.connect(self.dsn, row_factory=row_factory)
        configure_search_path(connection, self.schema)
        return connection

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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
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
            except psycopg.Error:
                continue

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_systems (
                    source_system_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    schedule_mode TEXT NOT NULL,
                    description TEXT,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_contracts (
                    dataset_contract_id TEXT PRIMARY KEY,
                    dataset_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    allow_extra_columns BOOLEAN NOT NULL,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    columns_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS column_mappings (
                    column_mapping_id TEXT PRIMARY KEY,
                    source_system_id TEXT NOT NULL REFERENCES source_systems (source_system_id),
                    dataset_contract_id TEXT NOT NULL REFERENCES dataset_contracts (dataset_contract_id),
                    version INTEGER NOT NULL,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    rules_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transformation_packages (
                    transformation_package_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    handler_key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_definitions (
                    publication_definition_id TEXT PRIMARY KEY,
                    transformation_package_id TEXT NOT NULL REFERENCES transformation_packages (transformation_package_id),
                    publication_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_assets (
                    source_asset_id TEXT PRIMARY KEY,
                    source_system_id TEXT NOT NULL REFERENCES source_systems (source_system_id),
                    dataset_contract_id TEXT NOT NULL REFERENCES dataset_contracts (dataset_contract_id),
                    column_mapping_id TEXT NOT NULL REFERENCES column_mappings (column_mapping_id),
                    transformation_package_id TEXT REFERENCES transformation_packages (transformation_package_id),
                    name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    description TEXT,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_definitions (
                    ingestion_definition_id TEXT PRIMARY KEY,
                    source_asset_id TEXT NOT NULL REFERENCES source_assets (source_asset_id),
                    transport TEXT NOT NULL,
                    schedule_mode TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    file_pattern TEXT NOT NULL,
                    processed_path TEXT,
                    failed_path TEXT,
                    poll_interval_seconds INTEGER,
                    request_url TEXT,
                    request_method TEXT,
                    request_headers_json TEXT,
                    request_timeout_seconds INTEGER,
                    response_format TEXT,
                    output_file_name TEXT,
                    enabled BOOLEAN NOT NULL,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    source_name TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    target_kind TEXT NOT NULL,
                    target_ref TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    archived BOOLEAN NOT NULL DEFAULT FALSE,
                    max_concurrency INTEGER NOT NULL,
                    next_due_at TIMESTAMPTZ,
                    last_enqueued_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schedule_dispatches (
                    dispatch_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL REFERENCES execution_schedules (schedule_id),
                    target_kind TEXT NOT NULL,
                    target_ref TEXT NOT NULL,
                    enqueued_at TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ,
                    run_ids_json TEXT NOT NULL DEFAULT '[]',
                    failure_reason TEXT,
                    worker_detail TEXT,
                    claimed_by_worker_id TEXT,
                    claimed_at TIMESTAMPTZ,
                    claim_expires_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    worker_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    active_dispatch_id TEXT,
                    detail TEXT,
                    observed_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_lineage (
                    lineage_id TEXT PRIMARY KEY,
                    input_run_id TEXT,
                    target_layer TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    row_count INTEGER,
                    source_system TEXT,
                    source_run_id TEXT,
                    recorded_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_audit (
                    publication_audit_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    publication_key TEXT NOT NULL,
                    relation_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    published_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS local_users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    last_login_at TIMESTAMPTZ
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    actor_user_id TEXT,
                    actor_username TEXT,
                    subject_user_id TEXT,
                    subject_username TEXT,
                    remote_addr TEXT,
                    user_agent TEXT,
                    detail TEXT,
                    occurred_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS service_tokens (
                    token_id TEXT PRIMARY KEY,
                    token_name TEXT NOT NULL,
                    token_secret_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    scopes_json JSONB NOT NULL,
                    expires_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL,
                    last_used_at TIMESTAMPTZ,
                    revoked_at TIMESTAMPTZ
                )
                """
            )
            connection.execute(
                """
                ALTER TABLE source_systems
                ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
            connection.execute(
                """
                ALTER TABLE dataset_contracts
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE column_mappings
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE source_assets
                ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
            connection.execute(
                """
                ALTER TABLE source_assets
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE ingestion_definitions
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE execution_schedules
                ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS run_ids_json TEXT NOT NULL DEFAULT '[]'
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS failure_reason TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS worker_detail TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS claimed_by_worker_id TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ
                """
            )
            connection.execute(
                """
                ALTER TABLE schedule_dispatches
                ADD COLUMN IF NOT EXISTS claim_expires_at TIMESTAMPTZ
                """
            )
            self._seed_builtins(connection)

    def _seed_builtins(self, connection: psycopg.Connection) -> None:
        now = datetime.now(UTC)
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO transformation_packages (
                    transformation_package_id, name, handler_key, version, description, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (transformation_package_id) DO NOTHING
                """,
                [
                    (
                        package.transformation_package_id,
                        package.name,
                        package.handler_key,
                        package.version,
                        package.description,
                        now,
                    )
                    for package in _BUILTIN_TRANSFORMATION_PACKAGES
                ],
            )
            cursor.executemany(
                """
                INSERT INTO publication_definitions (
                    publication_definition_id, transformation_package_id, publication_key, name, description, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (publication_definition_id) DO NOTHING
                """,
                [
                    (
                        publication.publication_definition_id,
                        publication.transformation_package_id,
                        publication.publication_key,
                        publication.name,
                        publication.description,
                        now,
                    )
                    for publication in _BUILTIN_PUBLICATION_DEFINITIONS
                ],
            )
