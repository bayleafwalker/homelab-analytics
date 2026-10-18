"""Trace evidence corrections to the decisions made on that evidence (HLA-K02).

When a source window is re-landed, a tariff snapshot is revised or an entity
mapping changes, the affected publication is recomputed and its row gets a
new assessment. This use case compares, per decision record, the evidence
fingerprint pinned at record time with the current subject row for the same
period:

- same fingerprint → the decision's evidence still stands, even if the row
  was simply re-assessed (a new ``assessment_id`` alone is not a correction);
- different fingerprint → an ``evidence_superseded`` lifecycle event names the
  changed components, their correction kinds, the affected publications, the
  superseded and superseding row references, the source version and the
  review triggers that fired. The commitment becomes ``review_required``.

Only the decision's own period is compared, so corrections to other periods
leave it valid. Event ``dedupe_key`` = decision + superseding fingerprint, so a
repeated delivery of the same revision records no duplicate review. The
original evidence snapshot is never touched: it stays reconstructible next to
the pointer to the newer assessment.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Any

from packages.platform.decision_definitions import (
    DecisionDefinition,
    DecisionSubjectEvidence,
    evidence_fingerprint,
)
from packages.storage.decision_ledger import (
    DecisionActor,
    DecisionLedgerStore,
    DecisionLifecycleEventCreate,
    DecisionRecord,
)

TRACE_ACTOR = DecisionActor(
    actor="hla-evidence-trace",
    actor_role=None,
    actor_auth_provider="system",
    actor_authenticated=False,
)


@dataclass(frozen=True)
class EvidenceTraceResult:
    decision_id: str
    decision_key: str
    subject_period: str
    status: str  # unchanged | superseded | already_recorded | subject_unpublished | untraceable
    changed_components: tuple[str, ...] = ()
    correction_kinds: tuple[str, ...] = ()
    superseding_row_ref: str | None = None
    event_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision_key": self.decision_key,
            "subject_period": self.subject_period,
            "status": self.status,
            "changed_components": list(self.changed_components),
            "correction_kinds": list(self.correction_kinds),
            "superseding_row_ref": self.superseding_row_ref,
            "event_id": self.event_id,
        }


@dataclass(frozen=True)
class EvidenceTraceReport:
    traced_at: datetime
    results: tuple[EvidenceTraceResult, ...]
    affected_publication_keys: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return {
            "traced_at": self.traced_at.isoformat(),
            "counts": counts,
            "affected_publication_keys": list(self.affected_publication_keys),
            "results": [result.as_dict() for result in self.results],
        }


def trace_evidence_corrections(
    store: DecisionLedgerStore,
    *,
    definition_lookup: Callable[[str], DecisionDefinition | None],
    subject_reader: Callable[[str, str], DecisionSubjectEvidence | None],
    snapshot_components: Callable[[str, Mapping[str, Any]], dict[str, Any] | None],
    decision_key: str | None = None,
    now: datetime | None = None,
) -> EvidenceTraceReport:
    traced_at = now or datetime.now(UTC)
    results: list[EvidenceTraceResult] = []
    affected: set[str] = set()
    current_by_subject: dict[tuple[str, str], DecisionSubjectEvidence | None] = {}
    for record in store.list_decision_records(decision_key=decision_key):
        key = (record.decision_key, record.subject_period)
        if key not in current_by_subject:
            current_by_subject[key] = subject_reader(*key)
        result, publications = _trace_one(
            store,
            record,
            current=current_by_subject[key],
            definition=definition_lookup(record.decision_key),
            snapshot_components=snapshot_components,
            traced_at=traced_at,
        )
        results.append(result)
        affected.update(publications)
    return EvidenceTraceReport(
        traced_at=traced_at,
        results=tuple(results),
        affected_publication_keys=tuple(sorted(affected)),
    )


def pinned_evidence_components(
    record: DecisionRecord,
    snapshot_components: Callable[[str, Mapping[str, Any]], dict[str, Any] | None],
) -> dict[str, Any] | None:
    if record.commitment is not None:
        return dict(json.loads(record.commitment.evidence_components))
    return snapshot_components(record.decision_key, json.loads(record.evidence_snapshot))


def _component_label(definition: DecisionDefinition, component: str) -> str:
    declared = definition.evidence_component(component)
    return declared.label if declared is not None else component


def _trace_one(
    store: DecisionLedgerStore,
    record: DecisionRecord,
    *,
    current: DecisionSubjectEvidence | None,
    definition: DecisionDefinition | None,
    snapshot_components: Callable[[str, Mapping[str, Any]], dict[str, Any] | None],
    traced_at: datetime,
) -> tuple[EvidenceTraceResult, set[str]]:
    base = partial(
        EvidenceTraceResult,
        decision_id=record.decision_id,
        decision_key=record.decision_key,
        subject_period=record.subject_period,
    )
    if current is None:
        return base(status="subject_unpublished"), set()
    pinned = pinned_evidence_components(record, snapshot_components)
    if pinned is None or definition is None:
        return base(status="untraceable"), set()
    changed = tuple(
        sorted(
            component
            for component in set(pinned) | set(current.evidence_components)
            if pinned.get(component) != current.evidence_components.get(component)
        )
    )
    if not changed:
        return base(status="unchanged"), set()
    kinds = tuple(
        sorted(
            {
                declared.correction_kind
                for component in changed
                if (declared := definition.evidence_component(component)) is not None
            }
        )
    )
    triggers = list(definition.triggers_for_components(changed))
    if current.verdict != record.subject_verdict:
        triggers.extend(
            trigger.key for trigger in definition.review_triggers if trigger.kind == "verdict_change"
        )
    lineage = json.loads(record.lineage_reference)
    publications = sorted(
        {
            *[str(key) for key in lineage.get("publication_keys") or [record.subject_publication_key]],
            current.publication_key,
        }
    )
    superseding_fingerprint = current.evidence_fingerprint
    labels = [_component_label(definition, component) for component in changed]
    details = {
        "superseded_row_ref": record.subject_row_ref,
        "superseded_fingerprint": lineage.get("evidence_fingerprint")
        or evidence_fingerprint(pinned),
        "superseding_row_ref": current.row_ref,
        "superseding_fingerprint": superseding_fingerprint,
        "superseding_publication_key": current.publication_key,
        "superseding_schema_version": current.schema_version,
        "affected_publication_keys": publications,
        "changed_components": list(changed),
        "correction_kinds": list(kinds),
        "triggered_reviews": triggers,
        "verdict_before": record.subject_verdict,
        "verdict_after": current.verdict,
        "source_version": {
            key: current.lineage_reference.get(key)
            for key in (
                "assessment_id",
                "assessed_at",
                "source_run_ids",
                "tariff_snapshot_id",
                "source_report_ingested_at",
            )
            if key in current.lineage_reference
        },
        "traced_at": traced_at.isoformat(),
    }
    event, created = store.append_decision_lifecycle_event(
        DecisionLifecycleEventCreate(
            event_id=f"dle_{uuid.uuid4().hex}",
            decision_id=record.decision_id,
            event_kind="evidence_superseded",
            dedupe_key=f"{record.decision_id}:evidence_superseded:{superseding_fingerprint}",
            reason_code="evidence_superseded",
            reason=(
                "Evidence superseded by a newer assessment "
                f"({current.row_ref}): {', '.join(labels)} changed."
            ),
            details=json.dumps(details, sort_keys=True, separators=(",", ":"), default=str),
            actor=TRACE_ACTOR,
            occurred_at=traced_at,
            created_at=traced_at,
        )
    )
    return (
        base(
            status="superseded" if created else "already_recorded",
            changed_components=changed,
            correction_kinds=kinds,
            superseding_row_ref=current.row_ref,
            event_id=event.event_id,
        ),
        set(publications),
    )
