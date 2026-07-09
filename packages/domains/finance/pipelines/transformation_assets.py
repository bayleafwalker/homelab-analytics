from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from packages.domains.finance.pipelines.asset_models import (
    CURRENT_DIM_ASSET_VIEW,
    DIM_ASSET,
    FACT_ASSET_EVENT_COLUMNS,
    FACT_ASSET_EVENT_TABLE,
    MART_ASSET_VALUE_COLUMNS,
    MART_ASSET_VALUE_TABLE,
    MART_DEPRECIATION_SCHEDULE_COLUMNS,
    MART_DEPRECIATION_SCHEDULE_TABLE,
    extract_asset_events,
    extract_asset_register_events,
    extract_assets_from_register,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]

# Straight-line useful life applied when an asset has no explicitly recorded
# depreciation events. Indicative default (five years); per-class overrides
# can come via config in a later sprint.
_USEFUL_LIFE_MONTHS = 60


def ensure_asset_storage(store: DuckDBStore) -> None:
    store.ensure_dimension(DIM_ASSET)
    store.ensure_current_dimension_view(DIM_ASSET, CURRENT_DIM_ASSET_VIEW)
    store.ensure_table(FACT_ASSET_EVENT_TABLE, FACT_ASSET_EVENT_COLUMNS)
    store.ensure_table(MART_ASSET_VALUE_TABLE, MART_ASSET_VALUE_COLUMNS)
    store.ensure_table(
        MART_DEPRECIATION_SCHEDULE_TABLE, MART_DEPRECIATION_SCHEDULE_COLUMNS
    )


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


# ---------------------------------------------------------------------------
# Mart builders
# ---------------------------------------------------------------------------

