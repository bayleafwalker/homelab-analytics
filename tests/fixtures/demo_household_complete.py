"""Demo household fixture generator.

Generates realistic 12-month datasets for all built-in domains:
- Account transactions: salary income + 8 expense categories
- Subscriptions: 4 active services
- Utility bills: electricity + water, 12 months
- Contract prices: electricity tariff + broadband
- Budget targets: 4 categories
- Loan repayments: mortgage, 3 months of actuals

Call generate_all() to get a dict of {domain: csv_bytes}.
"""
from __future__ import annotations

import csv
import io

# ---------------------------------------------------------------------------
# Account transactions — 12 months of income + expenses
# ---------------------------------------------------------------------------

def _make_transactions() -> bytes:
    rows = []
    months = [
        ("2025-01", "2025-01-01", "2025-01-03"),
        ("2025-02", "2025-02-01", "2025-02-03"),
        ("2025-03", "2025-03-01", "2025-03-03"),
        ("2025-04", "2025-04-01", "2025-04-03"),
        ("2025-05", "2025-05-01", "2025-05-03"),
        ("2025-06", "2025-06-01", "2025-06-03"),
        ("2025-07", "2025-07-01", "2025-07-03"),
        ("2025-08", "2025-08-01", "2025-08-03"),
        ("2025-09", "2025-09-01", "2025-09-03"),
        ("2025-10", "2025-10-01", "2025-10-03"),
        ("2025-11", "2025-11-01", "2025-11-03"),
        ("2025-12", "2025-12-01", "2025-12-03"),
    ]
    expenses = [
        ("Supermarket Plus", "-280.00", "groceries"),
        ("City Power", "-85.00", "utilities"),
        ("Metro Transport", "-60.00", "transport"),
        ("Netflix Inc.", "-15.99", "entertainment"),
        ("Restaurant Roma", "-45.00", "dining"),
        ("Pharmacy Central", "-22.50", "health"),
        ("Book Store", "-18.00", "education"),
        ("Gym Membership", "-35.00", "health"),
    ]
    for (month, salary_date, expense_base_date) in months:
        rows.append({
            "booked_at": salary_date,
            "account_id": "CHK-001",
            "counterparty_name": "Employer Corp",
            "amount": "3200.00",
            "currency": "EUR",
            "description": "Monthly salary",
        })
        for i, (name, amount, category) in enumerate(expenses):
            day = str(5 + i).zfill(2)
            rows.append({
                "booked_at": f"{month}-{day}",
                "account_id": "CHK-001",
                "counterparty_name": name,
                "amount": amount,
                "currency": "EUR",
                "description": category,
            })
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["booked_at", "account_id", "counterparty_name", "amount", "currency", "description"])
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def _make_subscriptions() -> bytes:
    rows = [
        {"service_name": "Netflix", "provider": "Netflix Inc.", "billing_cycle": "monthly", "amount": "15.99", "currency": "EUR", "start_date": "2023-01-15", "end_date": ""},
        {"service_name": "Spotify", "provider": "Spotify AB", "billing_cycle": "monthly", "amount": "9.99", "currency": "EUR", "start_date": "2022-06-01", "end_date": ""},
        {"service_name": "iCloud 50GB", "provider": "Apple Inc.", "billing_cycle": "monthly", "amount": "1.29", "currency": "EUR", "start_date": "2021-03-10", "end_date": ""},
        {"service_name": "GitHub Pro", "provider": "GitHub Inc.", "billing_cycle": "annual", "amount": "48.00", "currency": "USD", "start_date": "2023-07-01", "end_date": ""},
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["service_name", "provider", "billing_cycle", "amount", "currency", "start_date", "end_date"])
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# Utility bills — electricity + water, 12 months
# ---------------------------------------------------------------------------

def _make_utility_bills() -> bytes:
    rows = []
    elec_amounts = [48.08, 52.30, 61.45, 57.20, 42.10, 38.50, 35.90, 38.20, 44.10, 53.80, 59.40, 63.15]
    water_amounts = [19.35, 18.90, 20.10, 21.50, 22.80, 24.10, 25.30, 24.90, 22.40, 20.80, 19.60, 18.75]
    elec_kwh = [320.5, 348.7, 409.7, 381.3, 280.7, 256.7, 239.3, 254.7, 294.0, 358.7, 396.0, 421.0]
    water_liters = [11900, 11600, 12400, 13200, 14000, 14800, 15600, 15300, 13800, 12800, 12000, 11500]
    months = [
        ("2025-01-01", "2025-01-31", "2025-02-05"),
        ("2025-02-01", "2025-02-28", "2025-03-05"),
        ("2025-03-01", "2025-03-31", "2025-04-05"),
        ("2025-04-01", "2025-04-30", "2025-05-05"),
        ("2025-05-01", "2025-05-31", "2025-06-05"),
        ("2025-06-01", "2025-06-30", "2025-07-05"),
        ("2025-07-01", "2025-07-31", "2025-08-05"),
        ("2025-08-01", "2025-08-31", "2025-09-05"),
        ("2025-09-01", "2025-09-30", "2025-10-05"),
        ("2025-10-01", "2025-10-31", "2025-11-05"),
        ("2025-11-01", "2025-11-30", "2025-12-05"),
        ("2025-12-01", "2025-12-31", "2026-01-05"),
    ]
    for i, (start, end, invoiced) in enumerate(months):
        rows.append({
            "meter_id": "elec-001",
            "meter_name": "Main Electricity Meter",
            "provider": "City Power",
            "utility_type": "electricity",
            "location": "home",
            "billing_period_start": start,
            "billing_period_end": end,
            "billed_amount": f"{elec_amounts[i]:.2f}",
            "currency": "EUR",
            "billed_quantity": f"{elec_kwh[i]:.1f}",
            "usage_unit": "kWh",
            "invoice_date": invoiced,
        })
        rows.append({
            "meter_id": "water-001",
            "meter_name": "Cold Water Meter",
            "provider": "City Water",
            "utility_type": "water",
            "location": "home",
            "billing_period_start": start,
            "billing_period_end": end,
            "billed_amount": f"{water_amounts[i]:.2f}",
            "currency": "EUR",
            "billed_quantity": f"{water_liters[i]}",
            "usage_unit": "liter",
            "invoice_date": invoiced,
        })
    buf = io.StringIO()
    fields = ["meter_id", "meter_name", "provider", "utility_type", "location", "billing_period_start", "billing_period_end", "billed_amount", "currency", "billed_quantity", "usage_unit", "invoice_date"]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# Contract prices
