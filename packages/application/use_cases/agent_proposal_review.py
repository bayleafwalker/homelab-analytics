"""Operator review model for approval-gated action proposals.

Builds what an operator needs to decide on a proposal without leaving the
inbox:

- **effect** — what approval actually does for this adapter (in-registry
  only for ``platform`` proposals; HA approval-notification release for
  ``home_assistant`` proposals). Nothing here actuates a device.
- **change preview** — a diff-style before/after list of the fields that
  approval changes or that the proposal asserts.
- **evidence** — every publication the proposer cited, with its trust state
  at draft time next to its trust state now, so drift since drafting is
  visible, plus contract and lineage paths for drill-down.
- **trust** — the worst current guidance across cited publications and
  caveats the inbox must show (no cited evidence, unknown publications,
  degraded trust since draft).

The builder is pure: callers pass the proposal, the known publication names,
and a confidence lookup. It reads publication *metadata* only, never rows.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from packages.application.use_cases.agent_trust import (
    AnswerGuidance,
    ConfidenceLookup,
    assess_publication_trust,
    guidance_detail,
    safe_confidence_lookup,
    worst_guidance,
)
from packages.platform.action_proposals import (
    ADAPTER_HOME_ASSISTANT,
    ADAPTER_PLATFORM,
    ActionProposal,
)

PROPOSAL_REVIEW_SCHEMA_VERSION = "1.0.0"

EffectKind = Literal["in_registry_only", "release_ha_approval", "adapter_release"]


def _effect(proposal: ActionProposal) -> dict[str, Any]:
    if proposal.adapter == ADAPTER_HOME_ASSISTANT:
        return {
            "adapter": proposal.adapter,
            "kind": "release_ha_approval",
            "summary": (
                "Approving releases the pending Home Assistant approval "
                f"notification {proposal.notification_id!r}. The platform "
                "does not actuate devices; Home Assistant automations act on "
                "the released notification."
            ),
            "external_effect": True,
        }
    if proposal.adapter == ADAPTER_PLATFORM:
        return {
            "adapter": proposal.adapter,
            "kind": "in_registry_only",
            "summary": (
                "Approving records the decision in the proposal queue only. "
                "No external system is called and no canonical state changes."
            ),
            "external_effect": False,
        }
    return {
        "adapter": proposal.adapter,
        "kind": "adapter_release",
        "summary": (
            f"Approving hands the decision to the {proposal.adapter!r} adapter. "
            "This adapter has no release path in this deployment, so the "
            "decision is recorded in-registry only."
        ),
        "external_effect": False,
    }


def _change_preview(proposal: ActionProposal) -> list[dict[str, Any]]:
    resolved = proposal.status != "pending"
    rows: list[dict[str, Any]] = [
        {
            "field": "status",
            "label": "Status",
            "before": "pending" if not resolved else proposal.status,
            "after": "approved" if not resolved else proposal.status,
            "changes": not resolved,
        }
    ]
    previous_verdict = proposal.metadata.get("previous_verdict")
    rows.append(
        {
            "field": "verdict",
            "label": "Verdict",
            "before": None if previous_verdict is None else str(previous_verdict),
            "after": proposal.verdict,
            "changes": previous_verdict is not None and str(previous_verdict) != proposal.verdict,
        }
    )
    if proposal.value is not None:
        rows.append(
            {
                "field": "value",
                "label": "Proposed value",
                "before": None,
                "after": proposal.value,
                "changes": True,
            }
        )
    return rows


def build_proposal_review(
    proposal: ActionProposal,
    *,
    publication_names: Mapping[str, str],
    confidence_lookup: ConfidenceLookup | None,
) -> dict[str, Any]:
    lookup = safe_confidence_lookup(confidence_lookup)
    provenance = proposal.provenance
    cited: Sequence[str] = provenance.publication_keys if provenance is not None else ()

    evidence: list[dict[str, Any]] = []
    caveats: list[str] = []
    current_guidances: list[AnswerGuidance] = []
    for key in cited:
        known = key in publication_names
        trust_now = assess_publication_trust(key, lookup(key)) if known else None
        if trust_now is not None:
            current_guidances.append(trust_now.guidance)
        evidence.append(
            {
                "publication_key": key,
                "display_name": publication_names.get(key),
                "known": known,
                "at_draft": {
                    "confidence_verdict": provenance.confidence_verdict_at_draft
                    if provenance is not None
                    else None,
                    "freshness_state": provenance.freshness_state_at_draft
                    if provenance is not None
                    else None,
                    "assessed_at": provenance.assessed_at if provenance is not None else None,
                },
                "now": trust_now.as_dict() if trust_now is not None else None,
                "contract_path": f"/contracts/publications/{key}" if known else None,
                "lineage_path": f"/api/lineage/publication/{key}" if known else None,
            }
        )
        if not known:
            caveats.append(
                f"Cited publication {key!r} is not in the publication catalog; "
                "the proposer may have invented or mistyped it."
            )

    if not cited:
        caveats.append(
            "The proposer cited no publications; there is no evidence trail "
            "to check this proposal against."
        )
    overall = worst_guidance(current_guidances)
    if overall == "do_not_state_as_current":
        caveats.append(
            "At least one cited publication is stale or unreliable now; the "
            "proposal may rest on out-of-date figures."
        )
    elif overall == "trust_unknown" and cited:
        caveats.append(
            "No confidence snapshot exists for the cited evidence; freshness "
            "cannot be confirmed."
        )
    if provenance is not None and provenance.confidence_verdict_at_draft not in (
        None,
        "trustworthy",
    ):
        caveats.append(
            "The proposer drafted this while its evidence was "
            f"{provenance.confidence_verdict_at_draft}."
        )

    return {
        "schema_version": PROPOSAL_REVIEW_SCHEMA_VERSION,
        "proposal": proposal.to_dict(),
        "effect": _effect(proposal),
        "change_preview": _change_preview(proposal),
        "evidence": evidence,
        "trust": {
            "guidance": overall,
            "guidance_detail": guidance_detail(overall),
            "caveats": caveats,
        },
    }


def stamp_provenance_trust(
    publication_keys: Sequence[str],
    confidence_lookup: ConfidenceLookup | None,
) -> dict[str, str | None]:
    """Worst-case trust of cited publications, for stamping at draft time.

    Returns the ``confidence_verdict_at_draft`` / ``freshness_state_at_draft``
    / ``assessed_at`` triple for the least trustworthy cited publication, or
    nulls when no snapshot exists — never an optimistic default.
    """
    lookup = safe_confidence_lookup(confidence_lookup)
    trusts = [assess_publication_trust(key, lookup(key)) for key in publication_keys]
    if not trusts:
        return {
            "confidence_verdict_at_draft": None,
            "freshness_state_at_draft": None,
            "assessed_at": None,
        }
    worst_kind = worst_guidance(trust.guidance for trust in trusts)
    worst = next(trust for trust in trusts if trust.guidance == worst_kind)
    return {
        "confidence_verdict_at_draft": worst.confidence_verdict,
        "freshness_state_at_draft": worst.freshness_state,
        "assessed_at": worst.assessed_at,
    }


def summarize_agent_principals(proposals: Sequence[ActionProposal]) -> list[dict[str, Any]]:
    """Agent identities observed in the queue (not a registration authority).

    Groups agent- and assistant-drafted proposals by the authenticated
    creator and declared origin, so the operator can see who is proposing,
    how often, and with what outcome.
    """
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for proposal in proposals:
        if proposal.source_kind not in ("agent", "assistant"):
            continue
        creator = proposal.created_by or "unknown"
        key = (creator, proposal.policy_id)
        group = groups.setdefault(
            key,
            {
                "created_by": creator,
                "origin": proposal.policy_id,
                "source_kind": proposal.source_kind,
                "proposal_count": 0,
                "pending": 0,
                "approved": 0,
                "dismissed": 0,
                "first_seen_at": proposal.created_at,
                "last_seen_at": proposal.created_at,
                "cited_publications": set(),
            },
        )
        group["proposal_count"] += 1
        group[proposal.status] += 1
        group["first_seen_at"] = min(group["first_seen_at"], proposal.created_at)
        group["last_seen_at"] = max(group["last_seen_at"], proposal.created_at)
        if proposal.provenance is not None:
            group["cited_publications"].update(proposal.provenance.publication_keys)
    principals = []
    for group in groups.values():
        group["cited_publications"] = sorted(group["cited_publications"])
        principals.append(group)
    return sorted(principals, key=lambda item: item["last_seen_at"], reverse=True)