def refresh_asset_value(store: DuckDBStore) -> int:
    """Current estimated value per tracked asset.

    Valuation precedence per asset: disposal events zero the value; explicitly
    recorded depreciation events are summed (capped at purchase price);
    otherwise value straight-lines to zero over ``_USEFUL_LIFE_MONTHS``.
    """
    store.execute(f"DELETE FROM {MART_ASSET_VALUE_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_ASSET_VALUE_TABLE} (
            asset_id, asset_name, asset_type, location, purchase_date,
            purchase_price, currency, months_in_service,
            accumulated_depreciation, estimated_value, valuation_basis,
            is_disposed
        )
        WITH recorded_depreciation AS (
            SELECT asset_id, SUM(amount) AS recorded_amount
            FROM {FACT_ASSET_EVENT_TABLE}
            WHERE event_type = 'depreciation'
            GROUP BY asset_id
        ),
        disposals AS (
            SELECT DISTINCT asset_id
            FROM {FACT_ASSET_EVENT_TABLE}
            WHERE event_type = 'disposal'
        ),
        base AS (
            SELECT
                a.asset_id,
                a.asset_name,
                a.asset_type,
                a.location,
                a.purchase_date,
                a.purchase_price,
                a.currency,
                CASE
                    WHEN a.purchase_date IS NULL THEN NULL
                    ELSE GREATEST(
                        date_diff('month', a.purchase_date, CURRENT_DATE), 0
                    )
                END                                     AS months_in_service,
                r.recorded_amount,
                d.asset_id IS NOT NULL                  AS is_disposed
            FROM {CURRENT_DIM_ASSET_VIEW} a
            LEFT JOIN recorded_depreciation r ON r.asset_id = a.asset_id
            LEFT JOIN disposals d ON d.asset_id = a.asset_id
        ),
        valued AS (
            SELECT
                *,
                CASE
                    WHEN is_disposed
                        THEN COALESCE(purchase_price, 0)
                    WHEN recorded_amount IS NOT NULL
                        THEN LEAST(recorded_amount, COALESCE(purchase_price, recorded_amount))
                    ELSE ROUND(
                        LEAST(COALESCE(months_in_service, 0), {_USEFUL_LIFE_MONTHS})
                            * COALESCE(purchase_price, 0)
                            / {_USEFUL_LIFE_MONTHS}.0,
                        4
                    )
                END AS accumulated_depreciation,
                CASE
                    WHEN is_disposed THEN 'disposed'
                    WHEN recorded_amount IS NOT NULL THEN 'recorded_events'
                    ELSE 'straight_line_{_USEFUL_LIFE_MONTHS}m'
                END AS valuation_basis
            FROM base
        )
        SELECT
            asset_id,
            asset_name,
            asset_type,
            location,
            purchase_date,
            purchase_price,
            currency,
            months_in_service,
            accumulated_depreciation,
            GREATEST(COALESCE(purchase_price, 0) - accumulated_depreciation, 0)
                AS estimated_value,
            valuation_basis,
            is_disposed
        FROM valued
        ORDER BY asset_id
        """
    )
    return store.fetchall(f"SELECT COUNT(*) FROM {MART_ASSET_VALUE_TABLE}")[0][0]


def refresh_depreciation_schedule(store: DuckDBStore) -> int:
    """Annual depreciation by asset class.

    Assets with explicitly recorded depreciation events contribute those
    events in their recorded years; all other priced assets contribute a
    straight-line schedule projected over ``_USEFUL_LIFE_MONTHS`` from their
    purchase month. Grouped by currency so mixed-currency registers never sum
    across currencies.
    """
    store.execute(f"DELETE FROM {MART_DEPRECIATION_SCHEDULE_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_DEPRECIATION_SCHEDULE_TABLE} (
            depreciation_year, asset_type, currency, annual_depreciation,
            asset_count
        )
        WITH recorded_assets AS (
            SELECT DISTINCT asset_id
            FROM {FACT_ASSET_EVENT_TABLE}
            WHERE event_type = 'depreciation'
        ),
        straight_line AS (
            SELECT
                a.asset_id,
                COALESCE(a.asset_type, 'unknown')     AS asset_type,
                a.currency,
                CAST(EXTRACT(
                    year FROM date_trunc('month', a.purchase_date)
                        + to_months(CAST(gs.offs AS INTEGER))
                ) AS INTEGER)                          AS depreciation_year,
                a.purchase_price / {_USEFUL_LIFE_MONTHS}.0 AS depreciation_amount
            FROM {CURRENT_DIM_ASSET_VIEW} a
            CROSS JOIN generate_series(0, {_USEFUL_LIFE_MONTHS - 1}) AS gs(offs)
            WHERE a.purchase_date IS NOT NULL
              AND a.purchase_price IS NOT NULL
              AND a.asset_id NOT IN (SELECT asset_id FROM recorded_assets)
        ),
        recorded AS (
            SELECT
                e.asset_id,
                COALESCE(a.asset_type, 'unknown')      AS asset_type,
                e.currency,
                CAST(EXTRACT(year FROM e.event_date) AS INTEGER)
                                                       AS depreciation_year,
                e.amount                               AS depreciation_amount
            FROM {FACT_ASSET_EVENT_TABLE} e
            LEFT JOIN {CURRENT_DIM_ASSET_VIEW} a ON a.asset_id = e.asset_id
            WHERE e.event_type = 'depreciation'
        ),
        combined AS (
            SELECT * FROM straight_line
            UNION ALL
            SELECT * FROM recorded
        )
        SELECT
            depreciation_year,
            asset_type,
            currency,
            ROUND(SUM(depreciation_amount), 4)  AS annual_depreciation,
            COUNT(DISTINCT asset_id)            AS asset_count
        FROM combined
        GROUP BY depreciation_year, asset_type, currency
        ORDER BY depreciation_year, asset_type
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_DEPRECIATION_SCHEDULE_TABLE}"
    )[0][0]


def get_asset_value(
    store: DuckDBStore,
    *,
    asset_type: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if asset_type is not None:
        clauses.append("asset_type = ?")
        params.append(asset_type)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_ASSET_VALUE_TABLE} {where_sql} ORDER BY asset_id",
        params,
    )


def get_depreciation_schedule(
    store: DuckDBStore,
    *,
    asset_type: str | None = None,
    depreciation_year: int | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if asset_type is not None:
        clauses.append("asset_type = ?")
        params.append(asset_type)
    if depreciation_year is not None:
        clauses.append("depreciation_year = ?")
        params.append(depreciation_year)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_DEPRECIATION_SCHEDULE_TABLE}"
        f" {where_sql} ORDER BY depreciation_year, asset_type",
        params,
    )


def get_current_assets(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(f"SELECT * FROM {CURRENT_DIM_ASSET_VIEW} ORDER BY asset_id")


def count_asset_event_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_ASSET_EVENT_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_ASSET_EVENT_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]
