-- 0013_finance_debt_subscription_mart_publications: publication definitions
-- for the domain-marts-fillout finance track. SQLite control planes seed
-- these from BUILTIN_TRANSFORMATION_PACKAGE_SPECS at ensure-schema time;
-- Postgres control planes track builtin catalog additions through migrations.

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
    ('pub_loans_debt_overview', 'builtin_loan_repayments', 'mart_debt_overview', 'Debt overview mart', NULL, FALSE, NOW()),
    ('pub_subscriptions_changes', 'builtin_subscriptions', 'mart_subscription_changes', 'Subscription changes mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
