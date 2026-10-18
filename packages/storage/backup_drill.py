"""Restore drill: prove a backup bundle restores into a scratch instance.

The drill never touches the live stores. It verifies the bundle, restores
every included component into an empty scratch directory (SQLite control
plane, DuckDB warehouse, filesystem landing), then checks that the restored
warehouse opens and every table scans, and that the restored landing tree
matches the manifest. The receipt is written next to the bundles as
``restore-drill-status.json`` so ``/metrics`` can export drill recency.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from packages.storage.backup_bundle import (
    MANIFEST_FILENAME,
    BackupError,
    BackupSources,
    restore_backup,
    verify_backup,
)
from packages.storage.backup_schedule import list_bundles

__all__ = [
    "RESTORE_DRILL_STATUS_FILENAME",
    "read_restore_drill_status",
    "run_restore_drill",
]

RESTORE_DRILL_STATUS_FILENAME = "restore-drill-status.json"


def _scratch_targets(scratch: Path) -> BackupSources:
    return BackupSources(
        control_plane_backend="sqlite",
        reporting_backend="duckdb",
        blob_backend="filesystem",
        control_plane_database_path=scratch / "config.db",
        warehouse_database_path=scratch / "analytics" / "warehouse.duckdb",
        landing_root=scratch / "landing",
    )


def _warehouse_table_counts(path: Path) -> dict[str, int]:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        tables = connection.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_type = 'BASE TABLE' ORDER BY table_schema, table_name"
        ).fetchall()
        counts: dict[str, int] = {}
        for schema, table in tables:
            row = connection.execute(f'SELECT count(*) FROM "{schema}"."{table}"').fetchone()
            counts[f"{schema}.{table}"] = int(row[0]) if row else 0
        return counts
    finally:
        connection.close()


def read_restore_drill_status(backup_root: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads((backup_root / RESTORE_DRILL_STATUS_FILENAME).read_text())
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_receipt(backup_root: Path, receipt: dict[str, Any]) -> None:
    previous = read_restore_drill_status(backup_root) or {}
    status = {
        **receipt,
        "last_success_at": (
            receipt["finished_at"] if receipt["passed"] else previous.get("last_success_at")
        ),
    }
    backup_root.mkdir(parents=True, exist_ok=True)
    tmp = backup_root / f".{RESTORE_DRILL_STATUS_FILENAME}.{uuid.uuid4().hex}.tmp"
    tmp.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, backup_root / RESTORE_DRILL_STATUS_FILENAME)


def run_restore_drill(
    *,
    backup_root: Path,
    bundle_dir: Path | None = None,
    scratch_dir: Path | None = None,
    keep_scratch: bool = False,
    record: bool = True,
) -> dict[str, Any]:
    """Restore ``bundle_dir`` (default: newest bundle) into scratch and check it."""
    started_at = datetime.now(UTC)
    started = time.monotonic()
    errors: list[str] = []
    bundle = bundle_dir
    if bundle is None:
        bundles = list_bundles(backup_root)
        bundle = bundles[-1] if bundles else None
    owns_scratch = scratch_dir is None
    scratch = scratch_dir or Path(tempfile.mkdtemp(prefix="homelab-analytics-drill-"))
    receipt: dict[str, Any] = {
        "bundle": str(bundle) if bundle else None,
        "scratch_dir": str(scratch),
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "restored_components": [],
        "warehouse_tables": {},
        "landing_files": 0,
    }
    try:
        if bundle is None:
            raise BackupError(f"No complete backup bundle under {backup_root}.")
        if scratch.exists() and any(scratch.iterdir()):
            raise BackupError(f"Drill scratch directory is not empty: {scratch}")
        verification = verify_backup(bundle)
        if not verification.passed:
            raise BackupError("Bundle failed verification: " + "; ".join(verification.errors))
        targets = _scratch_targets(scratch)
        result = restore_backup(bundle, targets)
        receipt["restored_components"] = list(result.get("restored", []))
        manifest = json.loads((bundle / MANIFEST_FILENAME).read_text())
        components = {c["name"]: c for c in manifest["components"]}
        warehouse = components.get("warehouse_duckdb")
        if warehouse and warehouse.get("included"):
            receipt["warehouse_tables"] = _warehouse_table_counts(
                targets.warehouse_database_path
            )
        landing = components.get("landing_filesystem")
        if landing and landing.get("included"):
            expected = sorted(entry["path"].removeprefix("landing/") for entry in landing["files"])
            restored = sorted(
                path.relative_to(targets.landing_root).as_posix()
                for path in targets.landing_root.rglob("*")
                if path.is_file()
            ) if targets.landing_root.exists() else []
            receipt["landing_files"] = len(restored)
            if restored != expected:
                errors.append(
                    f"Restored landing tree differs from manifest "
                    f"({len(restored)} files vs {len(expected)} expected)."
                )
    except (BackupError, OSError, duckdb.Error, ValueError, KeyError) as exc:
        errors.append(str(exc))
    finally:
        if owns_scratch and not keep_scratch:
            shutil.rmtree(scratch, ignore_errors=True)
    finished_at = datetime.now(UTC)
    receipt.update(
        {
            "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
            "duration_seconds": round(time.monotonic() - started, 3),
            "passed": not errors,
            "errors": errors,
        }
    )
    if record:
        _write_receipt(backup_root, receipt)
    return receipt
