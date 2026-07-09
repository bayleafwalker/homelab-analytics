-- 0013_asset_marts: mart tables for the domain-marts-fillout assets track.
-- mart_asset_value and mart_depreciation_schedule. Rebuilt via DELETE + INSERT
-- on refresh.

CREATE TABLE IF NOT EXISTS mart_asset_value (
    asset_id VARCHAR NOT NULL,
    asset_name VARCHAR NOT NULL,
    asset_type VARCHAR,
    location VARCHAR,
    purchase_date DATE,
    purchase_price DECIMAL(18,4),
    currency VARCHAR,
    months_in_service INTEGER,
    accumulated_depreciation DECIMAL(18,4) NOT NULL,
    estimated_value DECIMAL(18,4) NOT NULL,
    valuation_basis VARCHAR NOT NULL,
    is_disposed BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_depreciation_schedule (
    depreciation_year INTEGER NOT NULL,
    asset_type VARCHAR NOT NULL,
    currency VARCHAR,
    annual_depreciation DECIMAL(18,4) NOT NULL,
    asset_count INTEGER NOT NULL
);
