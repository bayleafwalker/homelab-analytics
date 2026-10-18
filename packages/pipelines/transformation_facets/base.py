"""Shared state and helpers available to every transformation facet."""

from __future__ import annotations

import uuid

from packages.pipelines.scenario_registry import ScenarioRegistry
from packages.storage.control_plane import ControlPlaneStore, SourceLineageCreate
from packages.storage.duckdb_store import DuckDBStore


class TransformationFacetBase:
    """State initialised by ``TransformationService.__init__``."""

    _store: DuckDBStore
    _control_plane_store: ControlPlaneStore | None
    _scenario_registry: ScenarioRegistry

    def _record_lineage(
        self,
        *,
        run_id: str | None,
        source_system: str | None,
        records: list[tuple[str, str, int | None]],
    ) -> None:
        if run_id is None or self._control_plane_store is None:
            return
        self._control_plane_store.record_source_lineage(
            tuple(
                SourceLineageCreate(
                    lineage_id=uuid.uuid4().hex[:16],
                    input_run_id=run_id,
                    source_run_id=run_id,
                    source_system=source_system,
                    target_layer="transformation",
                    target_name=target_name,
                    target_kind=target_kind,
                    row_count=row_count,
                )
                for target_name, target_kind, row_count in records
            )
        )
