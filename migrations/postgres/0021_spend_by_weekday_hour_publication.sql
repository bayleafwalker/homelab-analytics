-- 0021_spend_by_weekday_hour_publication: publication definition for the
-- spend heatmap mart (GET /reports/spend-heatmap). SQLite control planes seed
-- this from BUILTIN_TRANSFORMATION_PACKAGE_SPECS at ensure-schema time;
-- Postgres control planes track builtin catalog additions through migrations.
-- Without this row account-transaction promotions refresh the mart but never
-- publish it to the Postgres reporting store.

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
    ('pub_account_transactions_spend_by_weekday_hour', 'builtin_account_transactions', 'mart_spend_by_weekday_hour', 'Spend by weekday and hour mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
