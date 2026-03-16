from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from packages.pipelines.transaction_models import (
    FACT_TRANSACTION_COLUMNS,
    FACT_TRANSACTION_TABLE,
    MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
    MART_MONTHLY_CASHFLOW_COLUMNS,
    MART_MONTHLY_CASHFLOW_TABLE,
    TRANSFORMATION_AUDIT_COLUMNS,
    TRANSFORMATION_AUDIT_TABLE,
    extract_accounts,
    extract_counterparties,
)
from packages.storage.duckdb_store import DuckDBStore

NormalizeRow = Callable[[dict[str, Any]], dict[str, Any]]
RecordLineage = Callable[..., None]


def ensure_transaction_storage(store: DuckDBStore) -> None:
    store.ensure_table(FACT_TRANSACTION_TABLE, FACT_TRANSACTION_COLUMNS)
    store.ensure_table(MART_MONTHLY_CASHFLOW_TABLE, MART_MONTHLY_CASHFLOW_COLUMNS)
    store.ensure_table(
        MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
        MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
    )
    store.ensure_table(TRANSFORMATION_AUDIT_TABLE, TRANSFORMATION_AUDIT_COLUMNS)


def load_transactions(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    normalize_row: NormalizeRow,
    record_lineage: RecordLineage,
    dim_account,
    dim_counterparty,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    normalized_rows = [normalize_row(row) for row in rows]
    eff = effective_date or date.today()
    started_at = datetime.now(UTC)

    with store.atomic():
        accounts = extract_accounts(normalized_rows)
        accounts_upserted = store.upsert_dimension_rows(
            dim_account,
            accounts,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        counterparties = extract_counterparties(normalized_rows)
        counterparties_upserted = store.upsert_dimension_rows(
            dim_counterparty,
            counterparties,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        fact_rows = []
        for row in normalized_rows:
            booked_at_utc = row["booked_at_utc"]
            booked_at = booked_at_utc.date()
            amount = row["amount"]
            if isinstance(amount, str):
                amount = Decimal(amount)
            elif isinstance(amount, float):
                amount = Decimal(str(amount))

            fact_rows.append(
                {
                    "transaction_id": _transaction_id(
                        booked_at,
                        row["account_id"],
                        row["counterparty_name"],
                        amount,
                    ),
                    "booked_at": booked_at,
                    "booked_at_utc": booked_at_utc,
                    "booking_month": booked_at.strftime("%Y-%m"),
                    "account_id": row["account_id"],
                    "counterparty_name": row["counterparty_name"],
                    "amount": amount,
                    "currency": row["currency"],
                    "normalized_currency": row["normalized_currency"],
                    "description": row.get("description", ""),
                    "direction": row["direction"],
                    "run_id": run_id,
                }
            )

        inserted = store.insert_rows(FACT_TRANSACTION_TABLE, fact_rows)

    completed_at = datetime.now(UTC)
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    store.insert_rows(
        TRANSFORMATION_AUDIT_TABLE,
        [
            {
                "audit_id": uuid.uuid4().hex[:16],
                "input_run_id": run_id,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "fact_rows": inserted,
                "accounts_upserted": accounts_upserted,
                "counterparties_upserted": counterparties_upserted,
            }
        ],
    )
    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_account", "dimension", accounts_upserted),
            ("dim_counterparty", "dimension", counterparties_upserted),
            ("fact_transaction", "fact", inserted),
        ],
    )
    return inserted


def refresh_monthly_cashflow(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_MONTHLY_CASHFLOW_TABLE}")

    store.execute(
        f"""
        INSERT INTO {MART_MONTHLY_CASHFLOW_TABLE}
            (booking_month, income, expense, net, transaction_count)
        SELECT
            booking_month,
            COALESCE(SUM(CASE WHEN amount >= 0 THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS expense,
            COALESCE(SUM(amount), 0) AS net,
            COUNT(*) AS transaction_count
        FROM {FACT_TRANSACTION_TABLE}
        GROUP BY booking_month
        ORDER BY booking_month
        """
    )
    return store.fetchall(f"SELECT COUNT(*) FROM {MART_MONTHLY_CASHFLOW_TABLE}")[0][0]


def get_monthly_cashflow(
    store: DuckDBStore,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if from_month is not None:
        clauses.append("booking_month >= ?")
        params.append(from_month)
    if to_month is not None:
        clauses.append("booking_month <= ?")
        params.append(to_month)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_MONTHLY_CASHFLOW_TABLE} {where_sql} ORDER BY booking_month",
        params,
    )


def get_transactions(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {FACT_TRANSACTION_TABLE} ORDER BY booked_at, account_id"
    )


def count_transactions(
    store: DuckDBStore,
    *,
    run_id: str | None = None,
) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_TRANSACTION_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_TRANSACTION_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def refresh_monthly_cashflow_by_counterparty(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_CASHFLOW_BY_COUNTERPARTY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_CASHFLOW_BY_COUNTERPARTY_TABLE}
            (booking_month, counterparty_name, income, expense, net, transaction_count)
        SELECT
            booking_month,
            counterparty_name,
            COALESCE(SUM(CASE WHEN amount >= 0 THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS expense,
            COALESCE(SUM(amount), 0) AS net,
            COUNT(*) AS transaction_count
        FROM {FACT_TRANSACTION_TABLE}
        GROUP BY booking_month, counterparty_name
        ORDER BY booking_month, counterparty_name
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_CASHFLOW_BY_COUNTERPARTY_TABLE}"
    )[0][0]


def get_monthly_cashflow_by_counterparty(
    store: DuckDBStore,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
    counterparty_name: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if from_month is not None:
        clauses.append("booking_month >= ?")
        params.append(from_month)
    if to_month is not None:
        clauses.append("booking_month <= ?")
        params.append(to_month)
    if counterparty_name is not None:
        clauses.append("counterparty_name = ?")
        params.append(counterparty_name)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_CASHFLOW_BY_COUNTERPARTY_TABLE}"
        f" {where_sql} ORDER BY booking_month, counterparty_name",
        params,
    )


def _transaction_id(
    booked_at: date,
    account_id: str,
    counterparty_name: str,
    amount: Decimal,
) -> str:
    raw = f"{booked_at.isoformat()}|{account_id}|{counterparty_name}|{amount}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
