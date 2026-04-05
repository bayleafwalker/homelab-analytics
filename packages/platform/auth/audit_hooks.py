"""Auth event recording and lockout checking."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from fastapi import Request

from packages.platform.auth.credential_resolution import request_remote_addr
from packages.storage.control_plane import AuthAuditEventCreate, ControlPlaneStore


def build_auth_event_recorder(
    config_repository: ControlPlaneStore,
) -> Callable[..., None]:
    def record_auth_event(
        request: Request,
        *,
        event_type: str,
        success: bool,
        actor: Any = None,
        subject_user_id: str | None = None,
        subject_username: str | None = None,
        detail: str | None = None,
    ) -> None:
        config_repository.record_auth_audit_events(
            (
                AuthAuditEventCreate(
                    event_id=uuid.uuid4().hex,
                    event_type=event_type,
                    success=success,
                    actor_user_id=actor.user_id if actor else None,
                    actor_username=actor.username if actor else None,
                    subject_user_id=subject_user_id,
                    subject_username=subject_username,
                    remote_addr=request_remote_addr(request),
                    user_agent=request.headers.get("user-agent"),
                    detail=detail,
                ),
            )
        )

    return record_auth_event


def build_lockout_checker(
    config_repository: ControlPlaneStore,
    *,
    auth_failure_window_seconds: int,
    auth_failure_threshold: int,
    auth_lockout_seconds: int,
) -> Callable[[str, datetime], datetime | None]:
    def locked_out_until(username: str, now: datetime) -> datetime | None:
        recent_events = config_repository.list_auth_audit_events(
            subject_username=username,
            since=now - timedelta(seconds=auth_failure_window_seconds),
            limit=max(auth_failure_threshold * 4, 20),
        )
        consecutive_failures = 0
        latest_failure_at: datetime | None = None
        for event in recent_events:
            if event.event_type == "login_succeeded" and event.success:
                break
            if event.event_type not in {"login_failed", "login_blocked"}:
                continue
            if event.success:
                continue
            consecutive_failures += 1
            if latest_failure_at is None:
                latest_failure_at = event.occurred_at
        if latest_failure_at is None or consecutive_failures < auth_failure_threshold:
            return None
        candidate = latest_failure_at + timedelta(seconds=auth_lockout_seconds)
        if candidate <= now:
            return None
        return candidate

    return locked_out_until
