from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from packages.pipelines.contract_price_models import MART_CONTRACT_PRICE_CURRENT_TABLE
from packages.pipelines.normalization import normalize_currency_code, normalize_unit
from packages.pipelines.utility_models import (
    FACT_BILL_COLUMNS,
    FACT_BILL_TABLE,
    FACT_UTILITY_USAGE_COLUMNS,
    FACT_UTILITY_USAGE_TABLE,
    MART_CONTRACT_RENEWAL_WATCHLIST_COLUMNS,
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
    MART_CONTRACT_REVIEW_CANDIDATES_COLUMNS,
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
    MART_USAGE_VS_PRICE_SUMMARY_COLUMNS,
    MART_USAGE_VS_PRICE_SUMMARY_TABLE,
    MART_UTILITY_COST_SUMMARY_COLUMNS,
    MART_UTILITY_COST_SUMMARY_TABLE,
    MART_UTILITY_COST_TREND_MONTHLY_COLUMNS,
    MART_UTILITY_COST_TREND_MONTHLY_TABLE,
    extract_meters_from_bills,
    extract_meters_from_usage,
    utility_bill_id,
    utility_usage_id,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def ensure_utility_storage(store: DuckDBStore) -> None:
    store.ensure_table(FACT_UTILITY_USAGE_TABLE, FACT_UTILITY_USAGE_COLUMNS)
    store.ensure_table(FACT_BILL_TABLE, FACT_BILL_COLUMNS)
    store.ensure_table(MART_UTILITY_COST_SUMMARY_TABLE, MART_UTILITY_COST_SUMMARY_COLUMNS)
    store.ensure_table(
        MART_UTILITY_COST_TREND_MONTHLY_TABLE, MART_UTILITY_COST_TREND_MONTHLY_COLUMNS
    )
    store.ensure_table(
        MART_USAGE_VS_PRICE_SUMMARY_TABLE, MART_USAGE_VS_PRICE_SUMMARY_COLUMNS
    )
    store.ensure_table(
        MART_CONTRACT_REVIEW_CANDIDATES_TABLE, MART_CONTRACT_REVIEW_CANDIDATES_COLUMNS
    )
    store.ensure_table(
        MART_CONTRACT_RENEWAL_WATCHLIST_TABLE, MART_CONTRACT_RENEWAL_WATCHLIST_COLUMNS
    )


def load_utility_usage(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    dim_meter,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    eff = effective_date or date.today()

    with store.atomic():
        meters = extract_meters_from_usage(rows)
        meters_upserted = store.upsert_dimension_rows(
            dim_meter,
            meters,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        fact_rows = []
        for row in rows:
            usage_quantity = row["usage_quantity"]
            if isinstance(usage_quantity, str):
                usage_quantity = Decimal(usage_quantity)
            elif isinstance(usage_quantity, float):
                usage_quantity = Decimal(str(usage_quantity))

            usage_start = _coerce_date(row["usage_start"])
            usage_end = _coerce_date(row["usage_end"])
            usage_unit = normalize_unit(str(row["usage_unit"])).value

            fact_rows.append(
                {
                    "usage_id": utility_usage_id(
                        row["meter_id"],
                        usage_start,
                        usage_end,
                        usage_quantity,
                    ),
                    "meter_id": row["meter_id"],
                    "meter_name": row["meter_name"],
                    "utility_type": row["utility_type"],
                    "usage_start": usage_start,
                    "usage_end": usage_end,
                    "usage_quantity": usage_quantity,
                    "usage_unit": usage_unit,
                    "reading_source": row.get("reading_source"),
                    "run_id": run_id,
                }
            )

        inserted = store.insert_rows(FACT_UTILITY_USAGE_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_meter", "dimension", meters_upserted),
            ("fact_utility_usage", "fact", inserted),
        ],
    )
    return inserted


def load_bills(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    dim_meter,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    eff = effective_date or date.today()

    with store.atomic():
        meters = extract_meters_from_bills(rows)
        meters_upserted = store.upsert_dimension_rows(
            dim_meter,
            meters,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        fact_rows = []
        for row in rows:
            billed_amount = row["billed_amount"]
            if isinstance(billed_amount, str):
                billed_amount = Decimal(billed_amount)
            elif isinstance(billed_amount, float):
                billed_amount = Decimal(str(billed_amount))

            billed_quantity = row.get("billed_quantity")
            if isinstance(billed_quantity, str) and billed_quantity:
                billed_quantity = Decimal(billed_quantity)
            elif isinstance(billed_quantity, float):
                billed_quantity = Decimal(str(billed_quantity))
            elif billed_quantity in {"", None}:
                billed_quantity = None

            usage_unit = row.get("usage_unit")
            normalized_usage_unit = (
                normalize_unit(str(usage_unit)).value if usage_unit else None
            )

            fact_rows.append(
                {
                    "bill_id": utility_bill_id(
                        row["meter_id"],
                        _coerce_date(row["billing_period_start"]),
                        _coerce_date(row["billing_period_end"]),
                        str(row.get("provider", "")),
                        billed_amount,
                    ),
                    "meter_id": row["meter_id"],
                    "meter_name": row["meter_name"],
                    "provider": row.get("provider", ""),
                    "utility_type": row["utility_type"],
                    "billing_period_start": _coerce_date(row["billing_period_start"]),
                    "billing_period_end": _coerce_date(row["billing_period_end"]),
                    "billed_amount": billed_amount,
                    "currency": normalize_currency_code(str(row["currency"])),
                    "billed_quantity": billed_quantity,
                    "usage_unit": normalized_usage_unit,
                    "invoice_date": (
                        _coerce_date(row["invoice_date"])
                        if row.get("invoice_date")
                        else None
                    ),
                    "run_id": run_id,
                }
            )

        inserted = store.insert_rows(FACT_BILL_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_meter", "dimension", meters_upserted),
            ("fact_bill", "fact", inserted),
        ],
    )
    return inserted


def refresh_utility_cost_summary(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_UTILITY_COST_SUMMARY_TABLE}")

    store.execute(
        f"""
        INSERT INTO {MART_UTILITY_COST_SUMMARY_TABLE} (
            period_start, period_end, period_day, period_month, meter_id, meter_name,
            utility_type, usage_quantity, usage_unit, billed_amount, currency,
            unit_cost, bill_count, usage_record_count, coverage_status
        )
        SELECT
            b.billing_period_start AS period_start,
            b.billing_period_end AS period_end,
            b.billing_period_start AS period_day,
            strftime(b.billing_period_start, '%Y-%m') AS period_month,
            b.meter_id,
            b.meter_name,
            b.utility_type,
            COALESCE(SUM(u.usage_quantity), 0) AS usage_quantity,
            COALESCE(any_value(u.usage_unit), any_value(b.usage_unit)) AS usage_unit,
            SUM(b.billed_amount) AS billed_amount,
            b.currency,
            CASE
                WHEN COALESCE(SUM(u.usage_quantity), 0) > 0
                THEN CAST(ROUND(SUM(b.billed_amount) / SUM(u.usage_quantity), 4) AS DECIMAL(18,4))
                ELSE NULL
            END AS unit_cost,
            COUNT(DISTINCT b.bill_id) AS bill_count,
            COUNT(DISTINCT u.usage_id) AS usage_record_count,
            CASE
                WHEN COUNT(DISTINCT u.usage_id) > 0 THEN 'matched'
                ELSE 'bill_only'
            END AS coverage_status
        FROM {FACT_BILL_TABLE} b
        LEFT JOIN {FACT_UTILITY_USAGE_TABLE} u
            ON u.meter_id = b.meter_id
            AND u.utility_type = b.utility_type
            AND u.usage_start >= b.billing_period_start
            AND u.usage_end <= b.billing_period_end
        GROUP BY
            b.billing_period_start,
            b.billing_period_end,
            b.meter_id,
            b.meter_name,
            b.utility_type,
            b.currency
        ORDER BY b.billing_period_start, b.meter_id
        """
    )

    store.execute(
        f"""
        INSERT INTO {MART_UTILITY_COST_SUMMARY_TABLE} (
            period_start, period_end, period_day, period_month, meter_id, meter_name,
            utility_type, usage_quantity, usage_unit, billed_amount, currency,
            unit_cost, bill_count, usage_record_count, coverage_status
        )
        SELECT
            u.usage_start AS period_start,
            u.usage_end AS period_end,
            u.usage_start AS period_day,
            strftime(u.usage_start, '%Y-%m') AS period_month,
            u.meter_id,
            u.meter_name,
            u.utility_type,
            SUM(u.usage_quantity) AS usage_quantity,
            any_value(u.usage_unit) AS usage_unit,
            CAST(0 AS DECIMAL(18,4)) AS billed_amount,
            NULL AS currency,
            CAST(NULL AS DECIMAL(18,4)) AS unit_cost,
            0 AS bill_count,
            COUNT(*) AS usage_record_count,
            'usage_only' AS coverage_status
        FROM {FACT_UTILITY_USAGE_TABLE} u
        WHERE NOT EXISTS (
            SELECT 1
            FROM {FACT_BILL_TABLE} b
            WHERE b.meter_id = u.meter_id
                AND b.utility_type = u.utility_type
                AND u.usage_start >= b.billing_period_start
                AND u.usage_end <= b.billing_period_end
        )
        GROUP BY
            u.usage_start,
            u.usage_end,
            u.meter_id,
            u.meter_name,
            u.utility_type
        ORDER BY u.usage_start, u.meter_id
        """
    )

    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_UTILITY_COST_SUMMARY_TABLE}"
    )[0][0]


def get_utility_cost_summary(
    store: DuckDBStore,
    *,
    utility_type: str | None = None,
    meter_id: str | None = None,
    from_period: date | str | None = None,
    to_period: date | str | None = None,
    granularity: str = "month",
) -> list[dict[str, Any]]:
    if granularity not in {"day", "month"}:
        raise ValueError(f"Unsupported granularity: {granularity!r}")

    clauses: list[str] = []
    params: list[Any] = []
    if utility_type is not None:
        clauses.append("utility_type = ?")
        params.append(utility_type)
    if meter_id is not None:
        clauses.append("meter_id = ?")
        params.append(meter_id)
    if from_period is not None:
        clauses.append("period_start >= ?")
        params.append(_coerce_date(from_period))
    if to_period is not None:
        clauses.append("period_end <= ?")
        params.append(_coerce_date(to_period))
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    if granularity == "day":
        return store.fetchall_dicts(
            f"""
            SELECT
                period_day AS period,
                period_start,
                period_end,
                meter_id,
                meter_name,
                utility_type,
                usage_quantity,
                usage_unit,
                billed_amount,
                currency,
                CAST(unit_cost AS DECIMAL(18,4)) AS unit_cost,
                bill_count,
                usage_record_count,
                coverage_status
            FROM {MART_UTILITY_COST_SUMMARY_TABLE}
            {where_sql}
            ORDER BY period_day, meter_id
            """,
            params,
        )

    return store.fetchall_dicts(
        f"""
        SELECT
            period_month AS period,
            MIN(period_start) AS period_start,
            MAX(period_end) AS period_end,
            meter_id,
            any_value(meter_name) AS meter_name,
            utility_type,
            SUM(usage_quantity) AS usage_quantity,
            any_value(usage_unit) AS usage_unit,
            SUM(billed_amount) AS billed_amount,
            any_value(currency) AS currency,
            CASE
                WHEN SUM(usage_quantity) > 0
                THEN CAST(ROUND(SUM(billed_amount) / SUM(usage_quantity), 4) AS DECIMAL(18,4))
                ELSE NULL
            END AS unit_cost,
            SUM(bill_count) AS bill_count,
            SUM(usage_record_count) AS usage_record_count,
            CASE
                WHEN SUM(bill_count) > 0 AND SUM(usage_record_count) > 0 THEN 'matched'
                WHEN SUM(bill_count) > 0 THEN 'bill_only'
                ELSE 'usage_only'
            END AS coverage_status
        FROM {MART_UTILITY_COST_SUMMARY_TABLE}
        {where_sql}
        GROUP BY period_month, meter_id, utility_type
        ORDER BY period_month, meter_id
        """,
        params,
    )


def refresh_utility_cost_trend_monthly(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
            (billing_month, utility_type, total_cost, usage_amount,
             unit_price_effective, currency, meter_count)
        SELECT
            period_month                                AS billing_month,
            utility_type,
            SUM(billed_amount)                          AS total_cost,
            SUM(usage_quantity)                         AS usage_amount,
            CASE
                WHEN SUM(usage_quantity) > 0
                THEN CAST(ROUND(SUM(billed_amount) / SUM(usage_quantity), 4) AS DECIMAL(18,4))
                ELSE NULL
            END                                         AS unit_price_effective,
            ANY_VALUE(currency)                         AS currency,
            COUNT(DISTINCT meter_id)                    AS meter_count
        FROM {MART_UTILITY_COST_SUMMARY_TABLE}
        GROUP BY period_month, utility_type
        ORDER BY period_month, utility_type
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}"
    )[0][0]


