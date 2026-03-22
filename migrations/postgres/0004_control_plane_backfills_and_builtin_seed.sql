-- 0004_control_plane_backfills_and_builtin_seed: legacy backfills + builtin catalog seed
-- Moves compatibility-column backfills and builtin package/publication seeding into
-- tracked Postgres migrations so control-plane schema evolution is SQL-owned.

ALTER TABLE source_systems ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE dataset_contracts ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE column_mappings ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE transformation_packages ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE publication_definitions ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE source_assets ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE source_assets ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE ingestion_definitions ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE execution_schedules ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE schedule_dispatches ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE schedule_dispatches ADD COLUMN IF NOT EXISTS run_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE schedule_dispatches ADD COLUMN IF NOT EXISTS failure_reason TEXT;
ALTER TABLE schedule_dispatches ADD COLUMN IF NOT EXISTS worker_detail TEXT;
ALTER TABLE schedule_dispatches ADD COLUMN IF NOT EXISTS claimed_by_worker_id TEXT;
ALTER TABLE schedule_dispatches ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;
ALTER TABLE schedule_dispatches ADD COLUMN IF NOT EXISTS claim_expires_at TIMESTAMPTZ;

INSERT INTO transformation_packages (
    transformation_package_id,
    name,
    handler_key,
    version,
    description,
    archived,
    created_at
)
VALUES
    ('builtin_account_transactions', 'Built-in account transactions', 'account_transactions', 1, 'Canonical account transaction transformation and reporting flow.', FALSE, NOW()),
    ('builtin_subscriptions', 'Built-in subscriptions', 'subscriptions', 1, 'Recurring subscription transformation and summary publications.', FALSE, NOW()),
    ('builtin_contract_prices', 'Built-in contract prices', 'contract_prices', 1, 'Contract pricing and electricity tariff transformation and publications.', FALSE, NOW()),
    ('builtin_utility_usage', 'Built-in utility usage', 'utility_usage', 1, 'Utility usage transformation and reporting publications.', FALSE, NOW()),
    ('builtin_utility_bills', 'Built-in utility bills', 'utility_bills', 1, 'Utility bill transformation and reporting publications.', FALSE, NOW()),
    ('builtin_budgets', 'Built-in budgets', 'budgets', 1, 'Budget target and variance transformation and publications.', FALSE, NOW()),
    ('builtin_loan_repayments', 'Built-in loan repayments', 'loan_repayments', 1, 'Loan repayment transformation, amortization schedule, and overview publications.', FALSE, NOW()),
    ('builtin_homelab', 'Built-in homelab', 'homelab', 1, 'Homelab service health, backup freshness, storage risk, and workload cost publications.', FALSE, NOW())
ON CONFLICT (transformation_package_id) DO NOTHING;

