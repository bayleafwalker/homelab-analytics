"""Control-plane snapshot export/import helpers.

These helpers are portability utilities across control-plane backends. They
preserve shared catalog/control entities where practical, but they are not a
feature-parity contract for every backend-specific schema detail.
"""

from __future__ import annotations

from collections.abc import Callable

from packages.storage.auth_store import (
    LocalUserCreate,
    ServiceTokenCreate,
)
from packages.storage.control_plane import (
    AuthAuditEventCreate,
    ControlPlaneSnapshot,
    ControlPlaneStore,
    ExecutionScheduleCreate,
    PublicationAuditCreate,
    SourceLineageCreate,
)
from packages.storage.external_registry_catalog import (
    ExtensionRegistryRevisionCreate,
    ExtensionRegistrySourceCreate,
)
from packages.storage.ingestion_catalog import (
    ColumnMappingCreate,
    DatasetContractConfigCreate,
    IngestionDefinitionCreate,
    PublicationDefinitionCreate,
    SourceAssetCreate,
    SourceFreshnessConfigCreate,
    SourceSystemCreate,
    TransformationPackageCreate,
)


def export_control_plane_snapshot(store: ControlPlaneStore) -> ControlPlaneSnapshot:
    return ControlPlaneSnapshot(
        source_systems=tuple(store.list_source_systems()),
        dataset_contracts=tuple(store.list_dataset_contracts(include_archived=True)),
        column_mappings=tuple(store.list_column_mappings(include_archived=True)),
        transformation_packages=tuple(
            store.list_transformation_packages(include_archived=True)
        ),
        publication_definitions=tuple(
            store.list_publication_definitions(include_archived=True)
        ),
        source_assets=tuple(store.list_source_assets(include_archived=True)),
        source_freshness_configs=tuple(store.list_source_freshness_configs()),
        ingestion_definitions=tuple(
            store.list_ingestion_definitions(include_archived=True)
        ),
        extension_registry_sources=tuple(
            store.list_extension_registry_sources(include_archived=True)
        ),
        extension_registry_revisions=tuple(store.list_extension_registry_revisions()),
        extension_registry_activations=tuple(store.list_extension_registry_activations()),
        execution_schedules=tuple(store.list_execution_schedules(include_archived=True)),
        source_lineage=tuple(store.list_source_lineage()),
        publication_audit=tuple(store.list_publication_audit()),
        auth_audit_events=tuple(store.list_auth_audit_events()),
        local_users=tuple(store.list_local_users()),
        service_tokens=tuple(store.list_service_tokens(include_revoked=True)),
    )


