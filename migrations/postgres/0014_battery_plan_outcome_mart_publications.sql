-- 0014_battery_plan_outcome_mart_publications: publication definitions for
-- the household outcome evidence loop (Kotiakku battery-plan decision).
-- SQLite control planes seed these from BUILTIN_TRANSFORMATION_PACKAGE_SPECS at
-- ensure-schema time; Postgres control planes track builtin catalog additions
-- through migrations.

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
    ('pub_utility_battery_plan_outcome', 'builtin_utility_usage', 'mart_battery_plan_outcome', 'Battery plan outcome mart', NULL, FALSE, NOW()),
    ('pub_utility_battery_plan_outcome_values', 'builtin_utility_usage', 'mart_battery_plan_outcome_values', 'Battery plan outcome values mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
