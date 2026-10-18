"""Dialect-neutral control-plane storage for the durable action-proposal queue.

``SQLiteActionProposalStoreMixin`` and ``PostgresActionProposalStoreMixin`` only
provide ``_session()`` (see ``sql_dialect.py``); every query, the row mapping,
the compare-and-set transition and the history append live here, so both
backends share one implementation.

Schema: ``migrations/sqlite/0009_action_proposal_queue.sql`` and
``migrations/postgres/0016_action_proposal_queue.sql``, plus the changes-feed
position and counter from sqlite ``0013`` / postgres
``0020_action_proposal_changes_feed`` (mirrored in the SQLite inline bootstrap
``sqlite_control_plane_schema.py``). The lifecycle rules live
in :class:`packages.platform.action_proposals.ActionProposalRegistry`; the
store only persists state, compare-and-sets status, and appends history.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Mapping
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import psycopg

from packages.platform.action_proposals import (
    ActionProposal,
    ProposalConflictError,
    ProposalFeedEvent,
    ProposalHistoryEvent,
    ProposalHistoryEventKind,
    ProposalProvenance,
    ProposalSourceKind,
    ProposalStatus,
    ProvenanceTrustSource,
    sort_proposals,
)
from packages.storage.decision_ledger import aware_utc
from packages.storage.sql_dialect import DialectSession, SqlDialect, row_int

PROPOSAL_COLUMNS: tuple[str, ...] = (
    "action_id",
    "policy_id",
    "policy_name",
    "verdict",
    "value",
    "notification_id",
    "adapter",
    "source_kind",
    "source_key",
    "source_summary",
    "created_by",
    "status",
    "created_at",
    "approved_at",
    "dismissed_at",
    "metadata_json",
    "provenance_publication_keys_json",
    "provenance_confidence_verdict",
    "provenance_freshness_state",
    "provenance_assessed_at",
    "provenance_trust_source",
    "resolved_by",
    "resolution_reason",
    "idempotency_key",
    "updated_at",
)
# Columns a compare-and-set update rewrites: everything except the identity
# (action_id) and the idempotency key, which are fixed at insert.
MUTABLE_PROPOSAL_COLUMNS: tuple[str, ...] = tuple(
    column
    for column in PROPOSAL_COLUMNS
    if column not in {"action_id", "idempotency_key"}
)
EVENT_COLUMNS: tuple[str, ...] = (
    "event_id",
    "action_id",
    "sequence",
    "kind",
    "occurred_at",
    "actor",
    "actor_auth_provider",
    "reason",
    "feed_position",
)
TIMESTAMP_COLUMNS = frozenset(
    {"created_at", "approved_at", "dismissed_at", "updated_at", "occurred_at"}
)


def parse_timestamp(value: str) -> datetime:
    """Parse a stored or in-flight ISO timestamp as aware UTC."""
    return aware_utc(datetime.fromisoformat(value))


def normalize_timestamp(value: str | None) -> str | None:
    if value is None:
        return None
    return parse_timestamp(value).isoformat()


def timestamp_text(value: object) -> str | None:
    """Read a timestamp column back as an aware-UTC ISO string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return aware_utc(value).isoformat()
    return normalize_timestamp(str(value))


