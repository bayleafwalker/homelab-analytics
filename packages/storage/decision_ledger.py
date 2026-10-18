"""Decision ledger records: household decisions linked to exact evidence.

A decision record pins the declared decision (key + version), the exact
subject publication row it was made on (publication key, schema version,
period, row reference) and a lineage reference, plus the outcome (or an
explicit non-decision), rationale, acknowledged evidence gaps, uncertainty and
the acting identity as the auth layer reported it. Follow-ups record what was
later observed. Both are append-only: a record is never edited, so projected
evidence and realized outcomes stay distinct and auditable.

The model is generic (``decision_key`` + subject publication) so other
domains can reuse it; only the Kotiakku battery-plan decision is declared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

FOLLOW_UP_EVIDENCE_EFFECTS = frozenset(
    {
        "confirmed_decision",
        "changed_decision",
        "preserved_non_decision",
        "exposed_source_defect",
        "exposed_model_defect",
        "inconclusive",
    }
)
REALIZED_VALUE_STATUSES = frozenset({"observed", "user_entered"})


@dataclass(frozen=True)
class DecisionActor:
    actor: str
    actor_role: str | None
    actor_auth_provider: str
    actor_authenticated: bool


@dataclass(frozen=True)
class DecisionRecordCreate:
    decision_id: str
    decision_key: str
    decision_version: str
    subject_publication_key: str
    subject_schema_version: str
    subject_period: str
    subject_row_ref: str
    subject_verdict: str
    lineage_reference: str  # JSON document
    evidence_snapshot: str  # JSON document of the subject rows at decision time
    outcome: str
    is_non_decision: bool
    rationale: str
    evidence_gaps_acknowledged: str  # JSON list
    uncertainty: str | None
    actor: DecisionActor
    follow_up_due_on: date
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    decision_key: str
    decision_version: str
    subject_publication_key: str
    subject_schema_version: str
    subject_period: str
    subject_row_ref: str
    subject_verdict: str
    lineage_reference: str
    evidence_snapshot: str
    outcome: str
    is_non_decision: bool
    rationale: str
    evidence_gaps_acknowledged: str
    uncertainty: str | None
    actor: DecisionActor
    follow_up_due_on: date
    created_at: datetime


@dataclass(frozen=True)
class DecisionFollowUpCreate:
    follow_up_id: str
    decision_id: str
    observed_at: datetime
    observation_period: str | None
    realized_result: str
    realized_value_eur: Decimal | None
    realized_value_status: str | None
    evidence_effect: str
    notes: str | None
    actor: DecisionActor
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DecisionFollowUpRecord:
    follow_up_id: str
    decision_id: str
    observed_at: datetime
    observation_period: str | None
    realized_result: str
    realized_value_eur: Decimal | None
    realized_value_status: str | None
    evidence_effect: str
    notes: str | None
    actor: DecisionActor
    created_at: datetime


@runtime_checkable
class DecisionLedgerStore(Protocol):
    def create_decision_record(self, record: DecisionRecordCreate) -> DecisionRecord: ...

    def get_decision_record(self, decision_id: str) -> DecisionRecord: ...

    def list_decision_records(
        self,
        *,
        decision_key: str | None = None,
        subject_period: str | None = None,
    ) -> list[DecisionRecord]: ...

    def add_decision_follow_up(
        self, follow_up: DecisionFollowUpCreate
    ) -> DecisionFollowUpRecord: ...

    def list_decision_follow_ups(self, decision_id: str) -> list[DecisionFollowUpRecord]: ...


def aware_utc(value: datetime) -> datetime:
    """Normalize storage timestamps to aware UTC; naive values are UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return aware_utc(value)
    if isinstance(value, str):
        return aware_utc(datetime.fromisoformat(value))
    raise TypeError(f"Unsupported datetime value: {value!r}")


def coerce_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date value: {value!r}")


def coerce_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
