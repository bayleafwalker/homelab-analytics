"""Asset register, events, and valuation marts."""

from __future__ import annotations

from datetime import date
from typing import Any

from packages.domains.finance.pipelines.transformation_assets import (
    count_asset_event_rows,
    load_asset_event_rows,
    load_asset_register_rows,
)
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class AssetTransformationMixin(TransformationFacetBase):
    """Asset register, events, and valuation marts."""

    def load_asset_register(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_asset_register_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def load_asset_events(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_asset_event_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def count_asset_event_rows(self, run_id: str | None = None) -> int:
        return count_asset_event_rows(self._store, run_id=run_id)
