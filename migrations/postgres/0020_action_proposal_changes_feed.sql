-- 0020_action_proposal_changes_feed: a commit-ordered position on every
-- action-proposal history event, for GET /api/actions/proposals/changes.
-- Postgres port of sqlite migration 0013_action_proposal_changes_feed.
-- feed_position is assigned from the single-row action_proposal_feed_counter
-- in the same transaction that appends the event. The counter row lock is held
-- until commit, so positions become visible in commit order and a reader
-- paging with "feed_position > cursor" can never skip an event that commits
-- late. Existing events are backfilled in (occurred_at, action_id, sequence)
-- order. Events stay append-only: feed_position is written once, at insert.

ALTER TABLE action_proposal_events ADD COLUMN IF NOT EXISTS feed_position BIGINT;

WITH ordered AS (
    SELECT
        event_id,
        ROW_NUMBER() OVER (ORDER BY occurred_at, action_id, sequence) AS position
    FROM action_proposal_events
)
UPDATE action_proposal_events AS events
SET feed_position = ordered.position
FROM ordered
WHERE events.event_id = ordered.event_id
  AND events.feed_position IS NULL;

ALTER TABLE action_proposal_events ALTER COLUMN feed_position SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_action_proposal_events_feed_position
    ON action_proposal_events (feed_position);

CREATE TABLE IF NOT EXISTS action_proposal_feed_counter (
    counter_key TEXT PRIMARY KEY,
    last_position BIGINT NOT NULL
);

INSERT INTO action_proposal_feed_counter (counter_key, last_position)
SELECT 'action_proposal_events', COALESCE(MAX(feed_position), 0)
FROM action_proposal_events
ON CONFLICT (counter_key) DO NOTHING;
