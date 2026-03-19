from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from packages.pipelines.subscription_models import (
    FACT_SUBSCRIPTION_CHARGE_COLUMNS,
    FACT_SUBSCRIPTION_CHARGE_TABLE,
    MART_SUBSCRIPTION_SUMMARY_COLUMNS,
    MART_SUBSCRIPTION_SUMMARY_TABLE,
    MART_UPCOMING_FIXED_COSTS_30D_COLUMNS,
    MART_UPCOMING_FIXED_COSTS_30D_TABLE,
    extract_contracts,
    subscription_charge_id,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def ensure_subscription_storage(store: DuckDBStore) -> None:
    store.ensure_table(FACT_SUBSCRIPTION_CHARGE_TABLE, FACT_SUBSCRIPTION_CHARGE_COLUMNS)
    store.ensure_table(MART_SUBSCRIPTION_SUMMARY_TABLE, MART_SUBSCRIPTION_SUMMARY_COLUMNS)
    store.ensure_table(
        MART_UPCOMING_FIXED_COSTS_30D_TABLE, MART_UPCOMING_FIXED_COSTS_30D_COLUMNS
    )


def load_subscriptions(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    dim_contract,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    eff = effective_date or date.today()

    with store.atomic():
        contracts = extract_contracts(rows)
        contracts_upserted = store.upsert_dimension_rows(
            dim_contract,
            contracts,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        fact_rows = []
        for row in rows:
            fact_rows.append(
                {
                    "charge_id": subscription_charge_id(
                        row["service_name"],
                        row.get("billing_cycle", "monthly"),
                        row.get("start_date"),
                    ),
                    "contract_id": row["contract_id"],
                    "contract_name": row["service_name"],
                    "provider": row.get("provider", ""),
                    "billing_cycle": row.get("billing_cycle", "monthly"),
                    "amount": row["amount"],
                    "currency": row.get("currency", ""),
                    "start_date": row["start_date"],
                    "end_date": row.get("end_date"),
                    "run_id": run_id,
                }
            )

        inserted = store.insert_rows(FACT_SUBSCRIPTION_CHARGE_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_contract", "dimension", contracts_upserted),
            ("fact_subscription_charge", "fact", inserted),
        ],
    )
    return inserted


def refresh_subscription_summary(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_SUBSCRIPTION_SUMMARY_TABLE} (
            contract_id, contract_name, provider, billing_cycle, amount, currency,
            start_date, end_date, monthly_equivalent, status
        )
        SELECT
            contract_id,
            contract_name,
            provider,
            billing_cycle,
            amount,
            currency,
            start_date,
            end_date,
            CASE billing_cycle
                WHEN 'monthly' THEN CAST(amount AS DECIMAL(18,4))
                WHEN 'annual'  THEN ROUND(amount / 12, 4)
                WHEN 'weekly'  THEN ROUND(amount * 52 / 12, 4)
                ELSE CAST(amount AS DECIMAL(18,4))
            END AS monthly_equivalent,
            CASE
                WHEN end_date IS NULL OR end_date >= current_date THEN 'active'
                ELSE 'inactive'
            END AS status
        FROM {FACT_SUBSCRIPTION_CHARGE_TABLE}
        ORDER BY contract_name
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}"
    )[0][0]


def get_subscription_summary(
    store: DuckDBStore,
    *,
    status: str | None = None,
    currency: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if currency is not None:
        clauses.append("currency = ?")
        params.append(currency)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}"
        f" {where_sql} ORDER BY contract_name",
        params,
    )


def count_subscriptions(
    store: DuckDBStore,
    *,
    run_id: str | None = None,
) -> int:
    if run_id is None:
        return store.fetchall(
            f"SELECT COUNT(*) FROM {FACT_SUBSCRIPTION_CHARGE_TABLE}"
        )[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_SUBSCRIPTION_CHARGE_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def refresh_upcoming_fixed_costs_30d(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_UPCOMING_FIXED_COSTS_30D_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_UPCOMING_FIXED_COSTS_30D_TABLE}
            (contract_name, provider, frequency, expected_amount, currency,
             expected_date, confidence)
        WITH next_charges AS (
            SELECT
                contract_name,
                provider,
                billing_cycle,
                amount,
                currency,
                CASE billing_cycle
                    WHEN 'monthly' THEN
                        CASE
                            WHEN DATE_TRUNC('month', CURRENT_DATE)::DATE
                                 + (CAST(date_part('day', start_date) AS INTEGER) - 1)
                                 >= CURRENT_DATE
                            THEN DATE_TRUNC('month', CURRENT_DATE)::DATE
                                 + (CAST(date_part('day', start_date) AS INTEGER) - 1)
                            ELSE (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')::DATE
                                 + (CAST(date_part('day', start_date) AS INTEGER) - 1)
                        END
                    WHEN 'annual' THEN
                        CASE
                            WHEN MAKE_DATE(
                                    CAST(date_part('year', CURRENT_DATE) AS INTEGER),
                                    CAST(date_part('month', start_date) AS INTEGER),
                                    CAST(date_part('day', start_date) AS INTEGER)
                                 ) >= CURRENT_DATE
                            THEN MAKE_DATE(
                                    CAST(date_part('year', CURRENT_DATE) AS INTEGER),
                                    CAST(date_part('month', start_date) AS INTEGER),
                                    CAST(date_part('day', start_date) AS INTEGER)
                                 )
                            ELSE MAKE_DATE(
                                    CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1,
                                    CAST(date_part('month', start_date) AS INTEGER),
                                    CAST(date_part('day', start_date) AS INTEGER)
                                 )
                        END
                    WHEN 'weekly' THEN
                        start_date + INTERVAL '7 days' * CAST(CEIL(
                            (CURRENT_DATE - start_date)::DOUBLE / 7.0
                        ) AS INTEGER)
                END AS expected_date,
                CASE billing_cycle
                    WHEN 'annual' THEN 'estimated'
                    ELSE 'high'
                END AS confidence
            FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}
            WHERE status = 'active'
        )
        SELECT
            contract_name,
            provider,
            billing_cycle AS frequency,
            amount        AS expected_amount,
            currency,
            expected_date,
            confidence
        FROM next_charges
        WHERE billing_cycle IN ('monthly', 'weekly')
           OR expected_date <= CURRENT_DATE + INTERVAL '30 days'
        ORDER BY expected_date, contract_name
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_UPCOMING_FIXED_COSTS_30D_TABLE}"
    )[0][0]


def get_upcoming_fixed_costs_30d(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_UPCOMING_FIXED_COSTS_30D_TABLE}"
        " ORDER BY expected_date, contract_name"
    )
