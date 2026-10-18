"""Scheduled, retained backup bundles under a single destination root.

The running worker owns the schedule (``watch-schedule-dispatches`` calls
:func:`run_scheduled_backup` between dispatches, when it holds no warehouse
connection), so a backup never races the worker's own ingestion or promotion.
Cross-process exclusion still comes from :func:`create_backup`: the DuckDB
capture holds a read-only connection, which DuckDB refuses while another
process owns the write lock and which blocks writers while the copy runs.

Layout of ``destination_root``::

    backup-<UTC stamp>/        complete, verified bundles (manifest.json inside)
    .staging-<stamp>-<id>/     a bundle being written; never shipped or pruned
    backup-status.json         last attempt/success/failure, read by /metrics
    .backup.lock               advisory lock: one scheduled backup at a time

A bundle directory only appears under its final ``backup-`` name after
:func:`verify_backup` passed on the staged copy (atomic ``rename``), so an
off-site shipper may treat every ``backup-*`` directory as complete.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.storage.backup_bundle import (
    MANIFEST_FILENAME,
    BackupError,
    BackupSources,
    create_backup,
    verify_backup,
)

__all__ = [
    "BACKUP_STATUS_FILENAME",
    "BUNDLE_PREFIX",
    "BackupSchedulePolicy",
    "BackupStatus",
    "ScheduledBackupResult",
    "backup_due",
    "list_bundles",
    "prune_bundles",
    "read_backup_status",
    "run_scheduled_backup",
]

BACKUP_STATUS_FILENAME = "backup-status.json"
BUNDLE_PREFIX = "backup-"
STAGING_PREFIX = ".staging-"
LOCK_FILENAME = ".backup.lock"
# After a failure, retry no sooner than this (or the interval, if shorter) so a
# persistent blocker does not turn every idle poll into a backup attempt.
FAILURE_RETRY_SECONDS = 900


@dataclass(frozen=True)
class BackupSchedulePolicy:
    destination_root: Path
    interval_seconds: int
    retention_count: int

    @property
    def enabled(self) -> bool:
        return self.interval_seconds > 0


@dataclass(frozen=True)
class BackupStatus:
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_error: str | None = None
    last_bundle: str | None = None
    last_duration_seconds: float | None = None
    last_size_bytes: int | None = None
    consecutive_failures: int = 0
    successes_total: int = 0
    failures_total: int = 0
    bundles_retained: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BackupStatus:
        known = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in payload.items() if key in known})


@dataclass(frozen=True)
class ScheduledBackupResult:
    succeeded: bool
    status: BackupStatus
    bundle_dir: Path | None = None
    pruned: list[Path] = field(default_factory=list)
    error: str | None = None


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def read_backup_status(destination_root: Path) -> BackupStatus | None:
    path = destination_root / BACKUP_STATUS_FILENAME
    try:
        payload = json.loads(path.read_text())
    except (FileNotFoundError, NotADirectoryError):
        return None
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return BackupStatus.from_dict(payload)


def _write_status(destination_root: Path, status: BackupStatus) -> None:
    target = destination_root / BACKUP_STATUS_FILENAME
    tmp = destination_root / f".{BACKUP_STATUS_FILENAME}.{uuid.uuid4().hex}.tmp"
    tmp.write_text(json.dumps(status.as_dict(), indent=2, sort_keys=True) + "\n")
    os.replace(tmp, target)


def backup_due(
    policy: BackupSchedulePolicy,
    status: BackupStatus | None,
    *,
    now: datetime,
) -> bool:
    if not policy.enabled:
        return False
    if status is None:
        return True
    last_success = _parse_iso(status.last_success_at)
    if last_success is not None and (now - last_success).total_seconds() < policy.interval_seconds:
        return False
    last_failure = _parse_iso(status.last_failure_at)
    if last_failure is not None and (last_success is None or last_failure > last_success):
        retry_after = min(policy.interval_seconds, FAILURE_RETRY_SECONDS)
        if (now - last_failure).total_seconds() < retry_after:
            return False
    return True


def list_bundles(destination_root: Path) -> list[Path]:
    """Complete bundles, oldest first (stamps sort lexically by time)."""
    if not destination_root.is_dir():
        return []
    return sorted(
        path
        for path in destination_root.iterdir()
        if path.is_dir()
        and not path.is_symlink()
        and path.name.startswith(BUNDLE_PREFIX)
        and (path / MANIFEST_FILENAME).is_file()
    )


def prune_bundles(destination_root: Path, retention_count: int) -> list[Path]:
    """Delete the oldest complete bundles beyond ``retention_count``."""
    if retention_count < 1:
        raise BackupError("Backup retention must keep at least one bundle.")
    bundles = list_bundles(destination_root)
    doomed = bundles[: max(0, len(bundles) - retention_count)]
    for bundle in doomed:
        shutil.rmtree(bundle)
    return doomed


def _bundle_size(bundle: Path) -> int:
    return sum(path.stat().st_size for path in bundle.rglob("*") if path.is_file())


@contextmanager
def _exclusive_lock(destination_root: Path) -> Iterator[None]:
    handle = (destination_root / LOCK_FILENAME).open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BackupError("Another scheduled backup is already running.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _validate_destination(sources: BackupSources, destination_root: Path) -> None:
    root = destination_root.resolve()
    landing = sources.landing_root.resolve()
    if root == landing or landing in root.parents:
        raise BackupError(
            f"Backup destination {destination_root} is inside the landing root; "
            "bundles would be captured into later bundles."
        )


def run_scheduled_backup(
    sources: BackupSources,
    policy: BackupSchedulePolicy,
    *,
    now: datetime | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    create: Callable[..., dict[str, Any]] = create_backup,
) -> ScheduledBackupResult:
    """Stage, verify, publish, and prune one bundle; record the outcome.

    Never raises for an expected failure (warehouse locked by another process,
    disk full, verification mismatch): the failure is written to
    ``backup-status.json`` and returned, so the worker loop keeps running.
    """
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    root = policy.destination_root
    root.mkdir(parents=True, exist_ok=True)
    previous = read_backup_status(root) or BackupStatus()
    started = monotonic()
    staging: Path | None = None
    try:
        _validate_destination(sources, root)
        with _exclusive_lock(root):
            for stale in root.glob(f"{STAGING_PREFIX}*"):
                shutil.rmtree(stale, ignore_errors=True)
            stamp = moment.strftime("%Y%m%dT%H%M%SZ")
            staging = root / f"{STAGING_PREFIX}{stamp}-{uuid.uuid4().hex[:8]}"
            create(sources, staging, now=moment)
            verification = verify_backup(staging)
            if not verification.passed:
                raise BackupError(
                    "Staged bundle failed verification: " + "; ".join(verification.errors)
                )
            final = root / f"{BUNDLE_PREFIX}{stamp}"
            suffix = 1
            while final.exists():
                final = root / f"{BUNDLE_PREFIX}{stamp}-{suffix}"
                suffix += 1
            os.rename(staging, final)
            staging = None
            pruned = prune_bundles(root, policy.retention_count)
            status = BackupStatus(
                last_attempt_at=_iso(moment),
                last_success_at=_iso(moment),
                last_failure_at=previous.last_failure_at,
                last_error=None,
                last_bundle=final.name,
                last_duration_seconds=round(monotonic() - started, 3),
                last_size_bytes=_bundle_size(final),
                consecutive_failures=0,
                successes_total=previous.successes_total + 1,
                failures_total=previous.failures_total,
                bundles_retained=len(list_bundles(root)),
            )
            _write_status(root, status)
            return ScheduledBackupResult(
                succeeded=True, status=status, bundle_dir=final, pruned=pruned
            )
    except (BackupError, OSError) as exc:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        status = BackupStatus(
            last_attempt_at=_iso(moment),
            last_success_at=previous.last_success_at,
            last_failure_at=_iso(moment),
            last_error=str(exc),
            last_bundle=previous.last_bundle,
            last_duration_seconds=round(monotonic() - started, 3),
            last_size_bytes=previous.last_size_bytes,
            consecutive_failures=previous.consecutive_failures + 1,
            successes_total=previous.successes_total,
            failures_total=previous.failures_total + 1,
            bundles_retained=len(list_bundles(root)),
        )
        try:
            _write_status(root, status)
        except OSError:
            pass
        return ScheduledBackupResult(succeeded=False, status=status, error=str(exc))
