from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime

from packages.storage.auth_store import (
    ServiceTokenRecord,
    UserRole,
    normalize_service_token_scopes,
)
from packages.storage.control_plane import (
    AuthAuditEventRecord,
    PublicationAuditRecord,
    ScheduleDispatchRecord,
    SourceLineageRecord,
    WorkerHeartbeatRecord,
)


def _build_stale_dispatch_failure_reason(
    dispatch: ScheduleDispatchRecord,
    *,
    recovered_at: datetime,
    recovered_by_worker_id: str | None = None,
) -> str:
    detail = (
        "Dispatch claim expired at "
        f"{dispatch.claim_expires_at.isoformat() if dispatch.claim_expires_at else 'unknown'} "
        f"and was requeued at {recovered_at.isoformat()}"
    )
    if recovered_by_worker_id:
        detail += f" by worker {recovered_by_worker_id}"
    return detail


def _build_stale_dispatch_worker_detail(
    dispatch: ScheduleDispatchRecord,
    *,
    recovered_at: datetime,
    recovered_by_worker_id: str | None = None,
) -> str:
    return json.dumps(
        {
            "dispatch_id": dispatch.dispatch_id,
            "schedule_id": dispatch.schedule_id,
            "target_kind": dispatch.target_kind,
            "target_ref": dispatch.target_ref,
            "state": "failed",
            "recovery_state": "requeued",
            "recovered_at": recovered_at.isoformat(),
            "recovered_by_worker_id": recovered_by_worker_id,
            "previous_worker_id": dispatch.claimed_by_worker_id,
            "previous_claimed_at": (
                dispatch.claimed_at.isoformat() if dispatch.claimed_at is not None else None
            ),
            "previous_claim_expires_at": (
                dispatch.claim_expires_at.isoformat()
                if dispatch.claim_expires_at is not None
                else None
            ),
        },
        sort_keys=True,
    )


def _build_requeued_dispatch_worker_detail(
    dispatch: ScheduleDispatchRecord,
    *,
    recovered_at: datetime,
    recovered_by_worker_id: str | None = None,
) -> str:
    return json.dumps(
        {
            "state": "enqueued",
            "recovery_state": "requeued",
            "recovered_from_dispatch_id": dispatch.dispatch_id,
            "recovered_at": recovered_at.isoformat(),
            "recovered_by_worker_id": recovered_by_worker_id,
            "previous_worker_id": dispatch.claimed_by_worker_id,
        },
        sort_keys=True,
    )