def import_control_plane_snapshot(
    store: ControlPlaneStore,
    snapshot: ControlPlaneSnapshot,
    *,
    duplicate_exceptions: tuple[type[Exception], ...],
) -> None:
    for source_system_record in snapshot.source_systems:
        _ignore_duplicate(
            store.create_source_system,
            SourceSystemCreate(
                source_system_id=source_system_record.source_system_id,
                name=source_system_record.name,
                source_type=source_system_record.source_type,
                transport=source_system_record.transport,
                schedule_mode=source_system_record.schedule_mode,
                description=source_system_record.description,
                enabled=source_system_record.enabled,
                created_at=source_system_record.created_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for dataset_contract_record in snapshot.dataset_contracts:
        _ignore_duplicate(
            store.create_dataset_contract,
            DatasetContractConfigCreate(
                dataset_contract_id=dataset_contract_record.dataset_contract_id,
                dataset_name=dataset_contract_record.dataset_name,
                version=dataset_contract_record.version,
                allow_extra_columns=dataset_contract_record.allow_extra_columns,
                columns=dataset_contract_record.columns,
                archived=False,
                created_at=dataset_contract_record.created_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for column_mapping_record in snapshot.column_mappings:
        _ignore_duplicate(
            store.create_column_mapping,
            ColumnMappingCreate(
                column_mapping_id=column_mapping_record.column_mapping_id,
                source_system_id=column_mapping_record.source_system_id,
                dataset_contract_id=column_mapping_record.dataset_contract_id,
                version=column_mapping_record.version,
                rules=column_mapping_record.rules,
                archived=False,
                created_at=column_mapping_record.created_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for transformation_package_record in snapshot.transformation_packages:
        _ignore_duplicate(
            store.create_transformation_package,
            TransformationPackageCreate(
                transformation_package_id=transformation_package_record.transformation_package_id,
                name=transformation_package_record.name,
                handler_key=transformation_package_record.handler_key,
                version=transformation_package_record.version,
                description=transformation_package_record.description,
                archived=False,
                created_at=transformation_package_record.created_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for publication_definition_record in snapshot.publication_definitions:
        _ignore_duplicate(
            store.create_publication_definition,
            PublicationDefinitionCreate(
                publication_definition_id=publication_definition_record.publication_definition_id,
                transformation_package_id=publication_definition_record.transformation_package_id,
                publication_key=publication_definition_record.publication_key,
                name=publication_definition_record.name,
                description=publication_definition_record.description,
                archived=False,
                created_at=publication_definition_record.created_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for source_asset_record in snapshot.source_assets:
        _ignore_duplicate(
            store.create_source_asset,
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
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for freshness_config_record in snapshot.source_freshness_configs:
        _ignore_duplicate(
            store.create_source_freshness_config,
            SourceFreshnessConfigCreate(
                source_asset_id=freshness_config_record.source_asset_id,
                acquisition_mode=freshness_config_record.acquisition_mode,
                expected_frequency=freshness_config_record.expected_frequency,
                coverage_kind=freshness_config_record.coverage_kind,
                due_day_of_month=freshness_config_record.due_day_of_month,
                expected_window_days=freshness_config_record.expected_window_days,
                freshness_sla_days=freshness_config_record.freshness_sla_days,
                sensitivity_class=freshness_config_record.sensitivity_class,
                reminder_channel=freshness_config_record.reminder_channel,
                requires_human_action=freshness_config_record.requires_human_action,
                created_at=freshness_config_record.created_at,
                updated_at=freshness_config_record.updated_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for ingestion_definition_record in snapshot.ingestion_definitions:
        _ignore_duplicate(
            store.create_ingestion_definition,
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
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for extension_registry_source_record in snapshot.extension_registry_sources:
        _ignore_duplicate(
            store.create_extension_registry_source,
            ExtensionRegistrySourceCreate(
                extension_registry_source_id=(
                    extension_registry_source_record.extension_registry_source_id
                ),
                name=extension_registry_source_record.name,
                source_kind=extension_registry_source_record.source_kind,
                location=extension_registry_source_record.location,
                desired_ref=extension_registry_source_record.desired_ref,
                subdirectory=extension_registry_source_record.subdirectory,
                auth_secret_name=extension_registry_source_record.auth_secret_name,
                auth_secret_key=extension_registry_source_record.auth_secret_key,
                enabled=extension_registry_source_record.enabled,
                archived=False,
                created_at=extension_registry_source_record.created_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for extension_registry_revision_record in snapshot.extension_registry_revisions:
        _ignore_duplicate(
            store.create_extension_registry_revision,
            ExtensionRegistryRevisionCreate(
                extension_registry_revision_id=(
                    extension_registry_revision_record.extension_registry_revision_id
                ),
                extension_registry_source_id=(
                    extension_registry_revision_record.extension_registry_source_id
                ),
                resolved_ref=extension_registry_revision_record.resolved_ref,
                runtime_path=extension_registry_revision_record.runtime_path,
                manifest_path=extension_registry_revision_record.manifest_path,
                manifest_digest=extension_registry_revision_record.manifest_digest,
                manifest_version=extension_registry_revision_record.manifest_version,
                content_fingerprint=(
                    extension_registry_revision_record.content_fingerprint
                ),
                import_paths=extension_registry_revision_record.import_paths,
                extension_modules=extension_registry_revision_record.extension_modules,
                function_modules=extension_registry_revision_record.function_modules,
                minimum_platform_version=(
                    extension_registry_revision_record.minimum_platform_version
                ),
                sync_status=extension_registry_revision_record.sync_status,
                validation_error=extension_registry_revision_record.validation_error,
                created_at=extension_registry_revision_record.created_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for execution_schedule_record in snapshot.execution_schedules:
        _ignore_duplicate(
            store.create_execution_schedule,
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
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for source_asset_record in snapshot.source_assets:
        if source_asset_record.archived:
            store.set_source_asset_archived_state(
                source_asset_record.source_asset_id,
                archived=True,
            )
    for freshness_config_record in snapshot.source_freshness_configs:
        if freshness_config_record.source_asset_id:
            store.update_source_freshness_config(
                SourceFreshnessConfigCreate(
                    source_asset_id=freshness_config_record.source_asset_id,
                    acquisition_mode=freshness_config_record.acquisition_mode,
                    expected_frequency=freshness_config_record.expected_frequency,
                    coverage_kind=freshness_config_record.coverage_kind,
                    due_day_of_month=freshness_config_record.due_day_of_month,
                    expected_window_days=freshness_config_record.expected_window_days,
                    freshness_sla_days=freshness_config_record.freshness_sla_days,
                    sensitivity_class=freshness_config_record.sensitivity_class,
                    reminder_channel=freshness_config_record.reminder_channel,
                    requires_human_action=freshness_config_record.requires_human_action,
                    created_at=freshness_config_record.created_at,
                    updated_at=freshness_config_record.updated_at,
                )
            )
    for publication_definition_record in snapshot.publication_definitions:
        if publication_definition_record.archived:
            store.set_publication_definition_archived_state(
                publication_definition_record.publication_definition_id,
                archived=True,
            )
    for transformation_package_record in snapshot.transformation_packages:
        if transformation_package_record.archived:
            store.set_transformation_package_archived_state(
                transformation_package_record.transformation_package_id,
                archived=True,
            )
    for ingestion_definition_record in snapshot.ingestion_definitions:
        if ingestion_definition_record.archived:
            store.set_ingestion_definition_archived_state(
                ingestion_definition_record.ingestion_definition_id,
                archived=True,
            )
    for execution_schedule_record in snapshot.execution_schedules:
        if execution_schedule_record.archived:
            store.set_execution_schedule_archived_state(
                execution_schedule_record.schedule_id,
                archived=True,
            )
    for extension_registry_activation_record in snapshot.extension_registry_activations:
        store.activate_extension_registry_revision(
            extension_registry_source_id=(
                extension_registry_activation_record.extension_registry_source_id
            ),
            extension_registry_revision_id=(
                extension_registry_activation_record.extension_registry_revision_id
            ),
            activated_at=extension_registry_activation_record.activated_at,
        )
    for extension_registry_source_record in snapshot.extension_registry_sources:
        if extension_registry_source_record.archived:
            store.set_extension_registry_source_archived_state(
                extension_registry_source_record.extension_registry_source_id,
                archived=True,
            )
    for column_mapping_record in snapshot.column_mappings:
        if column_mapping_record.archived:
            store.set_column_mapping_archived_state(
                column_mapping_record.column_mapping_id,
                archived=True,
            )
    for dataset_contract_record in snapshot.dataset_contracts:
        if dataset_contract_record.archived:
            store.set_dataset_contract_archived_state(
                dataset_contract_record.dataset_contract_id,
                archived=True,
            )
    store.record_source_lineage(
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
    store.record_publication_audit(
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
    store.record_auth_audit_events(
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
        _ignore_duplicate(
            store.create_local_user,
            LocalUserCreate(
                user_id=local_user_record.user_id,
                username=local_user_record.username,
                password_hash=local_user_record.password_hash,
                role=local_user_record.role,
                enabled=local_user_record.enabled,
                created_at=local_user_record.created_at,
                last_login_at=local_user_record.last_login_at,
            ),
            duplicate_exceptions=duplicate_exceptions,
        )
    for service_token_record in snapshot.service_tokens:
        _ignore_duplicate(
            store.create_service_token,
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
            ),
            duplicate_exceptions=duplicate_exceptions,
        )


def _ignore_duplicate(
    operation: Callable[..., object],
    *args: object,
    duplicate_exceptions: tuple[type[Exception], ...],
) -> None:
    try:
        operation(*args)
    except Exception as exc:
        if isinstance(exc, duplicate_exceptions):
            return
        raise
