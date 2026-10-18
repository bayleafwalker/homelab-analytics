"""Answer-honesty guidance for agents, derived from publication confidence.

Agents read publications through the semantic index; this module turns the
latest :class:`PublicationConfidenceSnapshot` into a small, explicit trust
block so an agent knows whether it may state figures as current, must add a
caveat, or must refuse a confident claim. The mapping mirrors the operator
semantics of the confidence surface (``/control/confidence``) and the policy
engine: stale or degraded data degrades visibly, and *no snapshot* is never
treated as *trustworthy*.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal

from packages.platform.publication_confidence import (
    ConfidenceVerdict,
    FreshnessState,
    PublicationConfidenceSnapshot,
)

AnswerGuidance = Literal[
    "state_as_current",
    "state_with_caveat",
    "do_not_state_as_current",
    "trust_unknown",
]

# Ordered from most to least trustworthy; used to pick the worst of a set.
_GUIDANCE_ORDER: tuple[AnswerGuidance, ...] = (
    "state_as_current",
    "state_with_caveat",
    "trust_unknown",
    "do_not_state_as_current",
)

_GUIDANCE_COPY: dict[AnswerGuidance, str] = {
    "state_as_current": (
        "Sources are current and complete; figures may be stated as current."
    ),
    "state_with_caveat": (
        "Usable but degraded or due for refresh; state figures with the "
        "assessed_at date and the caveat."
    ),
    "do_not_state_as_current": (
        "Stale, unreliable, or unavailable; do not present figures as current. "
        "Say the data is out of date and cite assessed_at."
    ),
    "trust_unknown": (
        "No confidence snapshot exists for this publication; do not claim the "
        "figures are current. Say freshness is unknown."
    ),
}

ConfidenceLookup = Callable[[str], "PublicationConfidenceSnapshot | None"]


@dataclass(frozen=True)
class PublicationTrust:
    """Trust state of one publication, shaped for agents and reviewers."""

    publication_key: str
    confidence_verdict: str | None
    freshness_state: str | None
    completeness_pct: int | None
    assessed_at: str | None
    guidance: AnswerGuidance
    guidance_detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "publication_key": self.publication_key,
            "confidence_verdict": self.confidence_verdict,
            "freshness_state": self.freshness_state,
            "completeness_pct": self.completeness_pct,
            "assessed_at": self.assessed_at,
            "guidance": self.guidance,
            "guidance_detail": self.guidance_detail,
        }


def _guidance_for(snapshot: PublicationConfidenceSnapshot) -> AnswerGuidance:
    verdict = snapshot.confidence_verdict
    freshness = snapshot.freshness_state
    if verdict in (ConfidenceVerdict.UNRELIABLE, ConfidenceVerdict.UNAVAILABLE):
        return "do_not_state_as_current"
    if freshness in (FreshnessState.STALE, FreshnessState.UNAVAILABLE):
        return "do_not_state_as_current"
    if verdict == ConfidenceVerdict.DEGRADED or freshness == FreshnessState.DUE_SOON:
        return "state_with_caveat"
    return "state_as_current"


def assess_publication_trust(
    publication_key: str,
    snapshot: PublicationConfidenceSnapshot | None,
) -> PublicationTrust:
    if snapshot is None:
        return PublicationTrust(
            publication_key=publication_key,
            confidence_verdict=None,
            freshness_state=None,
            completeness_pct=None,
            assessed_at=None,
            guidance="trust_unknown",
            guidance_detail=_GUIDANCE_COPY["trust_unknown"],
        )
    guidance = _guidance_for(snapshot)
    return PublicationTrust(
        publication_key=publication_key,
        confidence_verdict=str(snapshot.confidence_verdict),
        freshness_state=str(snapshot.freshness_state),
        completeness_pct=snapshot.completeness_pct,
        assessed_at=snapshot.assessed_at.isoformat(),
        guidance=guidance,
        guidance_detail=_GUIDANCE_COPY[guidance],
    )


def safe_confidence_lookup(
    lookup: ConfidenceLookup | None,
) -> Callable[[str], PublicationConfidenceSnapshot | None]:
    """Wrap a lookup so storage errors read as *no snapshot*, never *trusted*."""

    def resolve(publication_key: str) -> PublicationConfidenceSnapshot | None:
        if lookup is None:
            return None
        try:
            return lookup(publication_key)
        except Exception:  # noqa: BLE001 - absence must degrade, not raise
            return None

    return resolve


def worst_guidance(guidances: Iterable[AnswerGuidance]) -> AnswerGuidance:
    """Least trustworthy guidance of a set (``trust_unknown`` when empty)."""
    resolved = list(guidances)
    if not resolved:
        return "trust_unknown"
    return max(resolved, key=_GUIDANCE_ORDER.index)


def guidance_detail(guidance: AnswerGuidance) -> str:
    return _GUIDANCE_COPY[guidance]
