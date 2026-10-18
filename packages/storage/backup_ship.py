"""Off-site shipment status written by the ``backup-ship`` sidecar.

The worker never ships bundles itself. On appservice a sidecar container
(docs/notes/appservice-proposals/deployment.yaml) streams each verified
``backup-<stamp>/`` bundle as ``tar | age | rclone rcat`` to the Object-Lock
bucket and records, on the shared backup volume::

    <backup_dir>/
        .shipped            one shipped bundle name per line
        ship-status.json    last pass / attempt / success / failure, read by /metrics

This module only reads those files so the worker and API ``/metrics`` can
export shipment recency. It tolerates a partially written or foreign file:
anything unparsable reads as "no status" rather than failing the scrape.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.storage.backup_schedule import list_bundles

__all__ = [
    "SHIPPED_STATE_FILENAME",
    "SHIP_STATUS_FILENAME",
    "ShipStatus",
    "pending_bundle_names",
    "read_ship_status",
    "read_shipped_names",
]

SHIP_STATUS_FILENAME = "ship-status.json"
SHIPPED_STATE_FILENAME = ".shipped"


@dataclass(frozen=True)
class ShipStatus:
    last_pass_at: str | None = None
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_error: str | None = None
    last_shipped_bundle: str | None = None
    last_size_bytes: int = 0
    consecutive_failures: int = 0
    shipped_total: int = 0
    failures_total: int = 0


def _text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _count(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def read_ship_status(backup_root: Path) -> ShipStatus | None:
    try:
        payload = json.loads((backup_root / SHIP_STATUS_FILENAME).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return ShipStatus(
        last_pass_at=_text(payload, "last_pass_at"),
        last_attempt_at=_text(payload, "last_attempt_at"),
        last_success_at=_text(payload, "last_success_at"),
        last_failure_at=_text(payload, "last_failure_at"),
        last_error=_text(payload, "last_error"),
        last_shipped_bundle=_text(payload, "last_shipped_bundle"),
        last_size_bytes=_count(payload, "last_size_bytes"),
        consecutive_failures=_count(payload, "consecutive_failures"),
        shipped_total=_count(payload, "shipped_total"),
        failures_total=_count(payload, "failures_total"),
    )


def read_shipped_names(backup_root: Path) -> set[str]:
    try:
        lines = (backup_root / SHIPPED_STATE_FILENAME).read_text().splitlines()
    except OSError:
        return set()
    return {line.strip() for line in lines if line.strip()}


def pending_bundle_names(backup_root: Path) -> list[str]:
    """Complete local bundles the sidecar has not recorded as shipped yet."""
    shipped = read_shipped_names(backup_root)
    return [bundle.name for bundle in list_bundles(backup_root) if bundle.name not in shipped]
