"""Portable, versioned outcome references for decisions (HLA-K04).

HLA keeps household authority: the envelope carries *references* (commitment,
publication, evidence pointer), the observation window, the result and
attention/cost coverage — never raw transactions, source rows, evidence
snapshots or credentials. Nothing here sends anything anywhere; callers
(an API route or the worker export command) hand the JSON to an operator or
to a consumer that pulls it.

Naming follows the vuoro conventions recorded in
``docs/plans/2026-10-agentic-ux-and-vuoro-alignment.md``: ``<name>/v1``
schema strings, ``repo_id = homelab-analytics``, ``hla.<noun>.<verb>``
operation names, idempotency keys matching ``^[A-Za-z0-9._:-]{8,128}$`` and a
``resource-changes/v1`` feed shape (``events[{event_id, terminal, data}]``,
``next_cursor``).

Identity and corrections: a decision's history (record, follow-ups,
lifecycle events) is replayed into revisions. Revision ``n`` has a stable
``event_id`` derived from its content, so re-exporting (a retry) yields the
same logical event; any correction — a follow-up, an evidence supersession, a
stop or reopen — produces a new revision whose ``supersedes`` names the
previous ``event_id``.

Unknown stays unknown: operator attention is the minutes entered on
follow-ups. With none entered ``attention.measured_minutes`` is ``null`` with
``capture_coverage = not_captured``; when only some follow-ups carry minutes
the sum of the known ones is ``partial``, never padded. A cost appears only
when a follow-up recorded an observed or user-entered value.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from datetime import date
from typing import Any

from packages.application.use_cases.decision_ledger import (
    derive_commitment_state,
    evaluate_follow_up_success,
)
from packages.storage.decision_ledger import (
    DecisionFollowUpRecord,
    DecisionLedgerStore,
    DecisionLifecycleEvent,
    DecisionRecord,
)

OUTCOME_REFERENCE_SCHEMA = "hla-outcome-reference/v1"
EVIDENCE_POINTER_SCHEMA = "hla-decision-evidence/v1"
CHANGES_FEED_SCHEMA = "resource-changes/v1"
REPO_ID = "homelab-analytics"
EXPORT_OPERATION = "hla.outcome.export"
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
EXCLUDED_CONTENT = ("raw_transactions", "source_rows", "evidence_snapshot", "credentials")


def build_outcome_references(
    record: DecisionRecord,
    follow_ups: Sequence[DecisionFollowUpRecord],
    events: Sequence[DecisionLifecycleEvent],
) -> list[dict[str, Any]]:
    """Every revision of the decision's outcome reference, oldest first."""
    timeline: list[tuple[Any, int, Any]] = [
        *((item.observed_at, 0, item) for item in follow_ups),
        *((item.occurred_at, 1, item) for item in events),
    ]
    timeline.sort(key=lambda entry: (entry[0], entry[1]))
    revisions: list[dict[str, Any]] = []
    seen_follow_ups: list[DecisionFollowUpRecord] = []
    seen_events: list[DecisionLifecycleEvent] = []
    states: list[tuple[list[DecisionFollowUpRecord], list[DecisionLifecycleEvent], date]] = [
        ([], [], record.created_at.date())
    ]
    for moment, _, item in timeline:
        if isinstance(item, DecisionFollowUpRecord):
            seen_follow_ups = [*seen_follow_ups, item]
        else:
            seen_events = [*seen_events, item]
        states.append((seen_follow_ups, seen_events, moment.date()))
    previous_event_id: str | None = None
    for index, (state_follow_ups, state_events, as_of) in enumerate(states, start=1):
        envelope = _envelope(
            record,
            state_follow_ups,
            state_events,
            revision=index,
            supersedes=previous_event_id,
            as_of=as_of,
        )
        previous_event_id = envelope["event_id"]
        revisions.append(envelope)
    return revisions


