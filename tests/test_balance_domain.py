"""Tests for the balance snapshot fact."""

from __future__ import annotations

import pytest

from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

TRANSACTION_ROWS = [
    {
        "booked_at": "2026-01-02",
        "account_id": "CHK-001",
        "counterparty_name": "Electric Utility",
        "amount": "-84.15",
        "currency": "EUR",
        "description": "Monthly bill",
    },
    {
        "booked_at": "2026-01-03",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": "2026-02-02",
        "account_id": "CHK-001",
        "counterparty_name": "Electric Utility",
        "amount": "-86.50",
        "currency": "EUR",
        "description": "Monthly bill",
    },
    {
        "booked_at": "2026-02-03",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
]

LOAN_ROWS = [
    {
        "loan_id": "loan-001",
        "loan_name": "Test Mortgage",
        "lender": "Test Bank",
        "loan_type": "mortgage",
        "principal": "200000.00",
        "annual_rate": "0.045",
        "term_months": "240",
        "start_date": "2023-01-01",
        "payment_frequency": "monthly",
        "repayment_date": "2026-01-01",
        "repayment_month": "2026-01",
        "payment_amount": "1265.00",
        "principal_portion": "515.00",
        "interest_portion": "750.00",
        "extra_amount": None,
        "currency": "EUR",
    },
    {
        "loan_id": "loan-001",
        "loan_name": "Test Mortgage",
        "lender": "Test Bank",
        "loan_type": "mortgage",
        "principal": "200000.00",
        "annual_rate": "0.045",
        "term_months": "240",
        "start_date": "2023-01-01",
        "payment_frequency": "monthly",
        "repayment_date": "2026-02-01",
        "repayment_month": "2026-02",
        "payment_amount": "1265.00",
        "principal_portion": "517.00",
        "interest_portion": "748.00",
        "extra_amount": None,
        "currency": "EUR",
    },
]


def test_refresh_balance_snapshot_inserts_account_and_loan_rows() -> None:
    svc = TransformationService(DuckDBStore.memory())
    svc.load_transactions(TRANSACTION_ROWS, run_id="transactions-run")
    svc.load_loan_repayments(LOAN_ROWS, run_id="loan-run")

    count = svc.refresh_balance_snapshot()

    assert count == 2
    rows = svc.get_balance_snapshot()
    assert [row["balance_kind"] for row in rows] == ["account", "loan"]

    account = next(row for row in rows if row["balance_kind"] == "account")
    loan = next(row for row in rows if row["balance_kind"] == "loan")

    assert account["entity_id"] == "CHK-001"
    assert float(account["balance_amount"]) == pytest.approx(4729.35)

    assert loan["entity_id"] == "loan-001"
    assert float(loan["balance_amount"]) == pytest.approx(198968.0)


def test_refresh_balance_snapshot_is_idempotent() -> None:
    svc = TransformationService(DuckDBStore.memory())
    svc.load_transactions(TRANSACTION_ROWS)
    svc.load_loan_repayments(LOAN_ROWS)

    svc.refresh_balance_snapshot()
    svc.refresh_balance_snapshot()

    rows = svc.get_balance_snapshot()
    assert len(rows) == 2
