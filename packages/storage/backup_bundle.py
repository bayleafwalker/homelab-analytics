"""Application-level backup bundles for local stores.

A backup bundle is a directory containing a ``manifest.json`` plus copies of
the file-backed stores an instance depends on:

- the SQLite control plane (``config.db``, which also holds SQLite run
  metadata), captured through the SQLite online-backup API;
- the DuckDB warehouse file (plus its WAL when present), captured while a
  read-only connection holds the file lock so no writer can attach;
- filesystem landing payloads under ``landing_root``.

Postgres-backed stores and S3 landing are *not* captured: they are recorded in
the manifest as excluded components with the reason, because the deployed
instance already covers them with ``pg_dump`` (CNPG) and object-storage
mirroring.

The manifest records a SHA-256 checksum and size for every file plus the
migration head of every schema track the running code ships. Verification
refuses a bundle whose checksums or schema heads do not match, and restore
refuses to overwrite non-empty targets unless explicitly forced.

No settings values (DSNs, S3 credentials, tokens, passwords) are written into
the manifest: only backend names and the landing-root path. The SQLite control
plane stores secret *references* (``auth_secret_name``/``auth_secret_key``) and
password/token *hashes*, never plaintext secret values.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import duckdb

from packages.storage.blob import PARTIAL_WRITE_SUFFIX
from packages.storage.duckdb_store import WarehouseBusyError, connect_with_lock_retry
from packages.storage.migration_runner import resolve_migrations_dir

__all__ = [
    "BACKUP_FORMAT",
    "BACKUP_FORMAT_VERSION",
    "BackupError",
    "BackupSources",
    "BackupVerification",
    "MANIFEST_FILENAME",
    "create_backup",
    "current_schema_heads",
    "restore_backup",
    "verify_backup",
]

BACKUP_FORMAT = "homelab-analytics-backup"
BACKUP_FORMAT_VERSION = 1
MANIFEST_FILENAME = "manifest.json"

SCHEMA_TRACKS: tuple[str, ...] = ("sqlite", "duckdb", "postgres", "postgres_run_metadata")

COMPONENT_CONTROL_PLANE_SQLITE = "control_plane_sqlite"
COMPONENT_WAREHOUSE_DUCKDB = "warehouse_duckdb"
COMPONENT_LANDING_FILESYSTEM = "landing_filesystem"
COMPONENT_CONTROL_PLANE_POSTGRES = "control_plane_postgres"
COMPONENT_REPORTING_POSTGRES = "reporting_postgres"
COMPONENT_LANDING_S3 = "landing_s3"

# Which schema track gates restore of each restorable component.
_COMPONENT_SCHEMA_TRACK: dict[str, str] = {
    COMPONENT_CONTROL_PLANE_SQLITE: "sqlite",
    COMPONENT_WAREHOUSE_DUCKDB: "duckdb",
}

_CHUNK_SIZE = 1024 * 1024
# 0.5 + 1 + 2 + 4 s: outlasts an API read session or a short worker promotion.
WAREHOUSE_LOCK_RETRY_ATTEMPTS = 5
WAREHOUSE_LOCK_RETRY_BACKOFF_SECONDS = 0.5


class BackupError(RuntimeError):
    """Raised when a backup cannot be created, verified, or restored safely."""


@dataclass(frozen=True)
class BackupSources:
    """Backend-neutral description of what an instance stores and where.

    Built from settings by the caller so this module stays independent of the
    settings object and never sees DSNs or credentials.
    """

    control_plane_backend: str
    reporting_backend: str
    blob_backend: str
    control_plane_database_path: Path
    warehouse_database_path: Path
    landing_root: Path


@dataclass
class BackupVerification:
    backup_dir: Path
    errors: list[str] = field(default_factory=list)
    manifest: dict[str, Any] | None = None

    @property
    def passed(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        manifest = self.manifest or {}
        return {
            "backup_dir": str(self.backup_dir),
            "passed": self.passed,
            "errors": list(self.errors),
            "created_at": manifest.get("created_at"),
            "schema_heads": manifest.get("schema_heads"),
            "components": [
                {
                    "name": component.get("name"),
                    "included": component.get("included"),
                    "files": len(component.get("files", [])),
                    **(
                        {"reason": component["reason"]}
                        if "reason" in component
                        else {}
                    ),
                }
                for component in manifest.get("components", [])
            ],
        }


# ---------------------------------------------------------------------------
# Schema heads
# ---------------------------------------------------------------------------


def current_schema_heads(
    migrations_root: Path | None = None,
) -> dict[str, str | None]:
    """Return the latest migration version per track shipped with this code."""
    heads: dict[str, str | None] = {}
    for track in SCHEMA_TRACKS:
        if migrations_root is not None:
            track_dir = migrations_root / track
        else:
            try:
                track_dir = resolve_migrations_dir(track, anchor_file=Path(__file__))
            except FileNotFoundError:
                heads[track] = None
                continue
        versions = sorted(path.stem for path in track_dir.glob("*.sql"))
        heads[track] = versions[-1] if versions else None
    return heads


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_backup(
    sources: BackupSources,
    destination: Path,
    *,
    schema_heads: Mapping[str, str | None] | None = None,
    now: datetime | None = None,
    lock_retry_attempts: int = WAREHOUSE_LOCK_RETRY_ATTEMPTS,
    lock_retry_backoff_seconds: float = WAREHOUSE_LOCK_RETRY_BACKOFF_SECONDS,
) -> dict[str, Any]:
    """Write a backup bundle to ``destination`` and return its manifest.

    ``destination`` must not exist or must be an empty directory.
    """
    if destination.exists():
        if not destination.is_dir():
            raise BackupError(f"Backup destination is not a directory: {destination}")
        if any(destination.iterdir()):
            raise BackupError(
                f"Backup destination is not empty: {destination}. "
                "Choose a new directory per backup."
            )
    destination.mkdir(parents=True, exist_ok=True)

    components: list[dict[str, Any]] = [
        _backup_control_plane(sources, destination),
        _backup_warehouse(
            sources,
            destination,
            lock_retry_attempts=lock_retry_attempts,
            lock_retry_backoff_seconds=lock_retry_backoff_seconds,
        ),
        _backup_landing(sources, destination),
    ]
    if sources.reporting_backend.lower() == "postgres":
        components.append(
            _excluded(
                COMPONENT_REPORTING_POSTGRES,
                "Postgres reporting schema is covered by pg_dump, not app backups.",
            )
        )

    created_at = (now or datetime.now(UTC)).astimezone(UTC)
    manifest: dict[str, Any] = {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
        "schema_heads": dict(
            schema_heads if schema_heads is not None else current_schema_heads()
        ),
        "source": {
            "control_plane_backend": sources.control_plane_backend,
            "reporting_backend": sources.reporting_backend,
            "blob_backend": sources.blob_backend,
            "landing_root": str(sources.landing_root),
        },
        "components": components,
    }
    (destination / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def _excluded(name: str, reason: str) -> dict[str, Any]:
    return {"name": name, "included": False, "reason": reason, "files": []}


def _backup_control_plane(sources: BackupSources, destination: Path) -> dict[str, Any]:
    backend = sources.control_plane_backend.lower()
    if backend != "sqlite":
        return _excluded(
            COMPONENT_CONTROL_PLANE_POSTGRES,
            "Postgres control plane and run metadata are covered by pg_dump "
            "(CNPG backup CronJob); use export-control-plane for a portable snapshot.",
        )
    source_path = sources.control_plane_database_path
    if not source_path.exists():
        return _excluded(
            COMPONENT_CONTROL_PLANE_SQLITE,
            "SQLite control-plane database does not exist yet.",
        )
    relative = "control_plane/config.db"
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        target_connection = sqlite3.connect(target)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
    finally:
        source_connection.close()
    return {
        "name": COMPONENT_CONTROL_PLANE_SQLITE,
        "included": True,
        "files": [_file_entry(destination, relative)],
    }


def _backup_warehouse(
    sources: BackupSources,
    destination: Path,
    *,
    lock_retry_attempts: int = WAREHOUSE_LOCK_RETRY_ATTEMPTS,
    lock_retry_backoff_seconds: float = WAREHOUSE_LOCK_RETRY_BACKOFF_SECONDS,
) -> dict[str, Any]:
    source_path = sources.warehouse_database_path
    if not source_path.exists():
        return _excluded(
            COMPONENT_WAREHOUSE_DUCKDB,
            "DuckDB warehouse file does not exist yet.",
        )
    try:
        # A read-only connection fails while another process holds the write
        # lock and blocks writers from attaching while the copy runs. Writers
        # hold the lock only briefly (API sessions, worker promotions), so a
        # conflict is retried with backoff before the backup gives up.
        guard = connect_with_lock_retry(
            str(source_path),
            read_only=True,
            attempts=lock_retry_attempts,
            backoff_seconds=lock_retry_backoff_seconds,
        )
    except (duckdb.Error, WarehouseBusyError) as exc:
        raise BackupError(
            f"Could not open DuckDB warehouse read-only ({exc}). "
            "A writer held the warehouse lock for the whole retry window. "
            "Stop worker and API processes that hold the warehouse, or let the "
            "running worker take a scheduled backup."
        ) from exc
    try:
        files = []
        relative = "warehouse/warehouse.duckdb"
        (destination / "warehouse").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination / relative)
        files.append(_file_entry(destination, relative))
        wal_path = source_path.with_name(source_path.name + ".wal")
        if wal_path.exists():
            wal_relative = "warehouse/warehouse.duckdb.wal"
            shutil.copyfile(wal_path, destination / wal_relative)
            files.append(_file_entry(destination, wal_relative))
    finally:
        guard.close()
    return {"name": COMPONENT_WAREHOUSE_DUCKDB, "included": True, "files": files}


def _backup_landing(sources: BackupSources, destination: Path) -> dict[str, Any]:
    if sources.blob_backend.lower() != "filesystem":
        return _excluded(
            COMPONENT_LANDING_S3,
            "Object-storage landing is not copied; mirror the bucket prefix with "
            "aws s3 sync or mc mirror.",
        )
    root = sources.landing_root
    files: list[dict[str, Any]] = []
    if root.is_dir():
        for source_file in sorted(_iter_regular_files(root)):
            relative_to_root = source_file.relative_to(root).as_posix()
            relative = f"landing/{relative_to_root}"
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, target)
            files.append(_file_entry(destination, relative))
    return {"name": COMPONENT_LANDING_FILESYSTEM, "included": True, "files": files}


def _iter_regular_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [name for name in dirnames if not (current / name).is_symlink()]
        for name in filenames:
            candidate = current / name
            if candidate.is_symlink() or not candidate.is_file():
                continue
            if name.endswith(PARTIAL_WRITE_SUFFIX):
                # In-flight blob write; the payload appears under its final
                # name only once complete (FilesystemBlobStore.write_bytes).
                continue
            yield candidate


def _file_entry(bundle_root: Path, relative: str) -> dict[str, Any]:
    path = bundle_root / relative
    return {"path": relative, "sha256": _sha256(path), "size": path.stat().st_size}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


def verify_backup(
    backup_dir: Path,
    *,
    schema_heads: Mapping[str, str | None] | None = None,
) -> BackupVerification:
    """Validate manifest format, file checksums, and schema compatibility."""
    result = BackupVerification(backup_dir=backup_dir)
    manifest_path = backup_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        result.errors.append(f"Missing {MANIFEST_FILENAME} in {backup_dir}")
        return result
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        result.errors.append(f"Manifest is not valid JSON: {exc}")
        return result
    if not isinstance(manifest, dict):
        result.errors.append("Manifest must be a JSON object")
        return result
    result.manifest = manifest

    if manifest.get("format") != BACKUP_FORMAT:
        result.errors.append(f"Unsupported backup format: {manifest.get('format')!r}")
        return result
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        result.errors.append(
            "Unsupported backup format_version: "
            f"{manifest.get('format_version')!r} (expected {BACKUP_FORMAT_VERSION})"
        )
        return result

    expected_heads = dict(
        schema_heads if schema_heads is not None else current_schema_heads()
    )
    recorded_heads = manifest.get("schema_heads") or {}
    components = manifest.get("components") or []
    for component in components:
        if not component.get("included"):
            continue
        name = str(component.get("name"))
        track = _COMPONENT_SCHEMA_TRACK.get(name)
        if track is not None and recorded_heads.get(track) != expected_heads.get(track):
            result.errors.append(
                f"Schema version mismatch for {name}: backup has {track} migration "
                f"{recorded_heads.get(track)!r}, this build expects "
                f"{expected_heads.get(track)!r}"
            )
        for entry in component.get("files") or []:
            error = _verify_file_entry(backup_dir, entry)
            if error is not None:
                result.errors.append(error)
    return result


def _verify_file_entry(backup_dir: Path, entry: Mapping[str, Any]) -> str | None:
    relative = str(entry.get("path", ""))
    try:
        path = _safe_join(backup_dir, relative)
    except BackupError as exc:
        return str(exc)
    if not path.is_file():
        return f"Missing backup file: {relative}"
    if path.stat().st_size != entry.get("size"):
        return f"Size mismatch for {relative}"
    if _sha256(path) != entry.get("sha256"):
        return f"Checksum mismatch for {relative}"
    return None


def _safe_join(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or ".." in pure.parts:
        raise BackupError(f"Unsafe path in backup manifest: {relative!r}")
    return root.joinpath(*pure.parts)


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def restore_backup(
    backup_dir: Path,
    targets: BackupSources,
    *,
    force: bool = False,
    schema_heads: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    """Verify ``backup_dir`` and restore its included components into ``targets``.

    Refuses when verification fails, when a component cannot be restored into
    the target backend, or when a target already holds data and ``force`` is
    false. Nothing is written until every check passes.
    """
    verification = verify_backup(backup_dir, schema_heads=schema_heads)
    if not verification.passed:
        raise BackupError(
            "Backup verification failed; refusing to restore: "
            + "; ".join(verification.errors)
        )
    manifest = verification.manifest or {}
    included = [c for c in manifest.get("components", []) if c.get("included")]

    plan: list[tuple[str, list[tuple[Path, Path]]]] = []
    blockers: list[str] = []
    occupied: list[str] = []
    for component in included:
        name = str(component["name"])
        entries = component.get("files") or []
        if name == COMPONENT_CONTROL_PLANE_SQLITE:
            if targets.control_plane_backend.lower() != "sqlite":
                blockers.append(
                    "Backup contains a SQLite control plane but the target "
                    "control-plane backend is "
                    f"{targets.control_plane_backend!r}."
                )
                continue
            db_path = targets.control_plane_database_path
            if _sqlite_target_has_data(db_path):
                occupied.append(f"Target control-plane database is not empty: {db_path}")
            plan.append(
                (name, [(_safe_join(backup_dir, e["path"]), db_path) for e in entries])
            )
        elif name == COMPONENT_WAREHOUSE_DUCKDB:
            warehouse = targets.warehouse_database_path
            wal = warehouse.with_name(warehouse.name + ".wal")
            if _file_has_data(warehouse) or _file_has_data(wal):
                occupied.append(f"Target DuckDB warehouse is not empty: {warehouse}")
            copies = []
            for entry in entries:
                source = _safe_join(backup_dir, entry["path"])
                copies.append((source, wal if entry["path"].endswith(".wal") else warehouse))
            plan.append((name, copies))
        elif name == COMPONENT_LANDING_FILESYSTEM:
            if targets.blob_backend.lower() != "filesystem":
                blockers.append(
                    "Backup contains filesystem landing payloads but the target blob "
                    f"backend is {targets.blob_backend!r}."
                )
                continue
            root = targets.landing_root
            if root.is_dir() and any(True for _ in _iter_regular_files(root)):
                occupied.append(f"Target landing root is not empty: {root}")
            copies = []
            for entry in entries:
                relative = str(entry["path"])
                if not relative.startswith("landing/"):
                    raise BackupError(f"Unexpected landing path in manifest: {relative!r}")
                copies.append(
                    (
                        _safe_join(backup_dir, relative),
                        _safe_join(root, relative[len("landing/") :]),
                    )
                )
            plan.append((name, copies))
        else:
            blockers.append(f"Unknown backup component: {name!r}")

    if blockers:
        raise BackupError("Refusing to restore: " + "; ".join(blockers))
    if occupied and not force:
        raise BackupError(
            "Refusing to restore: "
            + "; ".join(occupied)
            + ". Pass --force to overwrite existing data."
        )

    restored: list[dict[str, Any]] = []
    for name, copies in plan:
        if name == COMPONENT_WAREHOUSE_DUCKDB and force:
            # A stale WAL from the replaced warehouse must not replay over it.
            warehouse = targets.warehouse_database_path
            stale_wal = warehouse.with_name(warehouse.name + ".wal")
            if stale_wal.exists() and all(dst != stale_wal for _, dst in copies):
                stale_wal.unlink()
        if name == COMPONENT_CONTROL_PLANE_SQLITE and force:
            db_path = targets.control_plane_database_path
            for suffix in ("-wal", "-shm", "-journal"):
                sidecar = db_path.with_name(db_path.name + suffix)
                if sidecar.exists():
                    sidecar.unlink()
        for source, target in copies:
            _atomic_copy(source, target)
        restored.append({"name": name, "files": len(copies)})

    source_info = manifest.get("source") or {}
    warnings: list[str] = []
    source_landing = source_info.get("landing_root")
    if (
        any(name == COMPONENT_LANDING_FILESYSTEM for name, _ in plan)
        and source_landing
        and Path(source_landing) != targets.landing_root
    ):
        warnings.append(
            "Landing root differs from the backup source "
            f"({source_landing} -> {targets.landing_root}); run metadata stores "
            "absolute filesystem locators, so keep the original landing path "
            "(for example the same container mount) for payload reads to resolve."
        )
    skipped = [
        {"name": c.get("name"), "reason": c.get("reason")}
        for c in manifest.get("components", [])
        if not c.get("included")
    ]
    return {
        "backup_dir": str(backup_dir),
        "restored": restored,
        "skipped": skipped,
        "warnings": warnings,
        "forced": force,
    }


def _file_has_data(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _sqlite_target_has_data(path: Path) -> bool:
    """A target is empty when missing, zero-length, or holding no user rows."""
    if not _file_has_data(path):
        return False
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            if connection.execute(f"SELECT 1 FROM {quoted} LIMIT 1").fetchone():
                return True
        return False
    except sqlite3.DatabaseError:
        return True
    finally:
        connection.close()


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.restore-tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, target)