def get_utility_cost_trend_monthly(
    store: DuckDBStore,
    *,
    utility_type: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if utility_type is not None:
        clauses.append("utility_type = ?")
        params.append(utility_type)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}"
        f" {where_sql} ORDER BY billing_month, utility_type",
        params,
    )


def refresh_usage_vs_price_summary(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_USAGE_VS_PRICE_SUMMARY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_USAGE_VS_PRICE_SUMMARY_TABLE}
            (utility_type, period, usage_change_pct, price_change_pct,
             cost_change_pct, dominant_driver)
        WITH monthly_agg AS (
            SELECT
                period_month,
                utility_type,
                SUM(usage_quantity)  AS usage_amount,
                SUM(billed_amount)   AS total_cost,
                CASE
                    WHEN SUM(usage_quantity) > 0
                    THEN SUM(billed_amount) / SUM(usage_quantity)
                    ELSE NULL
                END AS unit_price
            FROM {MART_UTILITY_COST_SUMMARY_TABLE}
            GROUP BY period_month, utility_type
        ),
        with_prev AS (
            SELECT
                period_month,
                utility_type,
                usage_amount,
                total_cost,
                unit_price,
                LAG(usage_amount) OVER (
                    PARTITION BY utility_type ORDER BY period_month
                ) AS prev_usage,
                LAG(total_cost) OVER (
                    PARTITION BY utility_type ORDER BY period_month
                ) AS prev_cost,
                LAG(unit_price) OVER (
                    PARTITION BY utility_type ORDER BY period_month
                ) AS prev_unit_price
            FROM monthly_agg
        )
        SELECT
            utility_type,
            period_month AS period,
            CASE WHEN prev_usage > 0
                 THEN CAST(ROUND((usage_amount - prev_usage) / prev_usage * 100, 2) AS DECIMAL(18,4))
                 ELSE NULL
            END AS usage_change_pct,
            CASE WHEN prev_unit_price > 0
                 THEN CAST(ROUND((unit_price - prev_unit_price) / prev_unit_price * 100, 2) AS DECIMAL(18,4))
                 ELSE NULL
            END AS price_change_pct,
            CASE WHEN prev_cost > 0
                 THEN CAST(ROUND((total_cost - prev_cost) / prev_cost * 100, 2) AS DECIMAL(18,4))
                 ELSE NULL
            END AS cost_change_pct,
            CASE
                WHEN prev_unit_price > 0 AND prev_usage > 0 THEN
                    CASE
                        WHEN ABS(unit_price - prev_unit_price) / prev_unit_price
                           > ABS(usage_amount - prev_usage) / prev_usage
                        THEN 'price'
                        ELSE 'usage'
                    END
                WHEN prev_unit_price IS NOT NULL AND prev_unit_price > 0 THEN 'price'
                WHEN prev_usage IS NOT NULL AND prev_usage > 0 THEN 'usage'
                ELSE 'unknown'
            END AS dominant_driver
        FROM with_prev
        WHERE prev_usage IS NOT NULL
        ORDER BY utility_type, period
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_USAGE_VS_PRICE_SUMMARY_TABLE}"
    )[0][0]


