from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from packages.domains.finance.pipelines.transaction_models import (
    BANK_TRANSACTION_IDENTITY_STRATEGY,
    CURRENT_DIM_COUNTERPARTY_VIEW,
    FACT_TRANSACTION_COLUMNS,
    FACT_TRANSACTION_CURRENT_TABLE,
    FACT_TRANSACTION_TABLE,
    INGEST_BATCH_COLUMNS,
    INGEST_BATCH_TABLE,
    MART_ACCOUNT_BALANCE_TREND_COLUMNS,
    MART_ACCOUNT_BALANCE_TREND_TABLE,
    MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
    MART_MONTHLY_CASHFLOW_COLUMNS,
    MART_MONTHLY_CASHFLOW_TABLE,
    MART_RECENT_LARGE_TRANSACTIONS_COLUMNS,
    MART_RECENT_LARGE_TRANSACTIONS_TABLE,
    MART_SPEND_BY_CATEGORY_MONTHLY_COLUMNS,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
    MART_TRANSACTION_ANOMALIES_CURRENT_COLUMNS,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
    TRANSACTION_OBSERVATION_COLUMNS,
    TRANSACTION_OBSERVATION_TABLE,
    TRANSFORMATION_AUDIT_COLUMNS,
    TRANSFORMATION_AUDIT_TABLE,
    extract_accounts,
    extract_counterparties,
)
from packages.pipelines.identity_strategy import (
    IdentityStrategy,
    resolve_entity_key,
)
from packages.pipelines.reconciliation import (
    ReconciliationResult,
    ensure_entity_storage,
    reconcile_batch,
)

# Re-export so callers can import these from transformation_transactions
__all__ = [
    "ensure_transaction_storage",
    "load_transactions",
    "ensure_entity_storage",
    "reconcile_batch",
    "ReconciliationResult",
]
from packages.storage.duckdb_store import DuckDBStore

NormalizeRow = Callable[[dict[str, Any]], dict[str, Any]]
RecordLineage = Callable[..., None]


def ensure_transaction_storage(store: DuckDBStore) -> None:
    store.ensure_table(INGEST_BATCH_TABLE, INGEST_BATCH_COLUMNS)
    store.ensure_table(TRANSACTION_OBSERVATION_TABLE, TRANSACTION_OBSERVATION_COLUMNS)
    ensure_entity_storage(store)
    store.ensure_table(FACT_TRANSACTION_TABLE, FACT_TRANSACTION_COLUMNS)
    store.ensure_table(MART_MONTHLY_CASHFLOW_TABLE, MART_MONTHLY_CASHFLOW_COLUMNS)
    store.ensure_table(
        MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
        MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
    )
    store.ensure_table(
        MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
        MART_SPEND_BY_CATEGORY_MONTHLY_COLUMNS,
    )
    store.ensure_table(
        MART_RECENT_LARGE_TRANSACTIONS_TABLE,
        MART_RECENT_LARGE_TRANSACTIONS_COLUMNS,
    )
    store.ensure_table(
        MART_ACCOUNT_BALANCE_TREND_TABLE,
        MART_ACCOUNT_BALANCE_TREND_COLUMNS,
    )
    store.ensure_table(
        MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
        MART_TRANSACTION_ANOMALIES_CURRENT_COLUMNS,
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
    category_resolver: dict[str, str | None] | None = None,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
    batch_sha256: str | None = None,
    source_asset_id: str | None = None,
    identity_strategy: IdentityStrategy | None = None,
) -> tuple[int, str]:
    if not rows:
        return 0, ""

    normalized_rows = [normalize_row(row) for row in rows]
    eff = effective_date or date.today()
    started_at = datetime.now(UTC)
    strategy = identity_strategy or BANK_TRANSACTION_IDENTITY_STRATEGY
    bid = _batch_id(source_asset_id, batch_sha256, run_id)

    with store.atomic():
        # -- Immutable batch record (idempotent) -----------------------------
        store.execute(
            f"""
            INSERT INTO {INGEST_BATCH_TABLE}
                (batch_id, run_id, source_asset_id, file_sha256, row_count, landed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            [bid, run_id, source_asset_id, batch_sha256, len(normalized_rows), started_at],
        )

        accounts = extract_accounts(normalized_rows)
        accounts_upserted = store.upsert_dimension_rows(
            dim_account,
            accounts,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        counterparties = extract_counterparties(
            normalized_rows,
            category_resolver=category_resolver,
        )
        counterparties_upserted = store.upsert_dimension_rows(
            dim_counterparty,
            counterparties,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        fact_rows = []
        for ordinal, row in enumerate(normalized_rows):
            booked_at_utc = row["booked_at_utc"]
            booked_at = booked_at_utc.date()
            amount = row["amount"]
            if isinstance(amount, str):
                amount = Decimal(amount)
            elif isinstance(amount, float):
                amount = Decimal(str(amount))

            norm_json = _normalized_observation_json({**row, "booked_at": booked_at, "amount": amount})
            obs_id = _observation_id(bid, ordinal, norm_json)

            # Resolve entity key via identity strategy; surface failures as
            # NULL rather than aborting the batch.
            entity_key: str | None = None
            match_tier: int | None = None
            confidence: float | None = None
            try:
                result = resolve_entity_key(
                    {**row, "booked_at": booked_at.isoformat(), "amount": str(amount)},
                    strategy,
                )
                entity_key = result.entity_key
                match_tier = result.match_tier
                confidence = float(result.confidence)
            except ValueError:
                pass

            # -- Immutable observation row (idempotent) ----------------------
            store.execute(
                f"""
                INSERT INTO {TRANSACTION_OBSERVATION_TABLE}
                    (observation_id, batch_id, row_ordinal, entity_key, match_tier,
                     confidence, booked_at, account_id, counterparty_name, amount,
                     currency, description, normalized_row_json, observed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                [
                    obs_id, bid, ordinal, entity_key, match_tier,
                    confidence, booked_at, row["account_id"], row["counterparty_name"], amount,
                    row["currency"], row.get("description", ""), norm_json, started_at,
                ],
            )

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

        # Insert facts, skipping rows whose transaction_id already exists.
        # Duplicate IDs arise when overlapping bank statements are re-loaded;
        # the observation layer already captured the evidence — the fact table
        # should reflect the current best-known state and not error out.
        inserted = store.insert_rows_or_ignore(FACT_TRANSACTION_TABLE, fact_rows)

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
    return inserted, bid


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
        FROM {FACT_TRANSACTION_CURRENT_TABLE}
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
        FROM {FACT_TRANSACTION_CURRENT_TABLE}
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


def refresh_spend_by_category_monthly(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_SPEND_BY_CATEGORY_MONTHLY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_SPEND_BY_CATEGORY_MONTHLY_TABLE}
            (booking_month, counterparty_name, category, total_expense, transaction_count)
        SELECT
            ft.booking_month,
            ft.counterparty_name,
            dc.category,
            COALESCE(SUM(ABS(ft.amount)), 0) AS total_expense,
            COUNT(*) AS transaction_count
        FROM {FACT_TRANSACTION_CURRENT_TABLE} ft
        LEFT JOIN {CURRENT_DIM_COUNTERPARTY_VIEW} dc
            ON ft.counterparty_name = dc.counterparty_name
        WHERE ft.direction = 'expense'
        GROUP BY ft.booking_month, ft.counterparty_name, dc.category
        ORDER BY ft.booking_month, total_expense DESC
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_SPEND_BY_CATEGORY_MONTHLY_TABLE}"
    )[0][0]


