from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from packages.domains.finance.pipelines.asset_models import (
    CURRENT_DIM_ASSET_VIEW,
    DIM_ASSET,
    FACT_ASSET_EVENT_COLUMNS,
    FACT_ASSET_EVENT_TABLE,
    extract_asset_events,
    extract_asset_register_events,
    extract_assets_from_register,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def ensure_asset_storage(store: DuckDBStore) -> None:
    store.ensure_dimension(DIM_ASSET)
    store.ensure_current_dimension_view(DIM_ASSET, CURRENT_DIM_ASSET_VIEW)
    store.ensure_table(FACT_ASSET_EVENT_TABLE, FACT_ASSET_EVENT_COLUMNS)


def load_asset_register_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    asset_rows = extract_assets_from_register(rows)
    event_rows = extract_asset_register_events(rows)
    eff = effective_date or date.today()

    with store.atomic():
        assets_upserted = store.upsert_dimension_rows(
            DIM_ASSET,
            asset_rows,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )
        inserted = store.insert_rows(FACT_ASSET_EVENT_TABLE, event_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_asset", "dimension", assets_upserted),
            (FACT_ASSET_EVENT_TABLE, "fact", inserted),
        ],
    )
    return inserted


def load_asset_event_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    event_rows = extract_asset_events(rows)

    with store.atomic():
        inserted = store.insert_rows(FACT_ASSET_EVENT_TABLE, event_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[(FACT_ASSET_EVENT_TABLE, "fact", inserted)],
    )
    return inserted


def get_current_assets(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(f"SELECT * FROM {CURRENT_DIM_ASSET_VIEW} ORDER BY asset_id")


def count_asset_event_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_ASSET_EVENT_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_ASSET_EVENT_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]