# ---------------------------------------------------------------------------

def _make_contract_prices() -> bytes:
    rows = [
        {"contract_name": "Helen Spot", "provider": "Helen", "contract_type": "electricity", "price_component": "energy", "billing_cycle": "per_kwh", "unit_price": "0.0825", "currency": "EUR", "quantity_unit": "kWh", "valid_from": "2025-01-01", "valid_to": ""},
        {"contract_name": "Helen Spot", "provider": "Helen", "contract_type": "electricity", "price_component": "base_fee", "billing_cycle": "monthly", "unit_price": "5.99", "currency": "EUR", "quantity_unit": "", "valid_from": "2025-01-01", "valid_to": ""},
        {"contract_name": "Fiber 1000", "provider": "ISP Oy", "contract_type": "broadband", "price_component": "monthly_fee", "billing_cycle": "monthly", "unit_price": "39.90", "currency": "EUR", "quantity_unit": "", "valid_from": "2024-06-01", "valid_to": ""},
    ]
    buf = io.StringIO()
    fields = ["contract_name", "provider", "contract_type", "price_component", "billing_cycle", "unit_price", "currency", "quantity_unit", "valid_from", "valid_to"]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# Budget targets
# ---------------------------------------------------------------------------

def _make_budgets() -> bytes:
    rows = [
        {"budget_name": "Monthly Budget", "category": "groceries", "period_type": "monthly", "target_amount": "350.00", "currency": "EUR", "effective_from": "2025-01", "effective_to": ""},
        {"budget_name": "Monthly Budget", "category": "entertainment", "period_type": "monthly", "target_amount": "50.00", "currency": "EUR", "effective_from": "2025-01", "effective_to": ""},
        {"budget_name": "Monthly Budget", "category": "transport", "period_type": "monthly", "target_amount": "80.00", "currency": "EUR", "effective_from": "2025-01", "effective_to": ""},
        {"budget_name": "Monthly Budget", "category": "utilities", "period_type": "monthly", "target_amount": "120.00", "currency": "EUR", "effective_from": "2025-01", "effective_to": ""},
        {"budget_name": "Monthly Budget", "category": "dining", "period_type": "monthly", "target_amount": "60.00", "currency": "EUR", "effective_from": "2025-01", "effective_to": ""},
    ]
    buf = io.StringIO()
    fields = ["budget_name", "category", "period_type", "target_amount", "currency", "effective_from", "effective_to"]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# Loan repayments — mortgage (25yr, 4.5%) with 3 months actuals
# ---------------------------------------------------------------------------

def _make_loan_repayments() -> bytes:
    rows = [
        {
            "loan_id": "mortgage-001",
            "loan_name": "Home Mortgage",
            "lender": "First National Bank",
            "loan_type": "mortgage",
            "principal": "280000.00",
            "annual_rate": "0.045",
            "term_months": "300",
            "start_date": "2022-01-01",
            "payment_frequency": "monthly",
            "repayment_date": "2025-10-01",
            "payment_amount": "1557.00",
            "principal_portion": "514.50",
            "interest_portion": "1042.50",
            "extra_amount": "",
            "currency": "EUR",
        },
        {
            "loan_id": "mortgage-001",
            "loan_name": "Home Mortgage",
            "lender": "First National Bank",
            "loan_type": "mortgage",
            "principal": "280000.00",
            "annual_rate": "0.045",
            "term_months": "300",
            "start_date": "2022-01-01",
            "payment_frequency": "monthly",
            "repayment_date": "2025-11-01",
            "payment_amount": "1557.00",
            "principal_portion": "516.43",
            "interest_portion": "1040.57",
            "extra_amount": "",
            "currency": "EUR",
        },
        {
            "loan_id": "mortgage-001",
            "loan_name": "Home Mortgage",
            "lender": "First National Bank",
            "loan_type": "mortgage",
            "principal": "280000.00",
            "annual_rate": "0.045",
            "term_months": "300",
            "start_date": "2022-01-01",
            "payment_frequency": "monthly",
            "repayment_date": "2025-12-01",
            "payment_amount": "1557.00",
            "principal_portion": "518.37",
            "interest_portion": "1038.63",
            "extra_amount": "",
            "currency": "EUR",
        },
    ]
    buf = io.StringIO()
    fields = ["loan_id", "loan_name", "lender", "loan_type", "principal", "annual_rate", "term_months", "start_date", "payment_frequency", "repayment_date", "payment_amount", "principal_portion", "interest_portion", "extra_amount", "currency"]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_all() -> dict[str, bytes]:
    return {
        "account_transactions": _make_transactions(),
        "subscriptions": _make_subscriptions(),
        "utility_bills": _make_utility_bills(),
        "contract_prices": _make_contract_prices(),
        "budgets": _make_budgets(),
        "loan_repayments": _make_loan_repayments(),
    }