def _coerce_datetime_value(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise TypeError(f"Unsupported datetime value: {value!r}")
    return datetime.fromisoformat(value)


def _coerce_int_value(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def _coerce_string_sequence(value: object) -> tuple[str, ...] | list[str]:
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError(f"Unsupported string sequence value: {value!r}")


def _deserialize_schedule_dispatch_row(
    row: Mapping[str, object],
) -> ScheduleDispatchRecord:
    return ScheduleDispatchRecord(
        dispatch_id=str(row["dispatch_id"]),
        schedule_id=str(row["schedule_id"]),
        target_kind=str(row["target_kind"]),
        target_ref=str(row["target_ref"]),
        enqueued_at=_coerce_datetime_value(row["enqueued_at"]) or datetime.min,
        status=str(row["status"]),
        started_at=_coerce_datetime_value(row["started_at"]),
        completed_at=_coerce_datetime_value(row["completed_at"]),
        run_ids=tuple(json.loads(str(row["run_ids_json"] or "[]"))),
        failure_reason=str(row["failure_reason"]) if row["failure_reason"] is not None else None,
        worker_detail=str(row["worker_detail"]) if row["worker_detail"] is not None else None,
        claimed_by_worker_id=(
            str(row["claimed_by_worker_id"])
            if row["claimed_by_worker_id"] is not None
            else None
        ),
        claimed_at=_coerce_datetime_value(row["claimed_at"]),
        claim_expires_at=_coerce_datetime_value(row["claim_expires_at"]),
    )


def _deserialize_worker_heartbeat_row(
    row: Mapping[str, object],
) -> WorkerHeartbeatRecord:
    observed_at = _coerce_datetime_value(row["observed_at"])
    assert observed_at is not None
    return WorkerHeartbeatRecord(
        worker_id=str(row["worker_id"]),
        status=str(row["status"]),
        active_dispatch_id=(
            str(row["active_dispatch_id"])
            if row["active_dispatch_id"] is not None
            else None
        ),
        detail=str(row["detail"]) if row["detail"] is not None else None,
        observed_at=observed_at,
    )


def _deserialize_source_lineage_row(
    row: Mapping[str, object],
) -> SourceLineageRecord:
    recorded_at = _coerce_datetime_value(row["recorded_at"])
    assert recorded_at is not None
    return SourceLineageRecord(
        lineage_id=str(row["lineage_id"]),
        input_run_id=str(row["input_run_id"]) if row["input_run_id"] is not None else None,
        target_layer=str(row["target_layer"]),
        target_name=str(row["target_name"]),
        target_kind=str(row["target_kind"]),
        row_count=_coerce_int_value(row["row_count"]),
        source_system=(
            str(row["source_system"]) if row["source_system"] is not None else None
        ),
        source_run_id=(
            str(row["source_run_id"]) if row["source_run_id"] is not None else None
        ),
        recorded_at=recorded_at,
    )


def _deserialize_publication_audit_row(
    row: Mapping[str, object],
) -> PublicationAuditRecord:
    published_at = _coerce_datetime_value(row["published_at"])
    assert published_at is not None
    return PublicationAuditRecord(
        publication_audit_id=str(row["publication_audit_id"]),
        run_id=str(row["run_id"]) if row["run_id"] is not None else None,
        publication_key=str(row["publication_key"]),
        relation_name=str(row["relation_name"]),
        status=str(row["status"]),
        published_at=published_at,
    )


def _deserialize_auth_audit_event_row(
    row: Mapping[str, object],
) -> AuthAuditEventRecord:
    occurred_at = _coerce_datetime_value(row["occurred_at"])
    assert occurred_at is not None
    return AuthAuditEventRecord(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        success=bool(row["success"]),
        actor_user_id=(
            str(row["actor_user_id"]) if row["actor_user_id"] is not None else None
        ),
        actor_username=(
            str(row["actor_username"]) if row["actor_username"] is not None else None
        ),
        subject_user_id=(
            str(row["subject_user_id"]) if row["subject_user_id"] is not None else None
        ),
        subject_username=(
            str(row["subject_username"]) if row["subject_username"] is not None else None
        ),
        remote_addr=str(row["remote_addr"]) if row["remote_addr"] is not None else None,
        user_agent=str(row["user_agent"]) if row["user_agent"] is not None else None,
        detail=str(row["detail"]) if row["detail"] is not None else None,
        occurred_at=occurred_at,
    )


def _deserialize_service_token_row(
    row: Mapping[str, object],
) -> ServiceTokenRecord:
    raw_scopes = row["scopes_json"]
    decoded_scopes = json.loads(raw_scopes) if isinstance(raw_scopes, str) else raw_scopes
    created_at = _coerce_datetime_value(row["created_at"])
    assert created_at is not None
    return ServiceTokenRecord(
        token_id=str(row["token_id"]),
        token_name=str(row["token_name"]),
        token_secret_hash=str(row["token_secret_hash"]),
        role=UserRole(str(row["role"])),
        scopes=normalize_service_token_scopes(_coerce_string_sequence(decoded_scopes)),
        expires_at=_coerce_datetime_value(row["expires_at"]),
        created_at=created_at,
        last_used_at=_coerce_datetime_value(row["last_used_at"]),
        revoked_at=_coerce_datetime_value(row["revoked_at"]),
    )
