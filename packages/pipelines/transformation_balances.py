from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from packages.pipelines.balance_models import (
    FACT_BALANCE_SNAPSHOT_COLUMNS,
    FACT_BALANCE_SNAPSHOT_TABLE,
)
from packages.pipelines.loan_models import CURRENT_DIM_LOAN_VIEW, FACT_LOAN_REPAYMENT_TABLE
from packages.pipelines.transaction_models import FACT_TRANSACTION_CURRENT_TABLE
from packages.storage.duckdb_store import DuckDBStore


def ensure_balance_storage(store: DuckDBStore) -> None:
    store.ensure_table(FACT_BALANCE_SNAPSHOT_TABLE, FACT_BALANCE_SNAPSHOT_COLUMNS)


def _snapshot_id(snapshot_date: date, balance_kind: str, entity_id: str) -> str:
    raw = f"{snapshot_date.isoformat()}|{balance_kind}|{entity_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _current_account_balances(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"""
        WITH account_monthly AS (
            SELECT
                booking_month,
                account_id,
                SUM(amount) AS net_change,
                SUM(SUM(amount)) OVER (
                    PARTITION BY account_id ORDER BY booking_month
                ) AS cumulative_balance,
                MIN(normalized_currency) AS currency,
                ROW_NUMBER() OVER (
                    PARTITION BY account_id ORDER BY booking_month DESC
                ) AS rn
            FROM {FACT_TRANSACTION_CURRENT_TABLE}
            GROUP BY booking_month, account_id
        )
        SELECT
            account_id AS entity_id,
            account_id AS entity_label,
            cumulative_balance AS balance_amount,
            currency
        FROM account_monthly
        WHERE rn = 1
        ORDER BY account_id
        """
    )


def _current_loan_balances(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"""
        WITH paid_principal AS (
            SELECT
                loan_id,
                SUM(
                    COALESCE(
                        principal_portion + COALESCE(extra_amount, 0),
                        payment_amount - COALESCE(interest_portion, 0),
                        0
                    )
                ) AS principal_paid,
                MIN(currency) AS currency
            FROM {FACT_LOAN_REPAYMENT_TABLE}
            GROUP BY loan_id
        )
        SELECT
            l.loan_id AS entity_id,
            l.loan_name AS entity_label,
            GREATEST(
                COALESCE(l.principal, 0) - COALESCE(p.principal_paid, 0),
                0
            ) AS balance_amount,
            COALESCE(p.currency, l.currency) AS currency
        FROM {CURRENT_DIM_LOAN_VIEW} l
        LEFT JOIN paid_principal p
            ON l.loan_id = p.loan_id
        WHERE COALESCE(l.principal, 0) > 0 OR COALESCE(p.principal_paid, 0) > 0
        ORDER BY l.loan_id
        """
    )


def refresh_balance_snapshot(
    store: DuckDBStore,
    *,
    snapshot_date: date | None = None,
) -> int:
    effective_date = snapshot_date or date.today()
    rows: list[dict[str, Any]] = []

    for balance_kind, source_rows in (
        ("account", _current_account_balances(store)),
        ("loan", _current_loan_balances(store)),
    ):
        for row in source_rows:
            entity_id = str(row["entity_id"])
            rows.append(
                {
                    "snapshot_id": _snapshot_id(effective_date, balance_kind, entity_id),
                    "snapshot_date": effective_date,
                    "balance_kind": balance_kind,
                    "entity_id": entity_id,
                    "entity_label": row.get("entity_label"),
                    "balance_amount": str(row["balance_amount"]),
                    "currency": row.get("currency", ""),
                    "run_id": None,
                }
            )

    store.execute(f"DELETE FROM {FACT_BALANCE_SNAPSHOT_TABLE}")
    if rows:
        store.insert_rows(FACT_BALANCE_SNAPSHOT_TABLE, rows)
    return len(rows)


def get_balance_snapshot(
    store: DuckDBStore,
    *,
    balance_kind: str | None = None,
) -> list[dict[str, Any]]:
    if balance_kind is not None:
        return store.fetchall_dicts(
            f"SELECT * FROM {FACT_BALANCE_SNAPSHOT_TABLE}"
            " WHERE balance_kind = ? ORDER BY balance_kind, entity_id",
            [balance_kind],
        )
    return store.fetchall_dicts(
        f"SELECT * FROM {FACT_BALANCE_SNAPSHOT_TABLE} ORDER BY balance_kind, entity_id"
    )
