-- 0012_asset_mart_publications: publication definitions for the
-- domain-marts-fillout assets track. SQLite control planes seed these from
-- BUILTIN_TRANSFORMATION_PACKAGE_SPECS at ensure-schema time; Postgres
-- control planes track builtin catalog additions through migrations.

-- The asset-register package itself was never seeded: 0004 predates the
-- assets track, so on a fresh Postgres control plane the publication rows
-- below violated publication_definitions_transformation_package_id_fkey and
-- the api could not start at all. Seed the package first, matching the
-- BuiltinTransformationPackageSpec in packages/pipelines/household_packages.py.
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
    ('builtin_asset_register', 'Built-in asset register', 'asset_register', 1, 'Manual asset register transformation and current asset publication.', FALSE, NOW())
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
    ('pub_asset_register_current_assets', 'builtin_asset_register', 'rpt_current_dim_asset', 'Current asset view', NULL, FALSE, NOW()),
    ('pub_asset_register_asset_value', 'builtin_asset_register', 'mart_asset_value', 'Asset value mart', NULL, FALSE, NOW()),
    ('pub_asset_register_depreciation_schedule', 'builtin_asset_register', 'mart_depreciation_schedule', 'Depreciation schedule mart', NULL, FALSE, NOW())
ON CONFLICT (publication_definition_id) DO NOTHING;
