from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, TextIO

from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionProcessResult,
)
from packages.pipelines.csv_validation import ColumnType
from packages.storage.auth_store import LocalUserRecord, ServiceTokenRecord, UserRole
from packages.storage.control_plane import (
    AuthAuditEventRecord,
    ControlPlaneSnapshot,
    ExecutionScheduleRecord,
    PublicationAuditRecord,
    SourceLineageRecord,
)
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigRecord,
    IngestionDefinitionRecord,
    PublicationDefinitionRecord,
    RequestHeaderSecretRef,
    SourceAssetRecord,
    SourceSystemRecord,
    TransformationPackageRecord,
)


def _write_json(output: TextIO, payload: dict[str, object]) -> None:
    output.write(f"{json.dumps(payload, default=_json_default)}\n")


def _serialize_inbox_result(
    result: ConfiguredIngestionProcessResult,
) -> dict[str, int]:
    return {
        "discovered_files": result.discovered_files,
        "processed_files": result.processed_files,
        "rejected_files": result.rejected_files,
    }


def _json_default(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {value!r}")


def _control_plane_snapshot_to_dict(snapshot: ControlPlaneSnapshot) -> dict[str, object]:
    return {
        "source_systems": list(snapshot.source_systems),
        "dataset_contracts": list(snapshot.dataset_contracts),
        "column_mappings": list(snapshot.column_mappings),
        "transformation_packages": list(snapshot.transformation_packages),
        "publication_definitions": list(snapshot.publication_definitions),
        "source_assets": list(snapshot.source_assets),
        "ingestion_definitions": list(snapshot.ingestion_definitions),
        "execution_schedules": list(snapshot.execution_schedules),
        "source_lineage": list(snapshot.source_lineage),
        "publication_audit": list(snapshot.publication_audit),
        "auth_audit_events": list(snapshot.auth_audit_events),
        "local_users": list(snapshot.local_users),
        "service_tokens": list(snapshot.service_tokens),
    }


def _control_plane_snapshot_from_dict(payload: dict[str, Any]) -> ControlPlaneSnapshot:
    return ControlPlaneSnapshot(
        source_systems=tuple(
            SourceSystemRecord(
                source_system_id=item["source_system_id"],
                name=item["name"],
                source_type=item["source_type"],
                transport=item["transport"],
                schedule_mode=item["schedule_mode"],
                description=item.get("description"),
                enabled=item.get("enabled", True),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("source_systems", [])
        ),
        dataset_contracts=tuple(
            DatasetContractConfigRecord(
                dataset_contract_id=item["dataset_contract_id"],
                dataset_name=item["dataset_name"],
                version=item["version"],
                allow_extra_columns=item["allow_extra_columns"],
                columns=tuple(
                    DatasetColumnConfig(
                        name=column["name"],
                        type=ColumnType(column["type"]),
                        required=column["required"],
                    )
                    for column in item["columns"]
                ),
                archived=item.get("archived", False),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("dataset_contracts", [])
        ),
        column_mappings=tuple(
            ColumnMappingRecord(
                column_mapping_id=item["column_mapping_id"],
                source_system_id=item["source_system_id"],
                dataset_contract_id=item["dataset_contract_id"],
                version=item["version"],
                rules=tuple(
                    ColumnMappingRule(
                        target_column=rule["target_column"],
                        source_column=rule.get("source_column"),
                        default_value=rule.get("default_value"),
                    )
                    for rule in item["rules"]
                ),
                archived=item.get("archived", False),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("column_mappings", [])
        ),
        transformation_packages=tuple(
            TransformationPackageRecord(
                transformation_package_id=item["transformation_package_id"],
                name=item["name"],
                handler_key=item["handler_key"],
                version=item["version"],
                description=item.get("description"),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("transformation_packages", [])
        ),
        publication_definitions=tuple(
            PublicationDefinitionRecord(
                publication_definition_id=item["publication_definition_id"],
                transformation_package_id=item["transformation_package_id"],
                publication_key=item["publication_key"],
                name=item["name"],
                description=item.get("description"),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("publication_definitions", [])
        ),
        source_assets=tuple(
            SourceAssetRecord(
                source_asset_id=item["source_asset_id"],
                source_system_id=item["source_system_id"],
                dataset_contract_id=item["dataset_contract_id"],
                column_mapping_id=item["column_mapping_id"],
                transformation_package_id=item.get("transformation_package_id"),
                name=item["name"],
                asset_type=item["asset_type"],
                description=item.get("description"),
                enabled=item.get("enabled", True),
                archived=item.get("archived", False),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("source_assets", [])
        ),
        ingestion_definitions=tuple(
            IngestionDefinitionRecord(
                ingestion_definition_id=item["ingestion_definition_id"],
                source_asset_id=item["source_asset_id"],
                transport=item["transport"],
                schedule_mode=item["schedule_mode"],
                source_path=item["source_path"],
                file_pattern=item["file_pattern"],
                processed_path=item.get("processed_path"),
                failed_path=item.get("failed_path"),
                poll_interval_seconds=item.get("poll_interval_seconds"),
                request_url=item.get("request_url"),
                request_method=item.get("request_method"),
                request_headers=tuple(
                    RequestHeaderSecretRef(
                        name=header["name"],
                        secret_name=header["secret_name"],
                        secret_key=header["secret_key"],
                    )
                    for header in item.get("request_headers", [])
                ),
                request_timeout_seconds=item.get("request_timeout_seconds"),
                response_format=item.get("response_format"),
                output_file_name=item.get("output_file_name"),
                enabled=item["enabled"],
                archived=item.get("archived", False),
                source_name=item.get("source_name"),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("ingestion_definitions", [])
        ),
        execution_schedules=tuple(
            ExecutionScheduleRecord(
                schedule_id=item["schedule_id"],
                target_kind=item["target_kind"],
                target_ref=item["target_ref"],
                cron_expression=item["cron_expression"],
                timezone=item["timezone"],
                enabled=item["enabled"],
                archived=item.get("archived", False),
                max_concurrency=item["max_concurrency"],
                next_due_at=(
                    datetime.fromisoformat(item["next_due_at"])
                    if item.get("next_due_at")
                    else None
                ),
                last_enqueued_at=(
                    datetime.fromisoformat(item["last_enqueued_at"])
                    if item.get("last_enqueued_at")
                    else None
                ),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in payload.get("execution_schedules", [])
        ),
        source_lineage=tuple(
            SourceLineageRecord(
                lineage_id=item["lineage_id"],
                input_run_id=item.get("input_run_id"),
                target_layer=item["target_layer"],
                target_name=item["target_name"],
                target_kind=item["target_kind"],
                row_count=item.get("row_count"),
                source_system=item.get("source_system"),
                source_run_id=item.get("source_run_id"),
                recorded_at=datetime.fromisoformat(item["recorded_at"]),
            )
            for item in payload.get("source_lineage", [])
        ),
        publication_audit=tuple(
            PublicationAuditRecord(
                publication_audit_id=item["publication_audit_id"],
                run_id=item.get("run_id"),
                publication_key=item["publication_key"],
                relation_name=item["relation_name"],
                status=item["status"],
                published_at=datetime.fromisoformat(item["published_at"]),
            )
            for item in payload.get("publication_audit", [])
        ),
        auth_audit_events=tuple(
            AuthAuditEventRecord(
                event_id=item["event_id"],
                event_type=item["event_type"],
                success=item["success"],
                actor_user_id=item.get("actor_user_id"),
                actor_username=item.get("actor_username"),
                subject_user_id=item.get("subject_user_id"),
                subject_username=item.get("subject_username"),
                remote_addr=item.get("remote_addr"),
                user_agent=item.get("user_agent"),
                detail=item.get("detail"),
                occurred_at=datetime.fromisoformat(item["occurred_at"]),
            )
            for item in payload.get("auth_audit_events", [])
        ),
        local_users=tuple(
            LocalUserRecord(
                user_id=item["user_id"],
                username=item["username"],
                password_hash=item["password_hash"],
                role=UserRole(item["role"]),
                enabled=item["enabled"],
                created_at=datetime.fromisoformat(item["created_at"]),
                last_login_at=(
                    datetime.fromisoformat(item["last_login_at"])
                    if item.get("last_login_at")
                    else None
                ),
            )
            for item in payload.get("local_users", [])
        ),
        service_tokens=tuple(
            ServiceTokenRecord(
                token_id=item["token_id"],
                token_name=item["token_name"],
                token_secret_hash=item["token_secret_hash"],
                role=UserRole(item["role"]),
                scopes=tuple(item["scopes"]),
                expires_at=(
                    datetime.fromisoformat(item["expires_at"])
                    if item.get("expires_at")
                    else None
                ),
                created_at=datetime.fromisoformat(item["created_at"]),
                last_used_at=(
                    datetime.fromisoformat(item["last_used_at"])
                    if item.get("last_used_at")
                    else None
                ),
                revoked_at=(
                    datetime.fromisoformat(item["revoked_at"])
                    if item.get("revoked_at")
                    else None
                ),
            )
            for item in payload.get("service_tokens", [])
        ),
    )