def get_spend_by_category_monthly(
    store: DuckDBStore,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
    counterparty_name: str | None = None,
    category: str | None = None,
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
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_SPEND_BY_CATEGORY_MONTHLY_TABLE}"
        f" {where_sql} ORDER BY booking_month, total_expense DESC",
        params,
    )


def refresh_recent_large_transactions(
    store: DuckDBStore,
    *,
    threshold: Decimal = Decimal("100"),
    lookback_months: int = 3,
) -> int:
    store.execute(f"DELETE FROM {MART_RECENT_LARGE_TRANSACTIONS_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_RECENT_LARGE_TRANSACTIONS_TABLE}
            (transaction_id, booked_at, booking_month, account_id,
             counterparty_name, amount, currency, description, direction)
        SELECT
            entity_key AS transaction_id, booked_at, booking_month, account_id,
            counterparty_name, amount, currency, description, direction
        FROM {FACT_TRANSACTION_CURRENT_TABLE}
        WHERE ABS(amount) >= ?
          AND booked_at >= CURRENT_DATE - INTERVAL '{lookback_months}' MONTH
        ORDER BY ABS(amount) DESC
        """,
        [threshold],
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_RECENT_LARGE_TRANSACTIONS_TABLE}"
    )[0][0]


def get_recent_large_transactions(
    store: DuckDBStore,
) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_RECENT_LARGE_TRANSACTIONS_TABLE}"
        " ORDER BY ABS(amount) DESC, booked_at DESC"
    )


def refresh_account_balance_trend(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_ACCOUNT_BALANCE_TREND_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_ACCOUNT_BALANCE_TREND_TABLE}
            (booking_month, account_id, net_change, cumulative_balance, transaction_count)
        SELECT
            booking_month,
            account_id,
            SUM(amount) AS net_change,
            SUM(SUM(amount)) OVER (
                PARTITION BY account_id ORDER BY booking_month
            ) AS cumulative_balance,
            COUNT(*) AS transaction_count
        FROM {FACT_TRANSACTION_CURRENT_TABLE}
        GROUP BY booking_month, account_id
        ORDER BY booking_month, account_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_ACCOUNT_BALANCE_TREND_TABLE}"
    )[0][0]


def get_account_balance_trend(
    store: DuckDBStore,
    *,
    account_id: str | None = None,
    from_month: str | None = None,
    to_month: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if account_id is not None:
        clauses.append("account_id = ?")
        params.append(account_id)
    if from_month is not None:
        clauses.append("booking_month >= ?")
        params.append(from_month)
    if to_month is not None:
        clauses.append("booking_month <= ?")
        params.append(to_month)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_ACCOUNT_BALANCE_TREND_TABLE}"
        f" {where_sql} ORDER BY booking_month, account_id",
        params,
    )


def refresh_transaction_anomalies_current(
    store: DuckDBStore,
    *,
    lookback_days: int = 90,
    first_occurrence_threshold: Decimal = Decimal("50"),
    spike_stddev_multiplier: float = 2.0,
) -> int:
    store.execute(f"DELETE FROM {MART_TRANSACTION_ANOMALIES_CURRENT_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_TRANSACTION_ANOMALIES_CURRENT_TABLE}
            (transaction_id, booking_date, counterparty_name, amount, direction,
             anomaly_type, anomaly_reason)
        WITH counterparty_stats AS (
            SELECT
                counterparty_name,
                AVG(ABS(amount))    AS avg_amount,
                STDDEV(ABS(amount)) AS stddev_amount,
                COUNT(*)            AS tx_count
            FROM {FACT_TRANSACTION_CURRENT_TABLE}
            GROUP BY counterparty_name
        ),
        flagged AS (
            SELECT
                t.entity_key         AS transaction_id,
                t.booked_at          AS booking_date,
                t.counterparty_name,
                t.amount,
                t.direction,
                cs.avg_amount,
                cs.stddev_amount,
                cs.tx_count,
                CASE
                    WHEN cs.tx_count = 1
                         AND ABS(t.amount) >= {float(first_occurrence_threshold)}
                        THEN 'first_occurrence'
                    WHEN cs.stddev_amount > 0
                         AND ABS(t.amount) > cs.avg_amount + {spike_stddev_multiplier} * cs.stddev_amount
                        THEN 'amount_spike'
                    ELSE NULL
                END AS anomaly_type
            FROM {FACT_TRANSACTION_CURRENT_TABLE} t
            JOIN counterparty_stats cs ON t.counterparty_name = cs.counterparty_name
            WHERE t.booked_at >= CURRENT_DATE - INTERVAL '{lookback_days}' DAY
        )
        SELECT
            transaction_id,
            booking_date,
            counterparty_name,
            amount,
            direction,
            anomaly_type,
            CASE anomaly_type
                WHEN 'first_occurrence'
                    THEN 'First transaction with this counterparty'
                WHEN 'amount_spike'
                    THEN 'Amount above typical average of ' || ROUND(avg_amount, 2)
                ELSE ''
            END AS anomaly_reason
        FROM flagged
        WHERE anomaly_type IS NOT NULL
        ORDER BY booking_date DESC, ABS(amount) DESC
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_TRANSACTION_ANOMALIES_CURRENT_TABLE}"
    )[0][0]


def get_transaction_anomalies_current(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_TRANSACTION_ANOMALIES_CURRENT_TABLE}"
        " ORDER BY booking_date DESC, ABS(amount) DESC"
    )


def _transaction_id(
    booked_at: date,
    account_id: str,
    counterparty_name: str,
    amount: Decimal,
) -> str:
    raw = f"{booked_at.isoformat()}|{account_id}|{counterparty_name}|{amount}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Observation layer helpers
# ---------------------------------------------------------------------------


def _batch_id(source_asset_id: str | None, file_sha256: str | None, run_id: str | None) -> str:
    """Derive a stable batch identifier.

    Content-addressed when *source_asset_id* and *file_sha256* are both
    provided (same bytes = same batch, regardless of run_id).  Falls back
    to a truncated *run_id* so callers that do not have file metadata still
    get a unique identifier.
    """
    if source_asset_id and file_sha256:
        raw = f"{source_asset_id}|{file_sha256}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    return (run_id or uuid.uuid4().hex)[:16]


def _observation_id(batch_id: str, row_ordinal: int, normalized_row_json: str) -> str:
    raw = f"{batch_id}|{row_ordinal}|{normalized_row_json}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def populate_counterparty_category_ids(store: DuckDBStore) -> int:
    """Backfill category_id on current dim_counterparty rows by joining dim_category.

    Matches ``dim_counterparty.category`` (free-text bridge) against
    ``dim_category.display_name``. Only updates rows where ``category_id``
    is NULL, so it is idempotent and safe to call repeatedly.

    Returns the number of rows updated.
    """
    result = store.connection.execute(
        """
        UPDATE dim_counterparty AS cp
        SET category_id = dc.category_id
        FROM dim_category AS dc
        WHERE cp.is_current = TRUE
          AND dc.is_current = TRUE
          AND cp.category IS NOT NULL
          AND cp.category = dc.display_name
          AND cp.category_id IS NULL
        """
    )
    row = result.fetchone()
    return int(row[0]) if row else 0


def _normalized_observation_json(row: dict[str, Any]) -> str:
    """Stable, canonical JSON encoding of the business fields of a row."""
    return json.dumps(
        {
            "booked_at": str(row.get("booked_at", "")),
            "account_id": str(row.get("account_id", "")),
            "counterparty_name": str(row.get("counterparty_name", "")),
            "amount": str(row.get("amount", "")),
            "currency": str(row.get("currency", "")),
            "description": str(row.get("description") or ""),
        },
        sort_keys=True,
    )
