-- 0022_budget_envelope_drift_publication: publication definition for the
-- budget envelope drift mart. SQLite control planes seed this from
-- BUILTIN_TRANSFORMATION_PACKAGE_SPECS at ensure-schema time; Postgres control
-- planes track builtin catalog additions through migrations. Without this row
-- budget promotions refresh the mart but never publish it to the Postgres
-- reporting store.

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
    ('pub_budgets_envelope_drift', 'builtin_budgets', 'mart_budget_envelope_drift', 'Budget envelope drift mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