def get_usage_vs_price_summary(
    store: DuckDBStore,
    *,
    utility_type: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if utility_type is not None:
        clauses.append("utility_type = ?")
        params.append(utility_type)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_USAGE_VS_PRICE_SUMMARY_TABLE}"
        f" {where_sql} ORDER BY utility_type, period",
        params,
    )


def refresh_contract_review_candidates(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_CONTRACT_REVIEW_CANDIDATES_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_CONTRACT_REVIEW_CANDIDATES_TABLE}
            (contract_id, provider, utility_type, reason, score,
             current_price, market_reference, currency)
        WITH contract_stats AS (
            SELECT
                contract_type,
                AVG(unit_price)            AS avg_price,
                COUNT(DISTINCT contract_id) AS contract_count
            FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}
            WHERE status = 'active'
            GROUP BY contract_type
        ),
        flagged AS (
            SELECT
                c.contract_id,
                c.provider,
                c.contract_type                              AS utility_type,
                c.unit_price                                 AS current_price,
                cs.avg_price                                 AS market_reference,
                c.currency,
                CASE
                    WHEN c.valid_to IS NOT NULL
                         AND c.valid_to <= CURRENT_DATE
                        THEN 'expired_contract'
                    WHEN c.unit_price > cs.avg_price * 1.1
                        THEN 'above_market_average'
                    WHEN c.valid_from <= CURRENT_DATE - INTERVAL '365 days'
                         AND c.valid_to IS NULL
                        THEN 'long_tenure_no_expiry'
                    WHEN cs.contract_count > 1
                        THEN 'multiple_contracts_same_type'
                    ELSE NULL
                END AS reason,
                CASE
                    WHEN c.valid_to IS NOT NULL
                         AND c.valid_to <= CURRENT_DATE           THEN 3
                    WHEN c.unit_price > cs.avg_price * 1.1        THEN 2
                    WHEN c.valid_from <= CURRENT_DATE - INTERVAL '365 days'
                         AND c.valid_to IS NULL                   THEN 1
                    WHEN cs.contract_count > 1                    THEN 1
                    ELSE 0
                END AS score
            FROM {MART_CONTRACT_PRICE_CURRENT_TABLE} c
            JOIN contract_stats cs ON c.contract_type = cs.contract_type
            WHERE c.status = 'active'
        )
        SELECT
            contract_id,
            provider,
            utility_type,
            reason,
            score,
            current_price,
            market_reference,
            currency
        FROM flagged
        WHERE reason IS NOT NULL
        ORDER BY score DESC, contract_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_CONTRACT_REVIEW_CANDIDATES_TABLE}"
    )[0][0]


