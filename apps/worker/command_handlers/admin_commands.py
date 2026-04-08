"""Admin worker command handlers (users, tokens, control-plane, config)."""
from __future__ import annotations

import json
import uuid
from argparse import Namespace
from datetime import datetime
from pathlib import Path

from apps.api.app import serialize_run
from apps.worker.runtime import WorkerRuntime
from apps.worker.serialization import (
    _control_plane_snapshot_from_dict,
    _control_plane_snapshot_to_dict,
    _json_default,
    _write_json,
)
from packages.pipelines.config_preflight import run_config_preflight
from packages.platform.auth.contracts import UserRole
from packages.platform.auth.crypto import hash_password, issue_service_token
from packages.platform.auth.serialization import serialize_service_token, serialize_user
from packages.storage.auth_store import LocalUserCreate, ServiceTokenCreate


def handle_list_runs(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"runs": [serialize_run(run) for run in runtime.service.list_runs()]},
    )
    return 0


def handle_list_ingestion_definitions(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"ingestion_definitions": runtime.config_repository.list_ingestion_definitions()},
    )
    return 0


def handle_list_execution_schedules(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"execution_schedules": runtime.config_repository.list_execution_schedules()},
    )
    return 0


def handle_list_local_users(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"users": [serialize_user(user) for user in runtime.config_repository.list_local_users()]},
    )
    return 0


def handle_list_service_tokens(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {
            "service_tokens": [
                serialize_service_token(token)
                for token in runtime.config_repository.list_service_tokens(
                    include_revoked=getattr(args, "include_revoked", False)
                )
            ]
        },
    )
    return 0


def handle_create_local_admin_user(args: Namespace, runtime: WorkerRuntime) -> int:
    user = runtime.config_repository.create_local_user(
        LocalUserCreate(
            user_id=f"user-{args.username}",
            username=args.username,
            password_hash=hash_password(args.password),
            role=UserRole.ADMIN,
        )
    )
    _write_json(runtime.output, {"user": serialize_user(user)})
    return 0


def handle_create_service_token(args: Namespace, runtime: WorkerRuntime) -> int:
    expires_at = (
        datetime.fromisoformat(args.expires_at) if getattr(args, "expires_at", "") else None
    )
    issued_token = issue_service_token(f"token-{uuid.uuid4().hex}")
    token = runtime.config_repository.create_service_token(
        ServiceTokenCreate(
            token_id=issued_token.token_id,
            token_name=args.token_name,
            token_secret_hash=issued_token.token_secret_hash,
            role=UserRole(args.role),
            scopes=tuple(args.scope),
            expires_at=expires_at,
        )
    )
    _write_json(
        runtime.output,
        {
            "service_token": serialize_service_token(token),
            "token_value": issued_token.token_value,
        },
    )
    return 0


def handle_reset_local_user_password(args: Namespace, runtime: WorkerRuntime) -> int:
    user = runtime.config_repository.get_local_user_by_username(args.username)
    updated_user = runtime.config_repository.update_local_user_password(
        user.user_id,
        password_hash=hash_password(args.password),
    )
    _write_json(runtime.output, {"user": serialize_user(updated_user)})
    return 0


def handle_revoke_service_token(args: Namespace, runtime: WorkerRuntime) -> int:
    token = runtime.config_repository.revoke_service_token(args.token_id)
    _write_json(runtime.output, {"service_token": serialize_service_token(token)})
    return 0


def handle_export_control_plane(args: Namespace, runtime: WorkerRuntime) -> int:
    snapshot = runtime.config_repository.export_snapshot()
    destination = Path(args.output_path)
    destination.write_text(
        json.dumps(
            _control_plane_snapshot_to_dict(snapshot),
            default=_json_default,
            indent=2,
        )
    )
    _write_json(
        runtime.output,
        {
            "output_path": str(destination),
            "snapshot": {
                "source_systems": len(snapshot.source_systems),
                "dataset_contracts": len(snapshot.dataset_contracts),
                "column_mappings": len(snapshot.column_mappings),
                "source_assets": len(snapshot.source_assets),
                "ingestion_definitions": len(snapshot.ingestion_definitions),
                "extension_registry_sources": len(snapshot.extension_registry_sources),
                "extension_registry_revisions": len(snapshot.extension_registry_revisions),
                "extension_registry_activations": len(
                    snapshot.extension_registry_activations
                ),
                "execution_schedules": len(snapshot.execution_schedules),
                "source_lineage": len(snapshot.source_lineage),
                "publication_audit": len(snapshot.publication_audit),
                "auth_audit_events": len(snapshot.auth_audit_events),
                "local_users": len(snapshot.local_users),
                "service_tokens": len(snapshot.service_tokens),
            },
        },
    )
    return 0


def handle_import_control_plane(args: Namespace, runtime: WorkerRuntime) -> int:
    source = Path(args.input_path)
    snapshot = _control_plane_snapshot_from_dict(json.loads(source.read_text()))
    runtime.config_repository.import_snapshot(snapshot)
    _write_json(
        runtime.output,
        {
            "input_path": str(source),
            "imported": True,
        },
    )
    return 0


def handle_verify_config(args: Namespace, runtime: WorkerRuntime) -> int:
    report = run_config_preflight(
        runtime.config_repository,
        extension_registry=runtime.extension_registry,
        function_registry=runtime.function_registry,
        promotion_handler_registry=runtime.promotion_handler_registry,
        source_asset_id=getattr(args, "source_asset_id", None) or None,
        ingestion_definition_id=(getattr(args, "ingestion_definition_id", None) or None),
    )
    _write_json(runtime.output, {"report": report})
    return 0 if report.passed else 1
