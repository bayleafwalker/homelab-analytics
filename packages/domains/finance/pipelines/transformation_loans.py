from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from packages.domains.finance.pipelines.amortization import (
    LoanParameters,
    compute_amortization_schedule,
)
from packages.domains.finance.pipelines.loan_models import (
    CURRENT_DIM_LOAN_VIEW,
    FACT_LOAN_REPAYMENT_COLUMNS,
    FACT_LOAN_REPAYMENT_TABLE,
    MART_DEBT_OVERVIEW_COLUMNS,
    MART_DEBT_OVERVIEW_TABLE,
    MART_LOAN_OVERVIEW_COLUMNS,
    MART_LOAN_OVERVIEW_TABLE,
    MART_LOAN_REPAYMENT_VARIANCE_COLUMNS,
    MART_LOAN_REPAYMENT_VARIANCE_TABLE,
    MART_LOAN_SCHEDULE_PROJECTED_COLUMNS,
    MART_LOAN_SCHEDULE_PROJECTED_TABLE,
    extract_loan_dimensions,
    loan_repayment_id,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def ensure_loan_storage(store: DuckDBStore) -> None:
    store.ensure_table(FACT_LOAN_REPAYMENT_TABLE, FACT_LOAN_REPAYMENT_COLUMNS)
    store.ensure_table(MART_LOAN_SCHEDULE_PROJECTED_TABLE, MART_LOAN_SCHEDULE_PROJECTED_COLUMNS)
    store.ensure_table(MART_LOAN_REPAYMENT_VARIANCE_TABLE, MART_LOAN_REPAYMENT_VARIANCE_COLUMNS)
    store.ensure_table(MART_LOAN_OVERVIEW_TABLE, MART_LOAN_OVERVIEW_COLUMNS)
    store.ensure_table(MART_DEBT_OVERVIEW_TABLE, MART_DEBT_OVERVIEW_COLUMNS)


def load_loan_repayments(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    dim_loan,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    eff = effective_date or date.today()

    with store.atomic():
        loan_dims = extract_loan_dimensions(rows)
        loans_upserted = 0
        if loan_dims:
            loans_upserted = store.upsert_dimension_rows(
                dim_loan,
                loan_dims,
                effective_date=eff,
                source_system=source_system,
                source_run_id=run_id,
            )

        fact_rows = []
        for row in rows:
            repayment_date = str(row.get("repayment_date", ""))
            repayment_month = repayment_date[:7] if len(repayment_date) >= 7 else ""
            fact_rows.append(
                {
                    "repayment_id": loan_repayment_id(row["loan_id"], repayment_date),
                    "loan_id": row["loan_id"],
                    "repayment_date": repayment_date,
                    "repayment_month": repayment_month,
                    "payment_amount": row.get("payment_amount", "0"),
                    "principal_portion": row.get("principal_portion"),
                    "interest_portion": row.get("interest_portion"),
                    "extra_amount": row.get("extra_amount"),
                    "currency": row.get("currency", ""),
                    "run_id": run_id,
                }
            )

        inserted = store.insert_rows(FACT_LOAN_REPAYMENT_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_loan", "dimension", loans_upserted),
            ("fact_loan_repayment", "fact", inserted),
        ],
    )
    return inserted


def count_loan_repayments(
    store: DuckDBStore,
    *,
    run_id: str | None = None,
) -> int:
    if run_id is None:
        return store.fetchall(
            f"SELECT COUNT(*) FROM {FACT_LOAN_REPAYMENT_TABLE}"
        )[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_LOAN_REPAYMENT_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def refresh_loan_schedule_projected(store: DuckDBStore) -> int:
    """Read dim_loan parameters and materialise the projected amortization schedule."""
    store.execute(f"DELETE FROM {MART_LOAN_SCHEDULE_PROJECTED_TABLE}")

    loans = store.fetchall_dicts(
        f"SELECT * FROM {CURRENT_DIM_LOAN_VIEW} ORDER BY loan_id"
    )

    inserted_total = 0
    for loan in loans:
        try:
            params = LoanParameters(
                principal=Decimal(str(loan["principal"])),
                annual_rate=Decimal(str(loan["annual_rate"])),
                term_months=int(loan["term_months"]),
                start_date=loan["start_date"],
                payment_frequency=loan.get("payment_frequency", "monthly"),
            )
        except (KeyError, TypeError, ValueError):
            continue

        schedule = compute_amortization_schedule(params)
        rows = [
            {
                "loan_id": loan["loan_id"],
                "loan_name": loan["loan_name"],
                "period": row.period,
                "payment_date": row.payment_date,
                "payment": str(row.payment),
                "principal_portion": str(row.principal_portion),
                "interest_portion": str(row.interest_portion),
                "remaining_balance": str(row.remaining_balance),
                "currency": loan.get("currency", ""),
            }
            for row in schedule
        ]
        if rows:
            store.insert_rows(MART_LOAN_SCHEDULE_PROJECTED_TABLE, rows)
            inserted_total += len(rows)

    return inserted_total


def refresh_loan_repayment_variance(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_LOAN_REPAYMENT_VARIANCE_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_LOAN_REPAYMENT_VARIANCE_TABLE} (
            loan_id, loan_name, repayment_month, projected_payment,
            actual_payment, variance, projected_balance, actual_balance_estimate, currency
        )
        WITH projected_monthly AS (
            SELECT
                loan_id,
                loan_name,
                STRFTIME(payment_date, '%Y-%m') AS repayment_month,
                SUM(payment) AS projected_payment,
                MAX(remaining_balance) AS projected_balance,
                MIN(currency) AS currency
            FROM {MART_LOAN_SCHEDULE_PROJECTED_TABLE}
            GROUP BY loan_id, loan_name, STRFTIME(payment_date, '%Y-%m')
        ),
        actual_monthly AS (
            SELECT
                loan_id,
                repayment_month,
                SUM(payment_amount) AS actual_payment,
                MIN(currency) AS currency
            FROM {FACT_LOAN_REPAYMENT_TABLE}
            GROUP BY loan_id, repayment_month
        )
        SELECT
            p.loan_id,
            p.loan_name,
            p.repayment_month,
            p.projected_payment,
            COALESCE(a.actual_payment, 0) AS actual_payment,
            p.projected_payment - COALESCE(a.actual_payment, 0) AS variance,
            p.projected_balance,
            -- Estimate actual balance = projected_balance + variance accumulated
            p.projected_balance AS actual_balance_estimate,
            p.currency
        FROM projected_monthly p
        LEFT JOIN actual_monthly a
            ON p.loan_id = a.loan_id AND p.repayment_month = a.repayment_month
        ORDER BY p.loan_id, p.repayment_month
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_LOAN_REPAYMENT_VARIANCE_TABLE}"
    )[0][0]


