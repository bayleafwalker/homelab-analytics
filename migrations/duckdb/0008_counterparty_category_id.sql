-- 0008_counterparty_category_id: add category_id FK to dim_counterparty
--
-- Stage 1 carryover: dim_counterparty previously carried only a free-text
-- category bridge. This migration adds category_id as a nullable FK into
-- dim_category.category_id and backfills it by joining on the display_name.
--
-- The free-text category column is retained for backward compatibility.
-- Full removal of the bridge column is deferred to a future sprint.

ALTER TABLE dim_counterparty ADD COLUMN IF NOT EXISTS category_id VARCHAR;

-- Backfill: for every current dim_counterparty row whose category text
-- matches a dim_category display_name, set the category_id.
UPDATE dim_counterparty AS cp
SET category_id = dc.category_id
FROM dim_category AS dc
WHERE cp.is_current = TRUE
  AND dc.is_current = TRUE
  AND cp.category IS NOT NULL
  AND cp.category = dc.display_name
  AND cp.category_id IS NULL;