def proposal_row(proposal: ActionProposal, *, updated_at: str) -> dict[str, Any]:
    """Map a proposal onto column values (timestamps as aware-UTC ISO text)."""
    provenance = proposal.provenance
    return {
        "action_id": proposal.action_id,
        "policy_id": proposal.policy_id,
        "policy_name": proposal.policy_name,
        "verdict": proposal.verdict,
        "value": proposal.value,
        "notification_id": proposal.notification_id,
        "adapter": proposal.adapter,
        "source_kind": proposal.source_kind,
        "source_key": proposal.source_key,
        "source_summary": proposal.source_summary,
        "created_by": proposal.created_by,
        "status": proposal.status,
        "created_at": normalize_timestamp(proposal.created_at),
        "approved_at": normalize_timestamp(proposal.approved_at),
        "dismissed_at": normalize_timestamp(proposal.dismissed_at),
        "metadata_json": json.dumps(proposal.metadata, sort_keys=True, default=str),
        "provenance_publication_keys_json": (
            json.dumps(list(provenance.publication_keys)) if provenance is not None else None
        ),
        "provenance_confidence_verdict": (
            provenance.confidence_verdict_at_draft if provenance is not None else None
        ),
        "provenance_freshness_state": (
            provenance.freshness_state_at_draft if provenance is not None else None
        ),
        "provenance_assessed_at": provenance.assessed_at if provenance is not None else None,
        "provenance_trust_source": provenance.trust_source if provenance is not None else None,
        "resolved_by": proposal.resolved_by,
        "resolution_reason": proposal.resolution_reason,
        "idempotency_key": proposal.idempotency_key,
        "updated_at": normalize_timestamp(updated_at),
    }


def event_row(
    action_id: str,
    sequence: int,
    event: ProposalHistoryEvent,
    *,
    feed_position: int,
) -> dict[str, Any]:
    return {
        "event_id": f"ape_{uuid.uuid4().hex}",
        "action_id": action_id,
        "sequence": sequence,
        "kind": event.kind,
        "occurred_at": normalize_timestamp(event.at),
        "actor": event.actor,
        "actor_auth_provider": event.actor_auth_provider,
        "reason": event.reason,
        "feed_position": feed_position,
    }


def deserialize_event(row: Mapping[str, Any]) -> ProposalHistoryEvent:
    return ProposalHistoryEvent(
        kind=cast(ProposalHistoryEventKind, str(row["kind"])),
        at=cast(str, timestamp_text(row["occurred_at"])),
        actor=row["actor"],
        reason=row["reason"],
        actor_auth_provider=row["actor_auth_provider"],
    )


def deserialize_proposal(
    row: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
) -> ActionProposal:
    raw_keys = row["provenance_publication_keys_json"]
    provenance = None
    if raw_keys is not None:
        provenance = ProposalProvenance(
            publication_keys=[str(key) for key in json.loads(raw_keys)],
            confidence_verdict_at_draft=row["provenance_confidence_verdict"],
            freshness_state_at_draft=row["provenance_freshness_state"],
            assessed_at=row["provenance_assessed_at"],
            trust_source=cast(
                ProvenanceTrustSource | None, row["provenance_trust_source"]
            ),
        )
    return ActionProposal(
        action_id=str(row["action_id"]),
        policy_id=str(row["policy_id"]),
        policy_name=str(row["policy_name"]),
        verdict=str(row["verdict"]),
        value=row["value"],
        notification_id=str(row["notification_id"]),
        adapter=str(row["adapter"]),
        source_kind=cast(ProposalSourceKind, str(row["source_kind"])),
        source_key=row["source_key"],
        source_summary=row["source_summary"],
        created_by=row["created_by"],
        status=cast(ProposalStatus, str(row["status"])),
        created_at=cast(str, timestamp_text(row["created_at"])),
        approved_at=timestamp_text(row["approved_at"]),
        dismissed_at=timestamp_text(row["dismissed_at"]),
        metadata=dict(json.loads(row["metadata_json"])),
        provenance=provenance,
        resolved_by=row["resolved_by"],
        resolution_reason=row["resolution_reason"],
        idempotency_key=row["idempotency_key"],
        history=[deserialize_event(event) for event in events],
    )


def group_events(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["action_id"]), []).append(row)
    return grouped