INSERT INTO publication_definitions (
    publication_definition_id,
    transformation_package_id,
    publication_key,
    name,
    description,
    archived,
    created_at
)
VALUES
    ('pub_account_transactions_monthly_cashflow', 'builtin_account_transactions', 'mart_monthly_cashflow', 'Monthly cashflow mart', NULL, FALSE, NOW()),
    ('pub_account_transactions_counterparty_cashflow', 'builtin_account_transactions', 'mart_monthly_cashflow_by_counterparty', 'Monthly cashflow by counterparty mart', NULL, FALSE, NOW()),
    ('pub_account_transactions_current_accounts', 'builtin_account_transactions', 'rpt_current_dim_account', 'Current account view', NULL, FALSE, NOW()),
    ('pub_account_transactions_current_counterparties', 'builtin_account_transactions', 'rpt_current_dim_counterparty', 'Current counterparty view', NULL, FALSE, NOW()),
    ('pub_account_transactions_spend_by_category', 'builtin_account_transactions', 'mart_spend_by_category_monthly', 'Spend by category monthly mart', NULL, FALSE, NOW()),
    ('pub_account_transactions_recent_large', 'builtin_account_transactions', 'mart_recent_large_transactions', 'Recent large transactions mart', NULL, FALSE, NOW()),
    ('pub_account_transactions_balance_trend', 'builtin_account_transactions', 'mart_account_balance_trend', 'Account balance trend mart', NULL, FALSE, NOW()),
    ('pub_account_transactions_anomalies_current', 'builtin_account_transactions', 'mart_transaction_anomalies_current', 'Transaction anomalies current mart', NULL, FALSE, NOW()),
    ('pub_subscriptions_summary', 'builtin_subscriptions', 'mart_subscription_summary', 'Subscription summary mart', NULL, FALSE, NOW()),
    ('pub_subscriptions_upcoming_fixed_costs', 'builtin_subscriptions', 'mart_upcoming_fixed_costs_30d', 'Upcoming fixed costs (30-day) mart', NULL, FALSE, NOW()),
    ('pub_subscriptions_current_contracts', 'builtin_subscriptions', 'rpt_current_dim_contract', 'Current contract view', NULL, FALSE, NOW()),
    ('pub_contract_prices_current', 'builtin_contract_prices', 'mart_contract_price_current', 'Current contract price mart', NULL, FALSE, NOW()),
    ('pub_contract_prices_electricity_current', 'builtin_contract_prices', 'mart_electricity_price_current', 'Current electricity price mart', NULL, FALSE, NOW()),
    ('pub_contract_prices_current_contracts', 'builtin_contract_prices', 'rpt_current_dim_contract', 'Current contract view', NULL, FALSE, NOW()),
    ('pub_contract_prices_review_candidates', 'builtin_contract_prices', 'mart_contract_review_candidates', 'Contract review candidates mart', NULL, FALSE, NOW()),
    ('pub_contract_prices_renewal_watchlist', 'builtin_contract_prices', 'mart_contract_renewal_watchlist', 'Contract renewal watchlist mart', NULL, FALSE, NOW()),
    ('pub_utility_usage_summary', 'builtin_utility_usage', 'mart_utility_cost_summary', 'Utility cost summary mart', NULL, FALSE, NOW()),
    ('pub_utility_usage_cost_trend', 'builtin_utility_usage', 'mart_utility_cost_trend_monthly', 'Utility cost trend monthly mart', NULL, FALSE, NOW()),
    ('pub_utility_usage_vs_price', 'builtin_utility_usage', 'mart_usage_vs_price_summary', 'Usage vs price summary mart', NULL, FALSE, NOW()),
    ('pub_utility_usage_current_meters', 'builtin_utility_usage', 'rpt_current_dim_meter', 'Current meter view', NULL, FALSE, NOW()),
    ('pub_utility_bills_summary', 'builtin_utility_bills', 'mart_utility_cost_summary', 'Utility cost summary mart', NULL, FALSE, NOW()),
    ('pub_utility_bills_cost_trend', 'builtin_utility_bills', 'mart_utility_cost_trend_monthly', 'Utility cost trend monthly mart', NULL, FALSE, NOW()),
    ('pub_utility_bills_vs_price', 'builtin_utility_bills', 'mart_usage_vs_price_summary', 'Usage vs price summary mart', NULL, FALSE, NOW()),
    ('pub_utility_bills_current_meters', 'builtin_utility_bills', 'rpt_current_dim_meter', 'Current meter view', NULL, FALSE, NOW()),
    ('pub_budgets_variance', 'builtin_budgets', 'mart_budget_variance', 'Budget variance mart', NULL, FALSE, NOW()),
    ('pub_budgets_progress_current', 'builtin_budgets', 'mart_budget_progress_current', 'Budget progress current mart', NULL, FALSE, NOW()),
    ('pub_budgets_current_budgets', 'builtin_budgets', 'rpt_current_dim_budget', 'Current budget view', NULL, FALSE, NOW()),
    ('pub_loans_schedule_projected', 'builtin_loan_repayments', 'mart_loan_schedule_projected', 'Loan schedule projected mart', NULL, FALSE, NOW()),
    ('pub_loans_repayment_variance', 'builtin_loan_repayments', 'mart_loan_repayment_variance', 'Loan repayment variance mart', NULL, FALSE, NOW()),
    ('pub_loans_overview', 'builtin_loan_repayments', 'mart_loan_overview', 'Loan overview mart', NULL, FALSE, NOW()),
    ('pub_loans_current_loans', 'builtin_loan_repayments', 'rpt_current_dim_loan', 'Current loan view', NULL, FALSE, NOW()),
    ('pub_homelab_service_health_current', 'builtin_homelab', 'mart_service_health_current', 'Service health current mart', NULL, FALSE, NOW()),
    ('pub_homelab_backup_freshness', 'builtin_homelab', 'mart_backup_freshness', 'Backup freshness mart', NULL, FALSE, NOW()),
    ('pub_homelab_storage_risk', 'builtin_homelab', 'mart_storage_risk', 'Storage risk mart', NULL, FALSE, NOW()),
    ('pub_homelab_workload_cost_7d', 'builtin_homelab', 'mart_workload_cost_7d', 'Workload cost 7-day rolling mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
