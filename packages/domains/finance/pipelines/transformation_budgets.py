from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from packages.domains.finance.pipelines.budget_models import (
    FACT_BUDGET_TARGET_COLUMNS,
    FACT_BUDGET_TARGET_TABLE,
    MART_BUDGET_ENVELOPE_DRIFT_COLUMNS,
    MART_BUDGET_ENVELOPE_DRIFT_TABLE,
    MART_BUDGET_PROGRESS_CURRENT_COLUMNS,
    MART_BUDGET_PROGRESS_CURRENT_TABLE,
    MART_BUDGET_VARIANCE_COLUMNS,
    MART_BUDGET_VARIANCE_TABLE,
    budget_target_id,
    extract_budgets,
)
from packages.domains.finance.pipelines.transaction_models import (
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def _ensure_column(
    store: DuckDBStore,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    existing_columns = {
        row[1] for row in store.connection.execute(
            f"PRAGMA table_info('{table_name}')"
        ).fetchall()
    }
    if column_name not in existing_columns:
        store.connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


def ensure_budget_storage(store: DuckDBStore) -> None:
    store.ensure_table(FACT_BUDGET_TARGET_TABLE, FACT_BUDGET_TARGET_COLUMNS)
    store.ensure_table(MART_BUDGET_VARIANCE_TABLE, MART_BUDGET_VARIANCE_COLUMNS)
    store.ensure_table(
        MART_BUDGET_PROGRESS_CURRENT_TABLE, MART_BUDGET_PROGRESS_CURRENT_COLUMNS,
    )
    store.ensure_table(
        MART_BUDGET_ENVELOPE_DRIFT_TABLE,
        MART_BUDGET_ENVELOPE_DRIFT_COLUMNS,
    )
    _ensure_column(store, MART_BUDGET_VARIANCE_TABLE, "state", "VARCHAR")
    _ensure_column(store, MART_BUDGET_PROGRESS_CURRENT_TABLE, "state", "VARCHAR")
    _ensure_column(store, MART_BUDGET_ENVELOPE_DRIFT_TABLE, "state", "VARCHAR")


def load_budget_targets(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    dim_budget,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    eff = effective_date or date.today()

    with store.atomic():
        budgets = extract_budgets(rows)
        budgets_upserted = store.upsert_dimension_rows(
            dim_budget,
            budgets,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        fact_rows = []
        for row in rows:
            fact_rows.append(
                {
                    "target_id": budget_target_id(
                        row["budget_name"],
                        row["category_id"],
                        row["period_label"],
                    ),
                    "budget_id": row["budget_id"],
                    "budget_name": row["budget_name"],
                    "category_id": row["category_id"],
                    "period_type": row.get("period_type", "monthly"),
                    "period_label": row["period_label"],
                    "target_amount": row["target_amount"],
                    "currency": row.get("currency", ""),
                    "run_id": run_id,
                }
            )

        inserted = store.insert_rows(FACT_BUDGET_TARGET_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_budget", "dimension", budgets_upserted),
            ("fact_budget_target", "fact", inserted),
        ],
    )
    return inserted


def count_budget_targets(
    store: DuckDBStore,
    *,
    run_id: str | None = None,
) -> int:
    if run_id is None:
        return store.fetchall(
            f"SELECT COUNT(*) FROM {FACT_BUDGET_TARGET_TABLE}"
        )[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_BUDGET_TARGET_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def refresh_budget_variance(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_BUDGET_VARIANCE_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_BUDGET_VARIANCE_TABLE} (
            budget_name, category_id, period_label, target_amount,
            actual_amount, variance, variance_pct, status, state, currency
        )
        SELECT
            b.budget_name,
            b.category_id,
            b.period_label,
            b.target_amount,
            COALESCE(s.total_expense, 0) AS actual_amount,
            b.target_amount - COALESCE(s.total_expense, 0) AS variance,
            CASE
                WHEN b.target_amount = 0 THEN NULL
                ELSE ROUND(
                    (COALESCE(s.total_expense, 0) - b.target_amount) * 100.0
                    / b.target_amount,
                    2
                )
            END AS variance_pct,
            CASE
                WHEN COALESCE(s.total_expense, 0) <= b.target_amount * 0.9
                    THEN 'under_budget'
                WHEN COALESCE(s.total_expense, 0) <= b.target_amount
                    THEN 'on_budget'
                ELSE 'over_budget'
            END AS status,
            CASE
                WHEN COALESCE(s.total_expense, 0) <= b.target_amount * 0.9
                    THEN 'good'
                WHEN COALESCE(s.total_expense, 0) <= b.target_amount
                    THEN 'warning'
                ELSE 'needs_action'
            END AS state,
            b.currency
        FROM {FACT_BUDGET_TARGET_TABLE} b
        LEFT JOIN (
            SELECT
                LOWER(COALESCE(category, counterparty_name)) AS category_id,
                booking_month,
                ABS(total_expense) AS total_expense
            FROM {MART_SPEND_BY_CATEGORY_MONTHLY_TABLE}
        ) s
            ON b.category_id = s.category_id
            AND b.period_label = s.booking_month
        ORDER BY b.budget_name, b.period_label
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_BUDGET_VARIANCE_TABLE}"
    )[0][0]


def get_budget_variance(
    store: DuckDBStore,
    *,
    budget_name: str | None = None,
    category_id: str | None = None,
    period_label: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if budget_name is not None:
        clauses.append("budget_name = ?")
        params.append(budget_name)
    if category_id is not None:
        clauses.append("category_id = ?")
        params.append(category_id)
    if period_label is not None:
        clauses.append("period_label = ?")
        params.append(period_label)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_BUDGET_VARIANCE_TABLE}"
        f" {where_sql} ORDER BY budget_name, period_label",
        params,
    )


def refresh_budget_progress_current(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_BUDGET_PROGRESS_CURRENT_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_BUDGET_PROGRESS_CURRENT_TABLE} (
            budget_name, category_id, target_amount, spent_amount,
            remaining, utilization_pct, state, currency
        )
        SELECT
            budget_name,
            category_id,
            target_amount,
            actual_amount AS spent_amount,
            variance AS remaining,
            CASE
                WHEN target_amount = 0 THEN 0
                ELSE ROUND(actual_amount * 100.0 / target_amount, 2)
            END AS utilization_pct,
            CASE
                WHEN target_amount = 0 THEN 'warning'
                WHEN actual_amount <= target_amount * 0.9 THEN 'good'
                WHEN actual_amount <= target_amount THEN 'warning'
                ELSE 'needs_action'
            END AS state,
            currency
        FROM {MART_BUDGET_VARIANCE_TABLE}
        WHERE period_label = (
            SELECT COALESCE(MAX(period_label), STRFTIME(CURRENT_DATE, '%Y-%m'))
            FROM {MART_BUDGET_VARIANCE_TABLE}
        )
        ORDER BY budget_name, category_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_BUDGET_PROGRESS_CURRENT_TABLE}"
    )[0][0]