_PROPOSAL_SELECT = f"SELECT {', '.join(PROPOSAL_COLUMNS)} FROM action_proposals"
_EVENT_SELECT = f"SELECT {', '.join(EVENT_COLUMNS)} FROM action_proposal_events"
_INSERT_PROPOSAL = (
    f"INSERT INTO action_proposals ({', '.join(PROPOSAL_COLUMNS)}) "
    f"VALUES ({', '.join('?' for _ in PROPOSAL_COLUMNS)})"
)
_INSERT_EVENT = (
    f"INSERT INTO action_proposal_events ({', '.join(EVENT_COLUMNS)}) "
    f"VALUES ({', '.join('?' for _ in EVENT_COLUMNS)})"
)
_UPDATE_PROPOSAL = (
    "UPDATE action_proposals SET "
    + ", ".join(f"{column} = ?" for column in MUTABLE_PROPOSAL_COLUMNS)
    + " WHERE action_id = ? AND status = ?"
)
_NEXT_SEQUENCE = (
    "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence"
    " FROM action_proposal_events WHERE action_id = ?"
)
# The changes feed: one counter row hands out commit-ordered feed positions.
# Bumping it row-locks it (Postgres) until commit; SQLite's BEGIN IMMEDIATE
# already serializes writers. Either way positions become visible in order.
FEED_COUNTER_KEY = "action_proposal_events"
_BUMP_FEED_COUNTER = (
    "UPDATE action_proposal_feed_counter SET last_position = last_position + ?"
    " WHERE counter_key = ?"
)
_SEED_FEED_COUNTER = (
    "INSERT INTO action_proposal_feed_counter (counter_key, last_position)"
    " SELECT ?, COALESCE(MAX(feed_position), 0) FROM action_proposal_events"
    " WHERE 1 = 1 ON CONFLICT (counter_key) DO NOTHING"
)
_READ_FEED_COUNTER = (
    "SELECT last_position FROM action_proposal_feed_counter WHERE counter_key = ?"
)
_FEED_SELECT = (
    "SELECT e.feed_position, e.event_id, e.action_id, e.sequence, e.kind,"
    " e.occurred_at, e.actor, e.actor_auth_provider, e.reason,"
    " p.adapter, p.source_kind, p.policy_id, p.policy_name"
    " FROM action_proposal_events e"
    " JOIN action_proposals p ON p.action_id = e.action_id"
    " WHERE e.feed_position > ?"
)
# Uniqueness violations on action_id / idempotency_key, per backend.
_INTEGRITY_ERRORS: tuple[type[Exception], ...] = (sqlite3.IntegrityError, psycopg.IntegrityError)


def _encode(dialect: SqlDialect, row: Mapping[str, Any], columns: tuple[str, ...]) -> list[object]:
    return [
        dialect.encode_datetime(parse_timestamp(row[column]))
        if column in TIMESTAMP_COLUMNS and row[column] is not None
        else row[column]
        for column in columns
    ]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _reserve_feed_positions(session: DialectSession, count: int) -> int:
    """Reserve ``count`` consecutive feed positions; return the first one."""
    if session.execute(_BUMP_FEED_COUNTER, [count, FEED_COUNTER_KEY]) != 1:
        session.execute(_SEED_FEED_COUNTER, [FEED_COUNTER_KEY])
        session.execute(_BUMP_FEED_COUNTER, [count, FEED_COUNTER_KEY])
    row = session.fetchone(_READ_FEED_COUNTER, (FEED_COUNTER_KEY,))
    last = row_int(cast(Any, row)["last_position"])
    return last - count + 1


