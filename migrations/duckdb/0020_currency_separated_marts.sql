-- 0020_currency_separated_marts: one row per denomination in monetary marts.
--
-- Monetary reporting marts keep separate totals per currency and never
-- convert between them. The affected marts are derived tables, so existing
-- rows cannot be attributed to a currency and are rebuilt from facts by
-- `python -m apps.worker.main upgrade-reporting` (the supported upgrade for an
-- installed store; it applies this same DDL for the recognised legacy shape,
-- then refreshes the marts and republishes). The column is nullable here so
-- the ALTER succeeds on populated tables; freshly created tables declare it
-- NOT NULL and the rebuild populates every row. Fact tables are untouched.
--
-- contract_version marks reporting_publication_snapshot rows. Rows written
-- before this migration keep NULL and their bytes are never rewritten: reads
-- report them as legacy_denomination_unavailable instead of guessing a
-- currency.

ALTER TABLE mart_monthly_cashflow ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE mart_monthly_cashflow_by_counterparty ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE mart_spend_by_category_monthly ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE mart_account_balance_trend ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE mart_spend_by_weekday_hour ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE mart_transaction_anomalies_current ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE mart_recent_significant_changes ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE mart_usage_vs_price_summary ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE reporting_publication_snapshot ADD COLUMN IF NOT EXISTS contract_version VARCHAR;
