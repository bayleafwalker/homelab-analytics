-- 0016_reporting_publication_snapshot: dated snapshots of the current-only
-- reporting publications (household overview, attention items, recent
-- changes, affordability ratios, recurring cost baseline, subscription
-- summary) so the reporting layer can answer as-of reads.
--
-- One snapshot per (publication_key, reference_month). reference_month is
-- the newest booking_month in mart_monthly_cashflow when the snapshot was
-- captured (YYYY-MM); a later refresh in the same reference month replaces
-- it. captured_at is an ISO-8601 string with an explicit UTC offset, like
-- the 0015 marts. rows_json holds the publication rows as JSON, serialised
-- the way the reporting API serialises them. Retention (newest N reference
-- months per publication) is applied at write time.
--
-- Runtime creates the same table through
-- the store-level helpers in packages/pipelines/reporting_snapshots.py; the Postgres
-- reporting store creates its copy on first write, like the published marts.

CREATE TABLE IF NOT EXISTS reporting_publication_snapshot (
    publication_key VARCHAR NOT NULL,
    reference_month VARCHAR NOT NULL,
    captured_at VARCHAR NOT NULL,
    run_id VARCHAR,
    row_count INTEGER NOT NULL,
    rows_json VARCHAR NOT NULL
);

