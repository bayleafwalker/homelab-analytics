-- 0014_finance_debt_subscription_marts: mart tables for the
-- domain-marts-fillout finance track. mart_debt_overview and
-- mart_subscription_changes. Rebuilt via DELETE + INSERT on refresh.

CREATE TABLE IF NOT EXISTS mart_debt_overview (
    debt_type VARCHAR NOT NULL,
    instrument_id VARCHAR NOT NULL,
    instrument_name VARCHAR,
    lender VARCHAR,
    original_principal DECIMAL(18,4),
    outstanding_balance DECIMAL(18,4) NOT NULL,
    currency VARCHAR,
    share_of_total_pct DECIMAL(6,3)
);

CREATE TABLE IF NOT EXISTS mart_subscription_changes (
    period_month VARCHAR NOT NULL,
    change_type VARCHAR NOT NULL,
    contract_id VARCHAR NOT NULL,
    contract_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    billing_cycle VARCHAR NOT NULL,
    amount DECIMAL(18,4) NOT NULL,
    monthly_equivalent DECIMAL(18,4) NOT NULL,
    currency VARCHAR NOT NULL,
    effective_date DATE NOT NULL
);