class ActionProposalStoreMixin:
    """Implements :class:`packages.platform.action_proposals.ActionProposalStore`."""

    if TYPE_CHECKING:
        # Supplied by the dialect binding (SQLiteSessionMixin / PostgresSessionMixin).
        def _session(
            self, *, write_lock: bool = False
        ) -> AbstractContextManager[DialectSession]: ...

    @staticmethod
    def _load_action_proposals(
        session: DialectSession, where: str, params: tuple[object, ...]
    ) -> list[ActionProposal]:
        rows = session.fetchall(f"{_PROPOSAL_SELECT} {where}", params)
        if not rows:
            return []
        ids = [str(row["action_id"]) for row in rows]
        events = group_events(
            session.fetchall(
                f"{_EVENT_SELECT} WHERE action_id IN ({', '.join('?' for _ in ids)})"
                " ORDER BY action_id, sequence",
                ids,
            )
        )
        return [deserialize_proposal(row, events.get(str(row["action_id"]), [])) for row in rows]

    def get_action_proposal(self, action_id: str) -> ActionProposal | None:
        with self._session() as session:
            found = self._load_action_proposals(session, "WHERE action_id = ?", (action_id,))
        return found[0] if found else None

    def find_action_proposal_by_idempotency_key(
        self, idempotency_key: str
    ) -> ActionProposal | None:
        with self._session() as session:
            found = self._load_action_proposals(
                session, "WHERE idempotency_key = ?", (idempotency_key,)
            )
        return found[0] if found else None

    def list_action_proposals(self) -> list[ActionProposal]:
        with self._session() as session:
            proposals = self._load_action_proposals(session, "", ())
        return sort_proposals(proposals)

    def insert_action_proposal(self, proposal: ActionProposal) -> None:
        row = proposal_row(proposal, updated_at=_now())
        try:
            with self._session(write_lock=True) as session:
                session.execute(_INSERT_PROPOSAL, _encode(session.dialect, row, PROPOSAL_COLUMNS))
                first_position = (
                    _reserve_feed_positions(session, len(proposal.history))
                    if proposal.history
                    else 0
                )
                for offset, event in enumerate(proposal.history):
                    session.execute(
                        _INSERT_EVENT,
                        _encode(
                            session.dialect,
                            event_row(
                                proposal.action_id,
                                offset + 1,
                                event,
                                feed_position=first_position + offset,
                            ),
                            EVENT_COLUMNS,
                        ),
                    )
        except _INTEGRITY_ERRORS as exc:
            raise ProposalConflictError(
                f"Proposal {proposal.action_id} or its idempotency key already exists."
            ) from exc

    def update_action_proposal(
        self,
        proposal: ActionProposal,
        *,
        expected_status: ProposalStatus,
        event: ProposalHistoryEvent | None,
    ) -> bool:
        row = proposal_row(proposal, updated_at=_now())
        # The write lock (SQLite BEGIN IMMEDIATE; the Postgres UPDATE's row lock)
        # makes the status check, the update and the event sequence one step,
        # so concurrent resolvers serialize and the loser updates zero rows.
        with self._session(write_lock=True) as session:
            updated = session.execute(
                _UPDATE_PROPOSAL,
                [
                    *_encode(session.dialect, row, MUTABLE_PROPOSAL_COLUMNS),
                    proposal.action_id,
                    expected_status,
                ],
            )
            if updated != 1:
                return False
            if event is not None:
                next_row = session.fetchone(_NEXT_SEQUENCE, (proposal.action_id,))
                next_sequence = int(cast(Any, next_row)["next_sequence"]) if next_row else 1
                session.execute(
                    _INSERT_EVENT,
                    _encode(
                        session.dialect,
                        event_row(
                            proposal.action_id,
                            next_sequence,
                            event,
                            feed_position=_reserve_feed_positions(session, 1),
                        ),
                        EVENT_COLUMNS,
                    ),
                )
        return True

    def list_action_proposal_changes(
        self,
        *,
        after_position: int,
        limit: int,
        action_id: str | None = None,
    ) -> list[ProposalFeedEvent]:
        params: list[object] = [after_position]
        statement = _FEED_SELECT
        if action_id is not None:
            statement += " AND e.action_id = ?"
            params.append(action_id)
        statement += " ORDER BY e.feed_position LIMIT ?"
        params.append(max(limit, 0))
        with self._session() as session:
            rows = session.fetchall(statement, params)
        return [
            ProposalFeedEvent(
                position=row_int(row["feed_position"]),
                event_id=str(row["event_id"]),
                action_id=str(row["action_id"]),
                sequence=row_int(row["sequence"]),
                event=deserialize_event(row),
                adapter=str(row["adapter"]),
                source_kind=str(row["source_kind"]),
                policy_id=str(row["policy_id"]),
                policy_name=str(row["policy_name"]),
            )
            for row in rows
        ]