def refresh_loan_overview(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_LOAN_OVERVIEW_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_LOAN_OVERVIEW_TABLE} (
            loan_id, loan_name, lender, original_principal, current_balance_estimate,
            monthly_payment, total_interest_projected, total_interest_paid,
            remaining_months, currency
        )
        SELECT
            l.loan_id,
            l.loan_name,
            l.lender,
            l.principal AS original_principal,
            COALESCE(sched.current_balance, l.principal) AS current_balance_estimate,
            COALESCE(sched.monthly_payment, 0) AS monthly_payment,
            COALESCE(sched.total_interest_projected, 0) AS total_interest_projected,
            COALESCE(paid.total_interest_paid, 0) AS total_interest_paid,
            COALESCE(sched.remaining_months, l.term_months) AS remaining_months,
            l.currency
        FROM {CURRENT_DIM_LOAN_VIEW} l
        LEFT JOIN (
            SELECT
                loan_id,
                MAX(remaining_balance) AS current_balance,
                AVG(payment) AS monthly_payment,
                SUM(interest_portion) AS total_interest_projected,
                COUNT(*) AS remaining_months
            FROM {MART_LOAN_SCHEDULE_PROJECTED_TABLE}
            WHERE remaining_balance > 0
            GROUP BY loan_id
        ) sched ON l.loan_id = sched.loan_id
        LEFT JOIN (
            SELECT
                loan_id,
                SUM(COALESCE(interest_portion, 0)) AS total_interest_paid
            FROM {FACT_LOAN_REPAYMENT_TABLE}
            GROUP BY loan_id
        ) paid ON l.loan_id = paid.loan_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_LOAN_OVERVIEW_TABLE}"
    )[0][0]


def get_loan_schedule_projected(
    store: DuckDBStore,
    loan_id: str | None = None,
) -> list[dict[str, Any]]:
    if loan_id is not None:
        return store.fetchall_dicts(
            f"SELECT * FROM {MART_LOAN_SCHEDULE_PROJECTED_TABLE}"
            " WHERE loan_id = ? ORDER BY period",
            [loan_id],
        )
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_LOAN_SCHEDULE_PROJECTED_TABLE} ORDER BY loan_id, period"
    )


