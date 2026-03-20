"""Home Assistant backup-run events source definition."""
from __future__ import annotations

from packages.platform.capability_types import SourceDefinition

HA_BACKUP_RUNS_SOURCE = SourceDefinition(
    dataset_name="ha_backup_runs",
    display_name="HA Backup Runs",
    description="Home Assistant backup job events — start, completion, size, and target.",
    retry_kind="ha_backup_runs",
)