def refresh_budget_envelope_drift(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_BUDGET_ENVELOPE_DRIFT_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_BUDGET_ENVELOPE_DRIFT_TABLE} (
            budget_name, category_id, period_label, envelope_amount,
            actual_amount, drift_amount, drift_pct, drift_state, state, currency
        )
        SELECT
            budget_name,
            category_id,
            period_label,
            target_amount AS envelope_amount,
            actual_amount,
            actual_amount - target_amount AS drift_amount,
            CASE
                WHEN target_amount = 0 THEN NULL
                ELSE ROUND(
                    (actual_amount - target_amount) * 100.0 / target_amount,
                    2
                )
            END AS drift_pct,
            CASE
                WHEN actual_amount <= target_amount * 0.9 THEN 'under_target'
                WHEN actual_amount <= target_amount THEN 'on_target'
                ELSE 'over_target'
            END AS drift_state,
            CASE
                WHEN actual_amount <= target_amount * 0.9 THEN 'good'
                WHEN actual_amount <= target_amount THEN 'warning'
                ELSE 'needs_action'
            END AS state,
            currency
        FROM {MART_BUDGET_VARIANCE_TABLE}
        ORDER BY budget_name, period_label
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_BUDGET_ENVELOPE_DRIFT_TABLE}"
    )[0][0]


def get_budget_envelope_drift(
    store: DuckDBStore,
    *,
    budget_name: str | None = None,
    category_id: str | None = None,
    period_label: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if budget_name is not None:
        clauses.append("budget_name = ?")
        params.append(budget_name)
    if category_id is not None:
        clauses.append("category_id = ?")
        params.append(category_id)
    if period_label is not None:
        clauses.append("period_label = ?")
        params.append(period_label)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_BUDGET_ENVELOPE_DRIFT_TABLE}"
        f" {where_sql} ORDER BY budget_name, period_label",
        params,
    )


def get_budget_progress_current(
    store: DuckDBStore,
) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_BUDGET_PROGRESS_CURRENT_TABLE}"
        " ORDER BY budget_name, category_id"
    )
