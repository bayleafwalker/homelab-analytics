-- 0013_action_proposal_changes_feed: a commit-ordered position on every
-- action-proposal history event, for GET /api/actions/proposals/changes.
-- feed_position is assigned from the single-row action_proposal_feed_counter
-- in the same BEGIN IMMEDIATE transaction that appends the event, so positions
-- are assigned and become visible in commit order. Existing events are
-- backfilled in (occurred_at, action_id, sequence) order. Events stay
-- append-only: feed_position is written once, at insert.
-- Mirrored in the inline bootstrap (sqlite_control_plane_schema.py).

ALTER TABLE action_proposal_events ADD COLUMN feed_position INTEGER;

UPDATE action_proposal_events
SET feed_position = (
    SELECT ordered.position
    FROM (
        SELECT
            event_id,
            ROW_NUMBER() OVER (ORDER BY occurred_at, action_id, sequence) AS position
        FROM action_proposal_events
    ) AS ordered
    WHERE ordered.event_id = action_proposal_events.event_id
)
WHERE feed_position IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_action_proposal_events_feed_position
    ON action_proposal_events (feed_position);

CREATE TABLE IF NOT EXISTS action_proposal_feed_counter (
    counter_key TEXT PRIMARY KEY,
    last_position INTEGER NOT NULL
);

INSERT INTO action_proposal_feed_counter (counter_key, last_position)
SELECT 'action_proposal_events', COALESCE(MAX(feed_position), 0)
FROM action_proposal_events
WHERE 1
ON CONFLICT (counter_key) DO NOTHING;
