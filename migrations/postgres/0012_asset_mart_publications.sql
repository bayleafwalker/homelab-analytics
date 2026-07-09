-- 0012_asset_mart_publications: publication definitions for the
-- domain-marts-fillout assets track. SQLite control planes seed these from
-- BUILTIN_TRANSFORMATION_PACKAGE_SPECS at ensure-schema time; Postgres
-- control planes track builtin catalog additions through migrations.

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
    ('pub_asset_register_asset_value', 'builtin_asset_register', 'mart_asset_value', 'Asset value mart', NULL, FALSE, NOW()),
    ('pub_asset_register_depreciation_schedule', 'builtin_asset_register', 'mart_depreciation_schedule', 'Depreciation schedule mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