def latest_outcome_reference(
    store: DecisionLedgerStore, decision_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    record = store.get_decision_record(decision_id)
    revisions = build_outcome_references(
        record,
        store.list_decision_follow_ups(decision_id),
        store.list_decision_lifecycle_events(decision_id),
    )
    return revisions[-1], revisions


def outcome_reference_feed(
    store: DecisionLedgerStore,
    *,
    decision_key: str | None = None,
    include_history: bool = True,
) -> dict[str, Any]:
    """A ``resource-changes/v1`` shaped feed of outcome-reference revisions."""
    events: list[dict[str, Any]] = []
    for record in sorted(
        store.list_decision_records(decision_key=decision_key),
        key=lambda item: (item.created_at, item.decision_id),
    ):
        revisions = build_outcome_references(
            record,
            store.list_decision_follow_ups(record.decision_id),
            store.list_decision_lifecycle_events(record.decision_id),
        )
        for envelope in revisions if include_history else revisions[-1:]:
            events.append(
                {
                    "event_id": envelope["event_id"],
                    "terminal": envelope["lifecycle_state"] == "stopped",
                    "data": envelope,
                }
            )
    return {
        "schema_version": CHANGES_FEED_SCHEMA,
        "repo_id": REPO_ID,
        "events": events,
        "next_cursor": None,
    }


def _envelope(
    record: DecisionRecord,
    follow_ups: Sequence[DecisionFollowUpRecord],
    events: Sequence[DecisionLifecycleEvent],
    *,
    revision: int,
    supersedes: str | None,
    as_of: date,
) -> dict[str, Any]:
    lifecycle = derive_commitment_state(record, follow_ups, events, today=as_of)
    latest = follow_ups[-1] if follow_ups else None
    success = evaluate_follow_up_success(record, latest) if latest is not None else None
    result = _result(latest, success)
    commitment = record.commitment
    lineage = json.loads(record.lineage_reference)
    fingerprint = (
        commitment.evidence_fingerprint if commitment is not None else lineage.get("evidence_fingerprint")
    )
    body: dict[str, Any] = {
        "schema_version": OUTCOME_REFERENCE_SCHEMA,
        "repo_id": REPO_ID,
        "operation": EXPORT_OPERATION,
        "outcome_ref": f"hla:decision:{record.decision_id}",
        "revision": revision,
        "supersedes": supersedes,
        "authority": {
            "owner": REPO_ID,
            "household_authority_transferred": False,
            "actuation_authorized": False,
        },
        "commitment_ref": {
            "decision_key": record.decision_key,
            "decision_version": record.decision_version,
            "decision_id": record.decision_id,
            "outcome": record.outcome,
            "is_non_decision": record.is_non_decision,
            "decided_at": record.created_at.isoformat(),
        },
        # HLA does not own a vuoro work item for a household decision; the
        # link stays explicit rather than invented.
        "work_ref": None,
        "publication_ref": {
            "publication_key": record.subject_publication_key,
            "schema_version": record.subject_schema_version,
            "period": record.subject_period,
            "row_ref": record.subject_row_ref,
            "evidence_fingerprint": fingerprint,
        },
        "observation_window": (
            {
                "start": commitment.observation_window_start.isoformat(),
                "end": commitment.observation_window_end.isoformat(),
            }
            if commitment is not None
            else None
        ),
        "result": result,
        "verdict_at_decision": record.subject_verdict,
        "lifecycle_state": lifecycle["state"],
        "evidence_status": lifecycle["evidence_status"],
        "evidence_effect": latest.evidence_effect if latest is not None else None,
        "attention": _attention(follow_ups),
        "cost": {
            "realized_value_eur": (
                str(latest.realized_value_eur)
                if latest is not None and latest.realized_value_eur is not None
                else None
            ),
            "value_status": latest.realized_value_status if latest is not None else None,
            "capture_coverage": (
                "captured"
                if latest is not None and latest.realized_value_eur is not None
                else "not_captured"
            ),
            "unknown_is_zero": False,
        },
        "evidence_pointer": {
            "schema_version": EVIDENCE_POINTER_SCHEMA,
            "href": f"/control/decisions/{record.decision_id}",
            "decision_id": record.decision_id,
            "row_ref": record.subject_row_ref,
            "evidence_fingerprint": fingerprint,
            "lineage_publication_keys": list(
                lineage.get("publication_keys") or [record.subject_publication_key]
            ),
            "follow_up_ids": [item.follow_up_id for item in follow_ups],
            "lifecycle_event_ids": [item.event_id for item in events],
            "superseded_by": lifecycle["superseded_by"],
        },
        "excluded": list(EXCLUDED_CONTENT),
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    body["event_id"] = f"hla_outref_{digest[:26]}"
    body["idempotency_key"] = f"hla:outcome:{record.decision_id}:r{revision}"
    return body


def _attention(follow_ups: Sequence[DecisionFollowUpRecord]) -> dict[str, Any]:
    """Operator minutes entered on follow-ups; unknown minutes are never zero."""
    known = [item.attention_minutes for item in follow_ups if item.attention_minutes is not None]
    if not known:
        coverage = "not_captured"
    elif len(known) == len(follow_ups):
        coverage = "captured"
    else:
        coverage = "partial"
    return {
        "measured_minutes": sum(known) if known else None,
        "capture_coverage": coverage,
        "unknown_is_zero": False,
    }


def _result(latest: DecisionFollowUpRecord | None, success: str | None) -> str:
    """accepted / rejected / insufficient_evidence / pending — never inferred."""
    if latest is None:
        return "pending"
    if latest.evidence_effect in {"exposed_source_defect", "exposed_model_defect"}:
        return "insufficient_evidence"
    if success == "met":
        return "accepted"
    if success == "not_met":
        return "rejected"
    return "insufficient_evidence"
