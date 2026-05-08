"""Use case: ingest Home Assistant state objects into the HA store."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from packages.pipelines.reporting_service import ReportingService


def ingest_ha_states(
    svc: "ReportingService",
    states: list[dict[str, Any]],
    *,
    run_id: str | None = None,
    source_system: str = "home_assistant",
) -> int:
    return svc.ingest_ha_states(states, run_id=run_id, source_system=source_system)
