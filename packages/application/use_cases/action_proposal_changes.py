"""The approval-queue changes feed (agentic UX plan §5.3).

``GET /api/actions/proposals/changes`` serves the proposal queue's
append-only history as a ``resource-changes/v1`` feed, the shape the
outcome-reference export uses and the vuoro client validates strictly:

    {"schema_version": "resource-changes/v1",
     "reference": "action-proposals" | "action-proposals/<action_id>",
     "next_cursor": "<opaque>",
     "events": [{"event_id", "terminal", "data"}]}

Cursors are opaque to readers (``apf.<feed position>``). Positions are handed
out in commit order (see ``packages/storage/action_proposal_store.py``), so a
reader that keeps passing back ``next_cursor`` sees every event exactly once,
including events that committed after a concurrent one. ``next_cursor`` is
always present: with no new events it equals the cursor that was passed in,
so a reader can poll with it indefinitely. A page shorter than ``limit``
means the reader is caught up.

``terminal`` is true when the event leaves the proposal approved or
dismissed. It describes that revision, not a promise: the HA dispatcher may
re-raise a resolved gate (``reopened``) and a failed HA release reverts an
approval (``release_failed``); both arrive as later, non-terminal events.
``data.effect_state`` maps the status onto vuoro's effect-intent states
(``proposed`` / ``accepted`` / ``rejected``). The feed is read-only and
pull-only: HLA never executes anything on a reader's behalf.
"""

from __future__ import annotations

import re
from typing import Any

from packages.application.use_cases.agent_capability_manifest import (
    PROPOSAL_STATE_TO_VUORO_EFFECT,
)
from packages.platform.action_proposals import ActionProposalRegistry, ProposalFeedEvent

CHANGES_FEED_SCHEMA = "resource-changes/v1"
PROPOSAL_EVENT_SCHEMA = "hla-action-proposal-event/v1"
REPO_ID = "homelab-analytics"
FEED_REFERENCE = "action-proposals"
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
_CURSOR_PATTERN = re.compile(r"^apf\.(0|[1-9][0-9]{0,17})$")

_STATUS_AFTER_EVENT = {
    "drafted": "pending",
    "refreshed": "pending",
    "reopened": "pending",
    "release_failed": "pending",
    "approved": "approved",
    "dismissed": "dismissed",
}
TERMINAL_STATUSES = frozenset({"approved", "dismissed"})


class InvalidCursorError(ValueError):
    """Raised for a cursor this feed did not issue."""


def encode_cursor(position: int) -> str:
    return f"apf.{position}"


def decode_cursor(cursor: str | None) -> int:
    """Feed position after which to read; ``None`` or empty starts at the beginning."""
    if cursor is None or cursor == "":
        return 0
    match = _CURSOR_PATTERN.match(cursor)
    if match is None:
        raise InvalidCursorError(f"Unrecognised changes-feed cursor: {cursor!r}")
    return int(match.group(1))


def feed_reference(action_id: str | None) -> str:
    return FEED_REFERENCE if action_id is None else f"{FEED_REFERENCE}/{action_id}"


def _event_payload(item: ProposalFeedEvent) -> dict[str, Any]:
    status = _STATUS_AFTER_EVENT.get(item.event.kind, "pending")
    return {
        "event_id": item.event_id,
        "terminal": status in TERMINAL_STATUSES,
        "data": {
            "schema_version": PROPOSAL_EVENT_SCHEMA,
            "repo_id": REPO_ID,
            "action_id": item.action_id,
            "sequence": item.sequence,
            "kind": item.event.kind,
            "occurred_at": item.event.at,
            "actor": item.event.actor,
            "actor_auth_provider": item.event.actor_auth_provider,
            "reason": item.event.reason,
            "status": status,
            "effect_state": PROPOSAL_STATE_TO_VUORO_EFFECT[status],
            "adapter": item.adapter,
            "source_kind": item.source_kind,
            "origin": item.policy_id,
            "title": item.policy_name,
            "proposal_path": f"/api/actions/proposals/{item.action_id}",
        },
    }


def proposal_changes_feed(
    registry: ActionProposalRegistry,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    action_id: str | None = None,
) -> dict[str, Any]:
    """One page of the changes feed after ``cursor``."""
    after = decode_cursor(cursor)
    bounded = min(max(limit, 1), MAX_LIMIT)
    items = registry.list_changes(after_position=after, limit=bounded, action_id=action_id)
    next_position = items[-1].position if items else after
    return {
        "schema_version": CHANGES_FEED_SCHEMA,
        "reference": feed_reference(action_id),
        "next_cursor": encode_cursor(next_position),
        "events": [_event_payload(item) for item in items],
    }