def get_contract_review_candidates(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_CONTRACT_REVIEW_CANDIDATES_TABLE}"
        " ORDER BY score DESC, contract_id"
    )


def refresh_contract_renewal_watchlist(
    store: DuckDBStore,
    *,
    lookahead_days: int = 90,
) -> int:
    store.execute(f"DELETE FROM {MART_CONTRACT_RENEWAL_WATCHLIST_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_CONTRACT_RENEWAL_WATCHLIST_TABLE}
            (contract_id, contract_name, provider, utility_type, renewal_date,
             days_until_renewal, current_price, currency, contract_duration_days)
        SELECT
            contract_id,
            contract_name,
            provider,
            contract_type                                                AS utility_type,
            valid_to                                                     AS renewal_date,
            CAST(valid_to - CURRENT_DATE AS INTEGER)                     AS days_until_renewal,
            unit_price                                                   AS current_price,
            currency,
            CAST(COALESCE(valid_to, CURRENT_DATE) - valid_from AS INTEGER)
                                                                         AS contract_duration_days
        FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}
        WHERE status = 'active'
          AND valid_to IS NOT NULL
          AND valid_to <= CURRENT_DATE + INTERVAL '{lookahead_days}' DAY
        ORDER BY valid_to, contract_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_CONTRACT_RENEWAL_WATCHLIST_TABLE}"
    )[0][0]


def get_contract_renewal_watchlist(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_CONTRACT_RENEWAL_WATCHLIST_TABLE}"
        " ORDER BY renewal_date, contract_id"
    )


def count_utility_usage(
    store: DuckDBStore,
    *,
    run_id: str | None = None,
) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_UTILITY_USAGE_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_UTILITY_USAGE_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def count_bills(
    store: DuckDBStore,
    *,
    run_id: str | None = None,
) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_BILL_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_BILL_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def _coerce_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
