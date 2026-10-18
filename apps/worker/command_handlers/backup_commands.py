"""Backup, verify-backup, and restore worker commands.

These commands operate on files only and run *before* the worker runtime is
built, so restoring into a fresh data directory never sees stores that the
runtime would otherwise initialize first.
"""
from __future__ import annotations

from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from apps.worker.ops import (
    backup_policy_from_settings,
    backup_sources_from_settings,
)
from apps.worker.serialization import _write_json
from packages.shared.settings import AppSettings
from packages.storage.backup_bundle import (
    BackupError,
    create_backup,
    restore_backup,
    verify_backup,
)
from packages.storage.backup_drill import run_restore_drill
from packages.storage.backup_schedule import run_scheduled_backup


def handle_backup(
    args: Namespace, settings: AppSettings, output: TextIO, error_output: TextIO
) -> int:
    destination = Path(args.output_dir)
    try:
        manifest = create_backup(backup_sources_from_settings(settings), destination)
    except BackupError as exc:
        error_output.write(f"{exc}\n")
        return 1
    _write_json(
        output,
        {
            "output_dir": str(destination),
            "created_at": manifest["created_at"],
            "schema_heads": manifest["schema_heads"],
            "components": [
                {
                    "name": component["name"],
                    "included": component["included"],
                    "files": len(component["files"]),
                    **({"reason": component["reason"]} if "reason" in component else {}),
                }
                for component in manifest["components"]
            ],
        },
    )
    return 0


def handle_verify_backup(
    args: Namespace, settings: AppSettings, output: TextIO, error_output: TextIO
) -> int:
    verification = verify_backup(Path(args.backup_dir))
    _write_json(output, {"verification": verification.as_dict()})
    if not verification.passed:
        for error in verification.errors:
            error_output.write(f"{error}\n")
        return 1
    return 0


def handle_restore(
    args: Namespace, settings: AppSettings, output: TextIO, error_output: TextIO
) -> int:
    try:
        result = restore_backup(
            Path(args.backup_dir),
            backup_sources_from_settings(settings),
            force=bool(getattr(args, "force", False)),
        )
    except BackupError as exc:
        error_output.write(f"{exc}\n")
        return 1
    _write_json(output, {"restore": result})
    for warning in result["warnings"]:
        error_output.write(f"warning: {warning}\n")
    return 0


def handle_scheduled_backup(
    args: Namespace, settings: AppSettings, output: TextIO, error_output: TextIO
) -> int:
    """One retained, verified bundle under the backup root, regardless of interval.

    Same staging/verify/prune/status path as the worker-loop schedule, for
    one-off runs (operator, restore drill, single-process deployments).
    """
    policy = backup_policy_from_settings(settings)
    if getattr(args, "backup_dir", ""):
        policy = replace(policy, destination_root=Path(args.backup_dir))
    result = run_scheduled_backup(backup_sources_from_settings(settings), policy)
    _write_json(
        output,
        {
            "scheduled_backup": {
                "succeeded": result.succeeded,
                "bundle_dir": str(result.bundle_dir) if result.bundle_dir else None,
                "pruned": [str(path) for path in result.pruned],
                "status": result.status.as_dict(),
            }
        },
    )
    if not result.succeeded:
        error_output.write(f"{result.error}\n")
        return 1
    return 0


def handle_restore_drill(
    args: Namespace, settings: AppSettings, output: TextIO, error_output: TextIO
) -> int:
    """Restore a bundle (default: newest scheduled bundle) into scratch and check it."""
    backup_root = Path(args.backup_dir) if getattr(args, "backup_dir", "") else (
        settings.resolved_backup_dir
    )
    receipt = run_restore_drill(
        backup_root=backup_root,
        bundle_dir=Path(args.bundle) if getattr(args, "bundle", "") else None,
        scratch_dir=Path(args.scratch_dir) if getattr(args, "scratch_dir", "") else None,
        keep_scratch=bool(getattr(args, "keep_scratch", False)),
    )
    _write_json(output, {"restore_drill": receipt})
    if not receipt["passed"]:
        for error in receipt["errors"]:
            error_output.write(f"{error}\n")
        return 1
    return 0
