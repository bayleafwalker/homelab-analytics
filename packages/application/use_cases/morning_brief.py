"""Deterministic morning brief (Kotona Stage B1).

The brief is a typed, deterministic composition over facts the platform
already publishes:

- reporting publications (``mart_*`` relations read through the reporting
  layer, never landing payloads),
- policy verdicts from the A1/A2 policy engine (``PolicyResult`` with its
  ``reason``),
- per-source freshness (``docs/product/source-freshness-workflow.md``),
- publication confidence snapshots
  (``packages/platform/publication_confidence.py``).

There is no LLM and no free text generation: every line is produced by a
section provider from a fixed template over typed inputs.

Honesty contract
----------------
Every item carries a ``claim_status``:

- ``confirmed`` — the backing publication's confidence verdict is
  ``trustworthy`` (all signals known and clean).
- ``provisional`` — the verdict is ``degraded`` but no signal is unknown and
  no source is stale; the claim is shown together with the caveats that
  degraded it.
- ``withheld`` — no claim is made. The item says *why* (no snapshot, stale
  or unavailable freshness, unknown validation or completeness, unreliable
  verdict, unreadable publication) and gives the remediation instead.

See :func:`assess_claim` for the exact ladder.

Determinism
-----------
:func:`compose_morning_brief` is a pure function of :class:`BriefInputs`
(including the injected ``as_of`` date and ``generated_at`` clock): equal
inputs produce byte-identical ``as_dict()`` output. ``content_hash`` is a
SHA-256 over the canonical JSON of the brief without ``generated_at`` so two
briefs with the same content compare equal across regenerations.

Extension point
---------------
Sections are pluggable through :class:`BriefSectionRegistry`. A provider
declares a ``key``, ``title``, ``order`` and the ``publication_keys`` it
reads; the gatherer fetches exactly those publications (rows + latest
confidence snapshot) and hands them to ``build``. A future section — for
example a battery-outcome section over a battery outcome publication — is
added by implementing :class:`BriefSectionProvider`, registering it on the
registry passed to the composer, and making its publication readable by the
API's publication reader (``apps/api/routes/briefing_routes.py``). No
composer change is needed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from packages.platform.publication_confidence import (
    COMPLETENESS_UNKNOWN_SOURCES_FLAG,
    REJECTED_RUNS_FLAG,
    VALIDATION_ERRORS_FLAG,
    VALIDATION_UNKNOWN_RUNS_FLAG,
    ConfidenceVerdict,
    FreshnessState,
    SignalState,
    completeness_signal_state,
    validation_signal_state,
)

BRIEF_SCHEMA_VERSION = "1.0.0"


class BriefSeverity(StrEnum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


_SEVERITY_RANK = {
    BriefSeverity.INFO: 0,
    BriefSeverity.NOTICE: 1,
    BriefSeverity.WARNING: 2,
    BriefSeverity.CRITICAL: 3,
}


class ClaimStatus(StrEnum):
    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    WITHHELD = "withheld"


class SectionStatus(StrEnum):
    OK = "ok"
    ATTENTION = "attention"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class EvidenceKind(StrEnum):
    PUBLICATION = "publication"
    RUN = "run"
    SOURCE = "source"
    POLICY = "policy"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfidenceEvidence:
    """Latest confidence snapshot for one publication, as plain data."""

    publication_key: str
    verdict: str
    freshness_state: str
    completeness_pct: int
    assessed_at: datetime
    quality_flags: Mapping[str, int] = field(default_factory=dict)
    contributing_run_ids: tuple[str, ...] = ()
    # (source_asset_id, freshness_state) pairs, sorted by source id.
    source_states: tuple[tuple[str, str], ...] = ()

    @property
    def validation_state(self) -> SignalState:
        return validation_signal_state(self.quality_flags)

    @property
    def completeness_state(self) -> SignalState:
        return completeness_signal_state(self.quality_flags)


@dataclass(frozen=True)
class PublicationInput:
    """Rows and confidence for one reporting publication.

    ``rows`` is ``None`` when the publication could not be read; ``error``
    then carries the reason.
    """

    publication_key: str
    rows: tuple[Mapping[str, Any], ...] | None
    confidence: ConfidenceEvidence | None
    error: str | None = None


@dataclass(frozen=True)
class PolicyEvidence:
    """One policy verdict, reduced from ``PolicyResult.to_dict()``."""

    policy_id: str
    name: str
    verdict: str
    value: str | None
    reason: str | None
    evaluated_at: str
    publication_key: str | None = None
    input_verdict: str | None = None
    input_freshness_state: str | None = None
    input_completeness_pct: int | None = None
    input_assessed_at: str | None = None

    @classmethod
    def from_result_dict(cls, payload: Mapping[str, Any]) -> PolicyEvidence:
        metadata = payload.get("metadata") or {}
        freshness = payload.get("input_freshness") or {}
        publication_key = metadata.get("publication_key")
        return cls(
            policy_id=str(payload.get("id")),
            name=str(payload.get("name") or payload.get("id")),
            verdict=str(payload.get("verdict")),
            value=payload.get("value"),
            reason=payload.get("reason"),
            evaluated_at=str(payload.get("evaluated_at") or ""),
            publication_key=publication_key if isinstance(publication_key, str) else None,
            input_verdict=freshness.get("verdict"),
            input_freshness_state=freshness.get("freshness_state"),
            input_completeness_pct=freshness.get("completeness_pct"),
            input_assessed_at=freshness.get("assessed_at"),
        )


@dataclass(frozen=True)
class SourceEvidence:
    """Freshness of one source asset (see ``SourceFreshnessView``)."""

    source_asset_id: str
    name: str
    dataset_name: str
    freshness_state: str
    latest_run_id: str | None
    latest_status: str | None
    landed_at: datetime | None
    next_expected_at: datetime | None
    covered_through: date | None
    suggested_action: str


@dataclass(frozen=True)
class BriefInputs:
    """Everything the composer reads. ``None`` collections mean unavailable."""

    as_of: date
    generated_at: datetime
    publications: Mapping[str, PublicationInput] = field(default_factory=dict)
    policies: tuple[PolicyEvidence, ...] | None = None
    policy_authority_mode: str | None = None
    sources: tuple[SourceEvidence, ...] | None = None

    def publication(self, key: str) -> PublicationInput:
        found = self.publications.get(key)
        if found is not None:
            return found
        return PublicationInput(
            publication_key=key,
            rows=None,
            confidence=None,
            error="publication was not gathered",
        )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BriefEvidenceRef:
    kind: EvidenceKind
    ref: str
    label: str

    def as_dict(self) -> dict[str, Any]:
        return {"kind": str(self.kind), "ref": self.ref, "label": self.label}


@dataclass(frozen=True)
class BriefConfidence:
    """Confidence shown next to an item."""

    publication_key: str | None
    verdict: str
    freshness_state: str
    completeness_pct: int | None
    validation_state: str
    completeness_state: str
    assessed_at: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "publication_key": self.publication_key,
            "verdict": self.verdict,
            "freshness_state": self.freshness_state,
            "completeness_pct": self.completeness_pct,
            "validation_state": self.validation_state,
            "completeness_state": self.completeness_state,
            "assessed_at": self.assessed_at,
        }


@dataclass(frozen=True)
class BriefItem:
    item_id: str
    severity: BriefSeverity
    claim_status: ClaimStatus
    headline: str
    detail: str | None = None
    caveats: tuple[str, ...] = ()
    remediation: str | None = None
    confidence: BriefConfidence | None = None
    evidence: tuple[BriefEvidenceRef, ...] = ()
    # Publication the lineage drill opens at; None when the item is not
    # backed by a publication (e.g. a source-freshness line, which links to
    # its run instead).
    lineage_publication_key: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "severity": str(self.severity),
            "claim_status": str(self.claim_status),
            "headline": self.headline,
            "detail": self.detail,
            "caveats": list(self.caveats),
            "remediation": self.remediation,
            "confidence": self.confidence.as_dict() if self.confidence else None,
            "evidence": [ref.as_dict() for ref in self.evidence],
            "lineage_publication_key": self.lineage_publication_key,
        }


@dataclass(frozen=True)
class SectionDraft:
    """What a provider returns; the composer derives status and ordering."""

    summary: str
    items: tuple[BriefItem, ...]
    # Lowest status the section may report. Lets a provider mark itself
    # degraded for gaps that are facts rather than withheld claims (e.g.
    # sources without a freshness schedule).
    status_floor: SectionStatus | None = None


@dataclass(frozen=True)
class BriefSection:
    key: str
    title: str
    order: int
    status: SectionStatus
    summary: str
    publication_keys: tuple[str, ...]
    items: tuple[BriefItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "order": self.order,
            "status": str(self.status),
            "summary": self.summary,
            "publication_keys": list(self.publication_keys),
            "items": [item.as_dict() for item in self.items],
        }


@dataclass(frozen=True)
class MorningBrief:
    schema_version: str
    as_of: date
    generated_at: datetime
    headline: str
    overall_severity: BriefSeverity
    counts: Mapping[str, int]
    sections: tuple[BriefSection, ...]
    content_hash: str

    def content_dict(self) -> dict[str, Any]:
        """Canonical content without ``generated_at`` / ``content_hash``."""
        return {
            "schema_version": self.schema_version,
            "as_of": self.as_of.isoformat(),
            "headline": self.headline,
            "overall_severity": str(self.overall_severity),
            "counts": dict(sorted(self.counts.items())),
            "sections": [section.as_dict() for section in self.sections],
        }

    def as_dict(self) -> dict[str, Any]:
        payload = self.content_dict()
        payload["generated_at"] = self.generated_at.isoformat()
        payload["content_hash"] = self.content_hash
        return payload


# ---------------------------------------------------------------------------
# Honesty ladder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimAssessment:
    status: ClaimStatus
    caveats: tuple[str, ...]
    remediation: str | None
    confidence: BriefConfidence | None


def confidence_view(evidence: ConfidenceEvidence | None, key: str) -> BriefConfidence:
    if evidence is None:
        return BriefConfidence(
            publication_key=key,
            verdict=str(ConfidenceVerdict.UNAVAILABLE),
            freshness_state=str(FreshnessState.UNAVAILABLE),
            completeness_pct=None,
            validation_state=str(SignalState.UNKNOWN),
            completeness_state=str(SignalState.UNKNOWN),
            assessed_at=None,
        )
    return BriefConfidence(
        publication_key=key,
        verdict=evidence.verdict,
        freshness_state=evidence.freshness_state,
        completeness_pct=evidence.completeness_pct,
        validation_state=str(evidence.validation_state),
        completeness_state=str(evidence.completeness_state),
        assessed_at=evidence.assessed_at.isoformat(),
    )


_STALE_SOURCE_STATES = {"overdue", "missing_period", "parse_failed"}


def _stale_sources(evidence: ConfidenceEvidence) -> list[str]:
    return [asset for asset, state in evidence.source_states if state in _STALE_SOURCE_STATES]


def assess_claim(publication: PublicationInput) -> ClaimAssessment:
    """Decide whether a claim backed by ``publication`` may be made.

    Ladder, evaluated in order:

    1. rows unreadable → withheld ("could not be read").
    2. no confidence snapshot → withheld (refresh to assess).
    3. freshness ``stale`` → withheld (upload the missing period).
    4. freshness ``unavailable`` or verdict ``unavailable`` → withheld
       (configure source freshness).
    5. validation signal ``unknown`` → withheld (re-run ingestion so landing
       validation is recorded).
    6. completeness signal ``unknown`` → withheld.
    7. verdict ``unreliable`` → withheld.
    8. verdict ``trustworthy`` → confirmed.
    9. otherwise (``degraded``) → provisional with every degrading caveat.
    """
    key = publication.publication_key
    evidence = publication.confidence
    view = confidence_view(evidence, key)
    if publication.rows is None:
        return ClaimAssessment(
            ClaimStatus.WITHHELD,
            (f"{key} could not be read: {publication.error or 'unknown error'}.",),
            f"Refresh the reporting layer so {key} is published, then reload the brief.",
            view,
        )
    if evidence is None:
        return ClaimAssessment(
            ClaimStatus.WITHHELD,
            (f"No confidence snapshot has been recorded for {key}.",),
            f"Run a transformation refresh for {key} so its confidence is assessed.",
            view,
        )
    verdict = evidence.verdict.lower()
    freshness = evidence.freshness_state.lower()
    if freshness == FreshnessState.STALE:
        stale = _stale_sources(evidence)
        named = f" ({', '.join(stale)})" if stale else ""
        return ClaimAssessment(
            ClaimStatus.WITHHELD,
            (f"{key} is stale: at least one contributing source is overdue or missing a period.",),
            f"Upload the missing period for the stale sources{named}, then refresh {key}.",
            view,
        )
    if freshness == FreshnessState.UNAVAILABLE or verdict == ConfidenceVerdict.UNAVAILABLE:
        return ClaimAssessment(
            ClaimStatus.WITHHELD,
            (f"Freshness for {key} is unavailable: its sources have no freshness schedule.",),
            f"Configure source freshness for the sources feeding {key}.",
            view,
        )
    if evidence.validation_state == SignalState.UNKNOWN:
        return ClaimAssessment(
            ClaimStatus.WITHHELD,
            (f"Validation for the runs feeding {key} is unknown.",),
            "Re-run ingestion for the contributing runs so landing validation is recorded.",
            view,
        )
    if evidence.completeness_state == SignalState.UNKNOWN:
        return ClaimAssessment(
            ClaimStatus.WITHHELD,
            (f"Completeness of {key} is unknown: no contributing source run could be resolved.",),
            "Check run history for the contributing sources and re-run the missing ingests.",
            view,
        )
    if verdict == ConfidenceVerdict.UNRELIABLE:
        return ClaimAssessment(
            ClaimStatus.WITHHELD,
            (f"{key} is unreliable ({evidence.completeness_pct}% of sources covered).",),
            "Ingest the missing sources and fix validation errors, then refresh.",
            view,
        )
    if verdict == ConfidenceVerdict.TRUSTWORTHY:
        return ClaimAssessment(ClaimStatus.CONFIRMED, (), None, view)

    caveats: list[str] = []
    if freshness == FreshnessState.DUE_SOON:
        caveats.append("A contributing source is due for its next ingest soon.")
    if evidence.completeness_pct < 100:
        caveats.append(f"Only {evidence.completeness_pct}% of contributing sources are covered.")
    flags = evidence.quality_flags
    validation_errors = int(flags.get(VALIDATION_ERRORS_FLAG, 0))
    rejected_runs = int(flags.get(REJECTED_RUNS_FLAG, 0))
    if validation_errors:
        caveats.append(f"{validation_errors} validation issue(s) were recorded.")
    if rejected_runs:
        caveats.append(f"{rejected_runs} contributing run(s) were rejected.")
    unknown_runs = int(flags.get(VALIDATION_UNKNOWN_RUNS_FLAG, 0))
    if unknown_runs:
        caveats.append(f"Validation is unknown for {unknown_runs} contributing run(s).")
    unknown_sources = int(flags.get(COMPLETENESS_UNKNOWN_SOURCES_FLAG, 0))
    if unknown_sources:
        caveats.append(f"Run metadata is missing for {unknown_sources} contributing source(s).")
    if not caveats:
        caveats.append(f"Confidence for {key} is degraded.")
    return ClaimAssessment(ClaimStatus.PROVISIONAL, tuple(caveats), None, view)


def publication_evidence(publication: PublicationInput) -> tuple[BriefEvidenceRef, ...]:
    """Evidence refs for a publication-backed item: the publication + runs."""
    refs = [
        BriefEvidenceRef(
            EvidenceKind.PUBLICATION, publication.publication_key, publication.publication_key
        )
    ]
    if publication.confidence is not None:
        for run_id in sorted(set(publication.confidence.contributing_run_ids)):
            refs.append(BriefEvidenceRef(EvidenceKind.RUN, run_id, f"run {run_id}"))
        for asset_id, state in publication.confidence.source_states:
            refs.append(BriefEvidenceRef(EvidenceKind.SOURCE, asset_id, f"{asset_id} ({state})"))
    return tuple(refs)


def withheld_item(
    item_id: str,
    headline: str,
    publication: PublicationInput,
    assessment: ClaimAssessment,
) -> BriefItem:
    """The item a section emits instead of a claim it cannot back."""
    return BriefItem(
        item_id=item_id,
        severity=BriefSeverity.NOTICE,
        claim_status=ClaimStatus.WITHHELD,
        headline=headline,
        detail=None,
        caveats=assessment.caveats,
        remediation=assessment.remediation,
        confidence=assessment.confidence,
        evidence=publication_evidence(publication),
        lineage_publication_key=publication.publication_key,
    )


# ---------------------------------------------------------------------------
# Section registry
# ---------------------------------------------------------------------------


class BriefSectionProvider(Protocol):
    """A pluggable brief section.

    ``build`` must be a pure function of ``inputs``: no clock reads, no I/O,
    no randomness. It reads only the publications it lists in
    ``publication_keys`` (plus ``inputs.policies`` / ``inputs.sources``).
    """

    @property
    def key(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def order(self) -> int: ...

    @property
    def publication_keys(self) -> tuple[str, ...]: ...

    def build(self, inputs: BriefInputs) -> SectionDraft: ...


@dataclass(frozen=True)
class FunctionSectionProvider:
    """Convenience provider wrapping a plain build function."""

    key: str
    title: str
    order: int
    publication_keys: tuple[str, ...]
    builder: Callable[[BriefInputs], SectionDraft]

    def build(self, inputs: BriefInputs) -> SectionDraft:
        return self.builder(inputs)


class BriefSectionRegistry:
    """Ordered set of section providers keyed by ``key``."""

    def __init__(self, providers: Iterable[BriefSectionProvider] = ()) -> None:
        self._providers: dict[str, BriefSectionProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: BriefSectionProvider) -> None:
        if provider.key in self._providers:
            raise ValueError(f"Brief section already registered: {provider.key}")
        self._providers[provider.key] = provider

    def providers(self) -> tuple[BriefSectionProvider, ...]:
        return tuple(sorted(self._providers.values(), key=lambda p: (p.order, p.key)))

    def keys(self) -> tuple[str, ...]:
        return tuple(provider.key for provider in self.providers())

    def publication_keys(self) -> tuple[str, ...]:
        keys: set[str] = set()
        for provider in self._providers.values():
            keys.update(provider.publication_keys)
        return tuple(sorted(keys))


# ---------------------------------------------------------------------------
# Composer
# ---------------------------------------------------------------------------


def _section_status(items: Sequence[BriefItem]) -> SectionStatus:
    if items and all(item.claim_status == ClaimStatus.WITHHELD for item in items):
        return SectionStatus.UNAVAILABLE
    if any(_SEVERITY_RANK[item.severity] >= 2 for item in items):
        return SectionStatus.ATTENTION
    if any(item.claim_status != ClaimStatus.CONFIRMED for item in items):
        return SectionStatus.DEGRADED
    return SectionStatus.OK


_STATUS_RANK = {
    SectionStatus.OK: 0,
    SectionStatus.DEGRADED: 1,
    SectionStatus.ATTENTION: 2,
    SectionStatus.UNAVAILABLE: 3,
}


def _apply_status_floor(
    status: SectionStatus, floor: SectionStatus | None
) -> SectionStatus:
    if floor is not None and _STATUS_RANK[floor] > _STATUS_RANK[status]:
        return floor
    return status


def _failed_section_draft(provider: BriefSectionProvider, exc: Exception) -> SectionDraft:
    return SectionDraft(
        summary=f"{provider.title} could not be assembled.",
        items=(
            BriefItem(
                item_id=f"{provider.key}:build-failed",
                severity=BriefSeverity.NOTICE,
                claim_status=ClaimStatus.WITHHELD,
                headline=f"{provider.title} is unavailable.",
                caveats=(f"The section failed to build ({type(exc).__name__}).",),
                remediation="Check the API logs for the briefing route.",
            ),
        ),
    )


def _headline(sections: Sequence[BriefSection], counts: Mapping[str, int]) -> str:
    attention = counts.get("warning", 0) + counts.get("critical", 0)
    withheld = counts.get("withheld", 0)
    parts: list[str] = []
    if attention:
        parts.append(f"{attention} item{'s' if attention != 1 else ''} need attention")
    else:
        parts.append("Nothing confirmed needs attention")
    if withheld:
        parts.append(
            f"{withheld} line{'s' if withheld != 1 else ''} withheld for stale or unknown data"
        )
    return "; ".join(parts) + "."


def _content_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compose_morning_brief(
    inputs: BriefInputs,
    registry: BriefSectionRegistry | None = None,
) -> MorningBrief:
    """Compose the brief. Pure: same inputs and registry → identical output."""
    if registry is None:
        from packages.application.use_cases.morning_brief_sections import (
            default_brief_section_registry,
        )

        registry = default_brief_section_registry()
    sections: list[BriefSection] = []
    for provider in registry.providers():
        try:
            draft = provider.build(inputs)
        except Exception as exc:  # a broken section must not hide the others
            draft = _failed_section_draft(provider, exc)
        sections.append(
            BriefSection(
                key=provider.key,
                title=provider.title,
                order=provider.order,
                status=_apply_status_floor(_section_status(draft.items), draft.status_floor),
                summary=draft.summary,
                publication_keys=tuple(sorted(provider.publication_keys)),
                items=draft.items,
            )
        )

    counts: dict[str, int] = {str(s): 0 for s in BriefSeverity}
    counts.update({str(c): 0 for c in ClaimStatus})
    overall = BriefSeverity.INFO
    for section in sections:
        for item in section.items:
            counts[str(item.severity)] += 1
            counts[str(item.claim_status)] += 1
            if _SEVERITY_RANK[item.severity] > _SEVERITY_RANK[overall]:
                overall = item.severity

    brief = MorningBrief(
        schema_version=BRIEF_SCHEMA_VERSION,
        as_of=inputs.as_of,
        generated_at=inputs.generated_at,
        headline=_headline(sections, counts),
        overall_severity=overall,
        counts=counts,
        sections=tuple(sections),
        content_hash="",
    )
    return MorningBrief(
        schema_version=brief.schema_version,
        as_of=brief.as_of,
        generated_at=brief.generated_at,
        headline=brief.headline,
        overall_severity=brief.overall_severity,
        counts=brief.counts,
        sections=brief.sections,
        content_hash=_content_hash(brief.content_dict()),
    )


# ---------------------------------------------------------------------------
# Gathering (I/O lives here, not in the composer)
# ---------------------------------------------------------------------------


class PublicationReader(Protocol):
    """Reads app-facing rows for a reporting publication by key."""

    def read_publication(self, publication_key: str) -> Sequence[Mapping[str, Any]]: ...


class ConfidenceSnapshotStore(Protocol):
    def list_publication_confidence_snapshots(
        self, *, publication_key: str | None = None, limit: int | None = None
    ) -> Any: ...


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def confidence_evidence_from_record(record: Any) -> ConfidenceEvidence:
    """Build :class:`ConfidenceEvidence` from a control-plane snapshot record."""
    states_raw = getattr(record, "source_freshness_states", None) or {}
    source_states = tuple(
        sorted(
            (str(asset_id), str((state or {}).get("freshness_state") or "unknown"))
            for asset_id, state in states_raw.items()
        )
    )
    return ConfidenceEvidence(
        publication_key=str(record.publication_key),
        verdict=str(record.confidence_verdict),
        freshness_state=str(record.freshness_state),
        completeness_pct=int(record.completeness_pct),
        assessed_at=_as_datetime(record.assessed_at),
        quality_flags=dict(getattr(record, "quality_flags", None) or {}),
        contributing_run_ids=tuple(getattr(record, "contributing_run_ids", None) or ()),
        source_states=source_states,
    )


def gather_publication_input(
    publication_key: str,
    *,
    reader: PublicationReader | None,
    confidence_store: ConfidenceSnapshotStore | None,
) -> PublicationInput:
    confidence: ConfidenceEvidence | None = None
    if confidence_store is not None:
        try:
            records = confidence_store.list_publication_confidence_snapshots(
                publication_key=publication_key, limit=1
            )
        except Exception:
            records = []
        if records:
            confidence = confidence_evidence_from_record(records[0])
    if reader is None:
        return PublicationInput(
            publication_key, None, confidence, error="no reporting service is configured"
        )
    try:
        rows = tuple(dict(row) for row in reader.read_publication(publication_key))
    except Exception as exc:
        return PublicationInput(publication_key, None, confidence, error=type(exc).__name__)
    return PublicationInput(publication_key, rows, confidence)


def source_evidence_from_view(view: Any) -> SourceEvidence:
    """Reduce a ``SourceFreshnessView`` (or pass a ``SourceEvidence`` through)."""
    if isinstance(view, SourceEvidence):
        return view
    return SourceEvidence(
        source_asset_id=str(view.source_asset_id),
        name=str(view.name),
        dataset_name=str(view.dataset_name),
        freshness_state=str(view.freshness_state),
        latest_run_id=view.latest_run_id,
        latest_status=view.status,
        landed_at=view.landed_at,
        next_expected_at=view.next_expected_at,
        covered_through=view.covered_through,
        suggested_action=str(view.suggested_action),
    )


def gather_brief_inputs(
    *,
    as_of: date,
    generated_at: datetime,
    registry: BriefSectionRegistry,
    reader: PublicationReader | None,
    confidence_store: ConfidenceSnapshotStore | None,
    policy_results: Sequence[Mapping[str, Any]] | None,
    policy_authority_mode: str | None,
    source_views: Sequence[Any] | None,
) -> BriefInputs:
    """Collect every input the registered sections declare."""
    publications = {
        key: gather_publication_input(key, reader=reader, confidence_store=confidence_store)
        for key in registry.publication_keys()
    }
    policies = (
        None
        if policy_results is None
        else tuple(
            sorted(
                (PolicyEvidence.from_result_dict(result) for result in policy_results),
                key=lambda p: p.policy_id,
            )
        )
    )
    sources = (
        None
        if source_views is None
        else tuple(
            sorted(
                (source_evidence_from_view(view) for view in source_views),
                key=lambda s: s.source_asset_id,
            )
        )
    )
    return BriefInputs(
        as_of=as_of,
        generated_at=generated_at,
        publications=publications,
        policies=policies,
        policy_authority_mode=policy_authority_mode,
        sources=sources,
    )
