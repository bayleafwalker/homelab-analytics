"""Unit tests for the deterministic morning brief composer (Kotona B1)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from packages.application.use_cases.morning_brief import (
    BriefInputs,
    BriefItem,
    BriefSectionRegistry,
    BriefSeverity,
    ClaimStatus,
    ConfidenceEvidence,
    FunctionSectionProvider,
    PolicyEvidence,
    PublicationInput,
    SectionDraft,
    SectionStatus,
    SourceEvidence,
    assess_claim,
    compose_morning_brief,
    gather_brief_inputs,
)
from packages.application.use_cases.morning_brief_sections import (
    ATTENTION_ITEMS_KEY,
    MONTHLY_CASHFLOW_KEY,
    RECENT_CHANGES_KEY,
    UPCOMING_FIXED_COSTS_KEY,
    default_brief_section_registry,
)

AS_OF = date(2026, 10, 18)
GENERATED_AT = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
ASSESSED_AT = datetime(2026, 10, 18, 5, 0, tzinfo=UTC)


def _confidence(key: str, **overrides: Any) -> ConfidenceEvidence:
    base = ConfidenceEvidence(
        publication_key=key,
        verdict="trustworthy",
        freshness_state="current",
        completeness_pct=100,
        assessed_at=ASSESSED_AT,
        quality_flags={"validation_errors": 0, "rejected_runs": 0},
        contributing_run_ids=("run-2", "run-1"),
        source_states=(("bank_csv", "current"),),
    )
    return replace(base, **overrides)


CASHFLOW_ROWS = (
    {"booking_month": "2026-08", "income": "5000", "expense": "4000", "net": "1000"},
    {"booking_month": "2026-09", "income": "5000", "expense": "4200", "net": "800"},
    {"booking_month": "2026-10", "income": "5100", "expense": "3866.5", "net": "1233.5"},
)


def _publications(**confidence_overrides: Any) -> dict[str, PublicationInput]:
    return {
        MONTHLY_CASHFLOW_KEY: PublicationInput(
            MONTHLY_CASHFLOW_KEY,
            CASHFLOW_ROWS,
            _confidence(MONTHLY_CASHFLOW_KEY, **confidence_overrides),
        ),
        ATTENTION_ITEMS_KEY: PublicationInput(
            ATTENTION_ITEMS_KEY,
            (
                {
                    "item_id": "a2",
                    "item_type": "contract_renewal",
                    "title": "Electricity contract renews",
                    "detail": "Renews in 14 days",
                    "severity": 2,
                    "source_domain": "utilities",
                },
                {
                    "item_id": "a1",
                    "item_type": "anomaly",
                    "title": "Unusual grocery spend",
                    "detail": "2.1x the 3-month average",
                    "severity": 3,
                    "source_domain": "finance",
                },
            ),
            _confidence(ATTENTION_ITEMS_KEY),
        ),
        RECENT_CHANGES_KEY: PublicationInput(
            RECENT_CHANGES_KEY,
            (
                {
                    "change_type": "utility_cost",
                    "period": "2026-10",
                    "description": "Electricity cost",
                    "current_value": "120",
                    "previous_value": "80",
                    "change_pct": "50",
                    "direction": "up",
                },
            ),
            _confidence(RECENT_CHANGES_KEY),
        ),
        UPCOMING_FIXED_COSTS_KEY: PublicationInput(
            UPCOMING_FIXED_COSTS_KEY,
            (
                {
                    "contract_name": "Internet",
                    "provider": "ISP",
                    "frequency": "monthly",
                    "expected_amount": "39.90",
                    "currency": "EUR",
                    "expected_date": "2026-10-25",
                    "confidence": "high",
                },
            ),
            _confidence(UPCOMING_FIXED_COSTS_KEY),
        ),
    }


POLICIES = (
    PolicyEvidence(
        policy_id="budget_status",
        name="Budget status",
        verdict="breach",
        value="104.0%",
        reason="Highest budget utilisation 104.0% is over 100%.",
        evaluated_at="2026-10-18T05:59:00+00:00",
    ),
    PolicyEvidence(
        policy_id="negative_cashflow",
        name="Negative cashflow",
        verdict="unavailable",
        value="-10",
        reason="stale input: publication 'mart_monthly_cashflow' is stale",
        evaluated_at="2026-10-18T05:59:00+00:00",
        publication_key=MONTHLY_CASHFLOW_KEY,
        input_verdict="degraded",
        input_freshness_state="stale",
        input_completeness_pct=100,
        input_assessed_at=ASSESSED_AT.isoformat(),
    ),
    PolicyEvidence(
        policy_id="bridge_health",
        name="Bridge health",
        verdict="ok",
        value="12s",
        reason="Bridge heartbeat is recent.",
        evaluated_at="2026-10-18T05:59:00+00:00",
    ),
)


def _source(asset_id: str, state: str, **kw: Any) -> SourceEvidence:
    defaults: dict[str, Any] = dict(
        source_asset_id=asset_id,
        name=asset_id.replace("_", " ").title(),
        dataset_name=asset_id,
        freshness_state=state,
        latest_run_id=f"run-{asset_id}",
        latest_status="landed",
        landed_at=datetime(2026, 9, 2, tzinfo=UTC),
        next_expected_at=datetime(2026, 10, 5, tzinfo=UTC),
        covered_through=None,
        suggested_action="none",
    )
    defaults.update(kw)
    return SourceEvidence(**defaults)


SOURCES = (
    _source("bank_csv", "current"),
    _source("electricity", "overdue", suggested_action="upload_missing_period"),
    _source("card_invoice", "parse_failed", latest_status="failed"),
    _source("loan_registry", "unconfigured"),
)


def _inputs(**kw: Any) -> BriefInputs:
    defaults: dict[str, Any] = dict(
        as_of=AS_OF,
        generated_at=GENERATED_AT,
        publications=_publications(),
        policies=POLICIES,
        policy_authority_mode="registry",
        sources=SOURCES,
    )
    defaults.update(kw)
    return BriefInputs(**defaults)


def _section(brief: Any, key: str) -> Any:
    return next(section for section in brief.sections if section.key == key)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_inputs_produce_identical_output() -> None:
    first = compose_morning_brief(_inputs())
    second = compose_morning_brief(_inputs())
    assert json.dumps(first.as_dict(), sort_keys=True) == json.dumps(
        second.as_dict(), sort_keys=True
    )
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 64


def test_content_hash_ignores_generated_at_but_tracks_content() -> None:
    base = compose_morning_brief(_inputs())
    later = compose_morning_brief(_inputs(generated_at=datetime(2026, 10, 18, 9, tzinfo=UTC)))
    assert base.content_hash == later.content_hash
    assert base.as_dict()["generated_at"] != later.as_dict()["generated_at"]
    changed = compose_morning_brief(_inputs(sources=SOURCES[:1]))
    assert changed.content_hash != base.content_hash


def test_gathering_is_order_independent() -> None:
    class Reader:
        def __init__(self, reverse: bool) -> None:
            self.reverse = reverse

        def read_publication(self, key: str) -> list[dict[str, Any]]:
            rows = list(_publications()[key].rows or ())
            return list(reversed(rows)) if self.reverse else rows

    class Store:
        def list_publication_confidence_snapshots(self, *, publication_key=None, limit=None):
            return [
                SimpleNamespace(
                    publication_key=publication_key,
                    confidence_verdict="trustworthy",
                    freshness_state="current",
                    completeness_pct=100,
                    assessed_at=ASSESSED_AT.isoformat(),
                    quality_flags={"validation_errors": 0},
                    contributing_run_ids=["run-1"],
                    source_freshness_states={"b": {"freshness_state": "current"}, "a": {"freshness_state": "current"}},
                )
            ]

    policy_dicts = [
        {
            "id": p.policy_id,
            "name": p.name,
            "verdict": p.verdict,
            "value": p.value,
            "reason": p.reason,
            "evaluated_at": p.evaluated_at,
            "metadata": {"publication_key": p.publication_key} if p.publication_key else {},
            "input_freshness": None,
        }
        for p in POLICIES
    ]
    registry = default_brief_section_registry()

    def gathered(reverse: bool) -> Any:
        return gather_brief_inputs(
            as_of=AS_OF,
            generated_at=GENERATED_AT,
            registry=registry,
            reader=Reader(reverse),
            confidence_store=Store(),
            policy_results=list(reversed(policy_dicts)) if reverse else policy_dicts,
            policy_authority_mode="registry",
            source_views=list(reversed(SOURCES)) if reverse else list(SOURCES),
        )

    forward = compose_morning_brief(gathered(False), registry)
    backward = compose_morning_brief(gathered(True), registry)
    assert forward.as_dict() == backward.as_dict()
    money = _section(forward, "money").items[0]
    assert money.claim_status == ClaimStatus.CONFIRMED
    assert [ref.ref for ref in money.evidence if ref.kind == "source"] == ["a", "b"]


# ---------------------------------------------------------------------------
# Honesty ladder
# ---------------------------------------------------------------------------


def test_trustworthy_cashflow_is_confirmed_claim_with_lineage() -> None:
    brief = compose_morning_brief(_inputs())
    item = _section(brief, "money").items[0]
    assert item.claim_status == ClaimStatus.CONFIRMED
    assert "October 2026" in item.headline
    assert "+1,233.50" in item.headline
    assert "3 positive months in a row" in item.headline
    assert item.lineage_publication_key == MONTHLY_CASHFLOW_KEY
    assert item.confidence is not None and item.confidence.verdict == "trustworthy"
    run_refs = [ref.ref for ref in item.evidence if ref.kind == "run"]
    assert run_refs == ["run-1", "run-2"]


@pytest.mark.parametrize(
    "overrides,expected_fragment",
    [
        ({"freshness_state": "stale", "verdict": "degraded",
          "source_states": (("bank_csv", "overdue"),)}, "bank_csv"),
        ({"freshness_state": "unavailable", "verdict": "unavailable"}, "Configure source freshness"),
        ({"verdict": "degraded", "quality_flags": {}}, "landing validation"),
        ({"verdict": "degraded", "quality_flags": {
            "validation_errors": 0,
            "completeness_expected_sources": 1,
            "completeness_unknown_sources": 1,
        }}, "run history"),
        ({"verdict": "unreliable", "completeness_pct": 30}, "Ingest the missing sources"),
    ],
)
def test_untrusted_cashflow_is_withheld_with_remediation(
    overrides: dict[str, Any], expected_fragment: str
) -> None:
    brief = compose_morning_brief(_inputs(publications=_publications(**overrides)))
    section = _section(brief, "money")
    item = section.items[0]
    assert item.claim_status == ClaimStatus.WITHHELD
    assert "1,233" not in item.headline and "1,233" not in (item.detail or "")
    assert item.remediation and expected_fragment in item.remediation
    assert item.lineage_publication_key == MONTHLY_CASHFLOW_KEY
    assert section.status == SectionStatus.UNAVAILABLE


def test_missing_snapshot_and_unreadable_rows_are_withheld() -> None:
    no_snapshot = assess_claim(PublicationInput("mart_x", (), None))
    assert no_snapshot.status == ClaimStatus.WITHHELD
    assert "transformation refresh" in (no_snapshot.remediation or "")
    unreadable = assess_claim(
        PublicationInput("mart_x", None, _confidence("mart_x"), error="KeyError")
    )
    assert unreadable.status == ClaimStatus.WITHHELD
    assert "KeyError" in unreadable.caveats[0]


def test_degraded_but_known_signals_is_provisional_with_caveats() -> None:
    brief = compose_morning_brief(
        _inputs(
            publications=_publications(
                verdict="degraded",
                freshness_state="due_soon",
                quality_flags={"validation_errors": 3, "rejected_runs": 0},
            )
        )
    )
    section = _section(brief, "money")
    item = section.items[0]
    assert item.claim_status == ClaimStatus.PROVISIONAL
    assert "+1,233.50" in item.headline
    assert any("due" in caveat for caveat in item.caveats)
    assert any("3 validation issue" in caveat for caveat in item.caveats)
    assert section.summary.endswith("(provisional)")
    assert section.status == SectionStatus.DEGRADED


def test_negative_cashflow_is_a_warning() -> None:
    rows = CASHFLOW_ROWS[:2] + (
        {"booking_month": "2026-10", "income": "3000", "expense": "3500", "net": "-500"},
    )
    pubs = _publications()
    pubs[MONTHLY_CASHFLOW_KEY] = replace(pubs[MONTHLY_CASHFLOW_KEY], rows=rows)
    item = _section(compose_morning_brief(_inputs(publications=pubs)), "money").items[0]
    assert item.severity == BriefSeverity.WARNING
    assert "negative at -500.00" in item.headline


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def test_attention_items_sorted_by_severity() -> None:
    items = _section(compose_morning_brief(_inputs()), "attention").items
    assert [item.item_id for item in items] == ["attention:a1", "attention:a2"]
    assert items[0].severity == BriefSeverity.WARNING


def test_empty_trusted_publication_states_absence() -> None:
    pubs = _publications()
    pubs[ATTENTION_ITEMS_KEY] = replace(pubs[ATTENTION_ITEMS_KEY], rows=())
    items = _section(compose_morning_brief(_inputs(publications=pubs)), "attention").items
    assert [item.headline for item in items] == ["No open attention items."]
    assert items[0].claim_status == ClaimStatus.CONFIRMED


def test_policy_section_reports_verdicts_reasons_and_remediation() -> None:
    section = _section(compose_morning_brief(_inputs()), "policies")
    by_id = {item.item_id: item for item in section.items}
    breach = by_id["policies:budget_status"]
    assert breach.severity == BriefSeverity.CRITICAL
    assert breach.detail == "Highest budget utilisation 104.0% is over 100%."
    assert breach.claim_status == ClaimStatus.PROVISIONAL  # no input confidence tracked
    stale = by_id["policies:negative_cashflow"]
    assert stale.claim_status == ClaimStatus.WITHHELD
    assert stale.remediation and "Upload the missing period" in stale.remediation
    assert stale.lineage_publication_key == MONTHLY_CASHFLOW_KEY
    assert by_id["policies:passing"].detail == "bridge_health"
    assert "Authority: registry." in section.summary


def test_policy_engine_absent_is_withheld() -> None:
    section = _section(compose_morning_brief(_inputs(policies=None)), "policies")
    assert section.status == SectionStatus.UNAVAILABLE
    assert section.items[0].remediation


def test_sources_section_gives_remediation_per_state() -> None:
    section = _section(compose_morning_brief(_inputs()), "sources")
    by_id = {item.item_id: item for item in section.items}
    assert by_id["sources:electricity"].severity == BriefSeverity.WARNING
    assert "Upload the missing period" in (by_id["sources:electricity"].remediation or "")
    assert "retry run run-card_invoice" in (by_id["sources:card_invoice"].remediation or "")
    assert "Configure source freshness" in (by_id["sources:loan_registry"].remediation or "")
    assert by_id["sources:current"].headline == "1 of 4 sources are current."
    run_refs = [ref.ref for ref in by_id["sources:electricity"].evidence if ref.kind == "run"]
    assert run_refs == ["run-electricity"]
    assert section.status == SectionStatus.ATTENTION


def test_unconfigured_sources_degrade_the_section() -> None:
    sources = (_source("bank_csv", "current"), _source("loan_registry", "unconfigured"))
    section = _section(compose_morning_brief(_inputs(sources=sources)), "sources")
    assert section.status == SectionStatus.DEGRADED
    current_only = _section(compose_morning_brief(_inputs(sources=sources[:1])), "sources")
    assert current_only.status == SectionStatus.OK


def test_brief_headline_and_counts() -> None:
    brief = compose_morning_brief(_inputs())
    assert brief.overall_severity == BriefSeverity.CRITICAL
    assert brief.counts["withheld"] == 1
    assert brief.headline.startswith(f"{brief.counts['warning'] + brief.counts['critical']} items need attention")
    assert [s.key for s in brief.sections] == [
        "money", "attention", "changes", "upcoming", "policies", "sources",
    ]


# ---------------------------------------------------------------------------
# Registry / extension point
# ---------------------------------------------------------------------------


def test_registry_rejects_duplicate_keys() -> None:
    registry = default_brief_section_registry()
    with pytest.raises(ValueError):
        registry.register(
            FunctionSectionProvider("money", "Dup", 1, (), lambda _: SectionDraft("", ()))
        )


def test_extension_section_slots_in_by_order_and_declares_publications() -> None:
    def build(inputs: BriefInputs) -> SectionDraft:
        publication = inputs.publication("mart_battery_outcome")
        assessment = assess_claim(publication)
        return SectionDraft(
            summary="battery",
            items=(
                BriefItem(
                    item_id="battery:outcome",
                    severity=BriefSeverity.INFO,
                    claim_status=assessment.status,
                    headline="Battery outcome",
                    remediation=assessment.remediation,
                ),
            ),
        )

    registry = default_brief_section_registry()
    registry.register(
        FunctionSectionProvider("battery", "Battery", 45, ("mart_battery_outcome",), build)
    )
    assert "mart_battery_outcome" in registry.publication_keys()
    brief = compose_morning_brief(_inputs(), registry)
    assert [s.key for s in brief.sections].index("battery") == 4
    # Not gathered → withheld, not invented.
    assert _section(brief, "battery").items[0].claim_status == ClaimStatus.WITHHELD


def test_failing_section_degrades_without_hiding_others() -> None:
    def boom(_: BriefInputs) -> SectionDraft:
        raise RuntimeError("broken")

    registry = BriefSectionRegistry(default_brief_section_registry().providers())
    registry.register(FunctionSectionProvider("broken", "Broken", 99, (), boom))
    brief = compose_morning_brief(_inputs(), registry)
    broken = _section(brief, "broken")
    assert broken.status == SectionStatus.UNAVAILABLE
    assert "RuntimeError" in broken.items[0].caveats[0]
    assert _section(brief, "money").items[0].claim_status == ClaimStatus.CONFIRMED
