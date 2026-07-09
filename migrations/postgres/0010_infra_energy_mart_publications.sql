-- 0010_infra_energy_mart_publications: publication definitions for the
-- domain-marts-fillout infra track. SQLite control planes seed these from
-- BUILTIN_TRANSFORMATION_PACKAGE_SPECS at ensure-schema time; Postgres control
-- planes track builtin catalog additions through migrations (see 0004).

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
    ('pub_utility_usage_energy_daily', 'builtin_utility_usage', 'mart_energy_daily', 'Energy daily breakdown mart', NULL, FALSE, NOW()),
    ('pub_homelab_cluster_utilization', 'builtin_homelab', 'mart_cluster_utilization', 'Cluster utilization mart', NULL, FALSE, NOW()),
    ('pub_homelab_uptime_summary', 'builtin_homelab', 'mart_uptime_summary', 'Uptime summary mart', NULL, FALSE, NOW()),
    ('pub_homelab_infra_cost', 'builtin_homelab', 'mart_infra_cost', 'Infrastructure cost mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