def get_loan_repayment_variance(
    store: DuckDBStore,
    loan_id: str | None = None,
) -> list[dict[str, Any]]:
    if loan_id is not None:
        return store.fetchall_dicts(
            f"SELECT * FROM {MART_LOAN_REPAYMENT_VARIANCE_TABLE}"
            " WHERE loan_id = ? ORDER BY repayment_month",
            [loan_id],
        )
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_LOAN_REPAYMENT_VARIANCE_TABLE} ORDER BY loan_id, repayment_month"
    )


def get_loan_overview(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_LOAN_OVERVIEW_TABLE} ORDER BY loan_name"
    )


def refresh_debt_overview(store: DuckDBStore) -> int:
    """Outstanding debt across instrument types.

    Loans contribute their principal minus repaid principal (typed by
    dim_loan.loan_type). Accounts whose latest cumulative transaction balance
    is negative contribute as 'account_credit' (credit cards and overdrafts
    ride the account-transaction lane). share_of_total_pct is computed within
    each currency so mixed-currency households never mix shares.
    """
    from packages.domains.finance.pipelines.transaction_models import (
        FACT_TRANSACTION_CURRENT_TABLE,
    )

    store.execute(f"DELETE FROM {MART_DEBT_OVERVIEW_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_DEBT_OVERVIEW_TABLE} (
            debt_type, instrument_id, instrument_name, lender,
            original_principal, outstanding_balance, currency,
            share_of_total_pct
        )
        WITH paid_principal AS (
            SELECT
                loan_id,
                SUM(
                    COALESCE(
                        principal_portion + COALESCE(extra_amount, 0),
                        payment_amount - COALESCE(interest_portion, 0),
                        0
                    )
                )               AS principal_paid,
                MIN(currency)   AS currency
            FROM {FACT_LOAN_REPAYMENT_TABLE}
            GROUP BY loan_id
        ),
        loan_debt AS (
            SELECT
                COALESCE(l.loan_type, 'loan')     AS debt_type,
                l.loan_id                         AS instrument_id,
                l.loan_name                       AS instrument_name,
                l.lender,
                l.principal                       AS original_principal,
                GREATEST(
                    COALESCE(l.principal, 0) - COALESCE(p.principal_paid, 0),
                    0
                )                                 AS outstanding_balance,
                COALESCE(p.currency, l.currency)  AS currency
            FROM {CURRENT_DIM_LOAN_VIEW} l
            LEFT JOIN paid_principal p ON p.loan_id = l.loan_id
            WHERE COALESCE(l.principal, 0) > 0
        ),
        account_monthly AS (
            SELECT
                account_id,
                SUM(SUM(amount)) OVER (
                    PARTITION BY account_id ORDER BY booking_month
                )                                 AS cumulative_balance,
                MIN(normalized_currency)          AS currency,
                ROW_NUMBER() OVER (
                    PARTITION BY account_id ORDER BY booking_month DESC
                )                                 AS rn
            FROM {FACT_TRANSACTION_CURRENT_TABLE}
            GROUP BY booking_month, account_id
        ),
        account_debt AS (
            SELECT
                'account_credit'                  AS debt_type,
                account_id                        AS instrument_id,
                account_id                        AS instrument_name,
                CAST(NULL AS VARCHAR)             AS lender,
                CAST(NULL AS DECIMAL(18,4))       AS original_principal,
                -cumulative_balance               AS outstanding_balance,
                currency
            FROM account_monthly
            WHERE rn = 1
              AND cumulative_balance < 0
        ),
        combined AS (
            SELECT * FROM loan_debt
            WHERE outstanding_balance > 0
            UNION ALL
            SELECT * FROM account_debt
        )
        SELECT
            debt_type,
            instrument_id,
            instrument_name,
            lender,
            original_principal,
            outstanding_balance,
            currency,
            ROUND(
                outstanding_balance * 100.0
                    / SUM(outstanding_balance) OVER (PARTITION BY currency),
                3
            ) AS share_of_total_pct
        FROM combined
        ORDER BY debt_type, instrument_id
        """
    )
    return store.fetchall(f"SELECT COUNT(*) FROM {MART_DEBT_OVERVIEW_TABLE}")[0][0]


def get_debt_overview(
    store: DuckDBStore,
    *,
    debt_type: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if debt_type is not None:
        clauses.append("debt_type = ?")
        params.append(debt_type)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_DEBT_OVERVIEW_TABLE}"
        f" {where_sql} ORDER BY debt_type, instrument_id",
        params,
    )
