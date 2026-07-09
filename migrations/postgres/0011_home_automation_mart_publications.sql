-- 0011_home_automation_mart_publications: publication definitions for the
-- domain-marts-fillout home-automation track. SQLite control planes seed
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
    ('pub_homelab_climate_summary', 'builtin_homelab', 'mart_climate_summary', 'Climate summary mart', NULL, FALSE, NOW()),
    ('pub_homelab_automation_reliability', 'builtin_homelab', 'mart_automation_reliability', 'Automation reliability mart', NULL, FALSE, NOW()),
    ('pub_homelab_device_battery', 'builtin_homelab', 'mart_device_battery', 'Device battery mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
