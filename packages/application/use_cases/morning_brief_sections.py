"""Built-in morning brief sections.

Each section is a pure function of :class:`BriefInputs`. Publication-backed
sections pass their publication through :func:`assess_claim` first and emit
a withheld item (with remediation) instead of a claim the confidence does
not support.

Sections and their sources:

==========  ==============================================  =====
key         source                                          order
==========  ==============================================  =====
money       ``mart_monthly_cashflow``                       10
attention   ``mart_open_attention_items``                   20
changes     ``mart_recent_significant_changes``             30
upcoming    ``mart_upcoming_fixed_costs_30d``               40
battery     ``mart_battery_plan_outcome``                   45
policies    policy engine verdicts (``PolicyResult``)       50
sources     source freshness (control plane + run metadata) 60
==========  ==============================================  =====

Orders are spaced by ten so later sections can slot in without
renumbering (the battery outcome section sits at 45).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from packages.application.use_cases.morning_brief import (
    BriefConfidence,
    BriefEvidenceRef,
    BriefInputs,
    BriefItem,
    BriefSectionRegistry,
    BriefSeverity,
    ClaimAssessment,
    ClaimStatus,
    EvidenceKind,
    FunctionSectionProvider,
    PublicationInput,
    SectionDraft,
    SectionStatus,
    assess_claim,
    publication_evidence,
    withheld_item,
)
from packages.shared.household_time import household_zone, local_date

MONTHLY_CASHFLOW_KEY = "mart_monthly_cashflow"
ATTENTION_ITEMS_KEY = "mart_open_attention_items"
RECENT_CHANGES_KEY = "mart_recent_significant_changes"
UPCOMING_FIXED_COSTS_KEY = "mart_upcoming_fixed_costs_30d"
BATTERY_PLAN_OUTCOME_KEY = "mart_battery_plan_outcome"

MAX_LIST_ITEMS = 5

_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def _signed(value: Decimal) -> str:
    return f"+{_money(value)}" if value > 0 else _money(value)


def _month_label(booking_month: str) -> str:
    try:
        year_s, month_s = booking_month[:7].split("-")
        return f"{_MONTH_NAMES[int(month_s) - 1]} {int(year_s)}"
    except (ValueError, IndexError):
        return booking_month


def _claim_item(
    *,
    item_id: str,
    severity: BriefSeverity,
    headline: str,
    detail: str | None,
    publication: PublicationInput,
    assessment: ClaimAssessment,
) -> BriefItem:
    return BriefItem(
        item_id=item_id,
        severity=severity,
        claim_status=assessment.status,
        headline=headline,
        detail=detail,
        caveats=assessment.caveats,
        remediation=assessment.remediation,
        confidence=assessment.confidence,
        evidence=publication_evidence(publication),
        lineage_publication_key=publication.publication_key,
    )


def _claim_summary(assessment: ClaimAssessment, text: str) -> str:
    if assessment.status == ClaimStatus.PROVISIONAL:
        return f"{text} (provisional)"
    return text


# ---------------------------------------------------------------------------
# money
# ---------------------------------------------------------------------------


def build_money_section(inputs: BriefInputs) -> SectionDraft:
    publication = inputs.publication(MONTHLY_CASHFLOW_KEY)
    assessment = assess_claim(publication)
    if assessment.status == ClaimStatus.WITHHELD:
        return SectionDraft(
            summary="Cashflow is withheld until its publication can be trusted.",
            items=(
                withheld_item(
                    "money:cashflow", "Cashflow is not stated.", publication, assessment
                ),
            ),
        )
    as_of_month = inputs.as_of.strftime("%Y-%m")
    months = sorted(
        (
            row
            for row in publication.rows or ()
            if str(row.get("booking_month") or "")[:7] <= as_of_month
            and _decimal(row.get("net")) is not None
        ),
        key=lambda row: str(row.get("booking_month")),
    )
    if not months:
        return SectionDraft(
            summary="No cashflow has been published yet.",
            items=(
                _claim_item(
                    item_id="money:cashflow",
                    severity=BriefSeverity.INFO,
                    headline="No cashflow months are published.",
                    detail=None,
                    publication=publication,
                    assessment=assessment,
                ),
            ),
        )
    latest = months[-1]
    month = str(latest.get("booking_month"))[:7]
    net = _decimal(latest.get("net")) or Decimal(0)
    income = _decimal(latest.get("income")) or Decimal(0)
    expense = _decimal(latest.get("expense")) or Decimal(0)

    flat_band = max(Decimal(1), abs(income) * Decimal("0.01"))
    streak = 0
    for row in reversed(months):
        if (_decimal(row.get("net")) or Decimal(0)) > flat_band:
            streak += 1
        else:
            break
    if abs(net) <= flat_band:
        branch = f"Cashflow for {_month_label(month)} is flat at {_signed(net)}."
        severity = BriefSeverity.INFO
    elif net < 0:
        branch = f"Cashflow for {_month_label(month)} is negative at {_signed(net)}."
        severity = BriefSeverity.WARNING
    elif streak >= 2:
        branch = (
            f"Cashflow for {_month_label(month)} is positive at {_signed(net)}, "
            f"{streak} positive months in a row."
        )
        severity = BriefSeverity.INFO
    else:
        branch = f"Cashflow for {_month_label(month)} is positive at {_signed(net)}."
        severity = BriefSeverity.INFO
    detail = f"Income {_money(income)}, expense {_money(expense)}."
    if month != as_of_month:
        detail += f" {_month_label(month)} is the latest published month."
    return SectionDraft(
        summary=_claim_summary(assessment, branch),
        items=(
            _claim_item(
                item_id="money:cashflow",
                severity=severity,
                headline=branch,
                detail=detail,
                publication=publication,
                assessment=assessment,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# attention / changes / upcoming
# ---------------------------------------------------------------------------

_ATTENTION_SEVERITY = {
    3: BriefSeverity.WARNING,
    2: BriefSeverity.NOTICE,
    1: BriefSeverity.INFO,
}


def _overflow_note(total: int) -> str:
    extra = total - MAX_LIST_ITEMS
    return f" {extra} more not shown." if extra > 0 else ""


def build_attention_section(inputs: BriefInputs) -> SectionDraft:
    publication = inputs.publication(ATTENTION_ITEMS_KEY)
    assessment = assess_claim(publication)
    if assessment.status == ClaimStatus.WITHHELD:
        return SectionDraft(
            summary="Open attention items are withheld.",
            items=(
                withheld_item(
                    "attention:items",
                    "Open attention items are not stated.",
                    publication,
                    assessment,
                ),
            ),
        )
    rows = sorted(
        publication.rows or (),
        key=lambda row: (-int(row.get("severity") or 0), str(row.get("item_id"))),
    )
    if not rows:
        return SectionDraft(
            summary=_claim_summary(assessment, "No open attention items."),
            items=(
                _claim_item(
                    item_id="attention:none",
                    severity=BriefSeverity.INFO,
                    headline="No open attention items.",
                    detail=None,
                    publication=publication,
                    assessment=assessment,
                ),
            ),
        )
    items = tuple(
        _claim_item(
            item_id=f"attention:{row.get('item_id')}",
            severity=_ATTENTION_SEVERITY.get(int(row.get("severity") or 1), BriefSeverity.INFO),
            headline=str(row.get("title")),
            detail=(
                f"{row.get('detail')} ({row.get('source_domain')}, {row.get('item_type')})"
            ),
            publication=publication,
            assessment=assessment,
        )
        for row in rows[:MAX_LIST_ITEMS]
    )
    summary = f"{len(rows)} open attention item{'s' if len(rows) != 1 else ''}."
    return SectionDraft(
        summary=_claim_summary(assessment, summary + _overflow_note(len(rows))),
        items=items,
    )


def build_changes_section(inputs: BriefInputs) -> SectionDraft:
    publication = inputs.publication(RECENT_CHANGES_KEY)
    assessment = assess_claim(publication)
    if assessment.status == ClaimStatus.WITHHELD:
        return SectionDraft(
            summary="Recent changes are withheld.",
            items=(
                withheld_item(
                    "changes:recent", "Recent changes are not stated.", publication, assessment
                ),
            ),
        )

    def magnitude(row: Mapping[str, Any]) -> Decimal:
        return abs(_decimal(row.get("change_pct")) or Decimal(0))

    rows = sorted(
        publication.rows or (),
        key=lambda row: (
            -magnitude(row),
            str(row.get("change_type")),
            str(row.get("period")),
            str(row.get("description")),
        ),
    )
    if not rows:
        return SectionDraft(
            summary=_claim_summary(assessment, "No significant changes recorded."),
            items=(
                _claim_item(
                    item_id="changes:none",
                    severity=BriefSeverity.INFO,
                    headline="No significant changes recorded.",
                    detail=None,
                    publication=publication,
                    assessment=assessment,
                ),
            ),
        )
    items = []
    for row in rows[:MAX_LIST_ITEMS]:
        pct = _decimal(row.get("change_pct"))
        current = _decimal(row.get("current_value")) or Decimal(0)
        previous = _decimal(row.get("previous_value")) or Decimal(0)
        pct_text = f" ({pct:+.1f}%)" if pct is not None else ""
        items.append(
            _claim_item(
                item_id=f"changes:{row.get('change_type')}:{row.get('period')}:{row.get('description')}",
                severity=BriefSeverity.NOTICE,
                headline=f"{row.get('description')}{pct_text}",
                detail=(
                    f"{row.get('period')}: {_money(previous)} → {_money(current)}, "
                    f"{row.get('direction')}."
                ),
                publication=publication,
                assessment=assessment,
            )
        )
    summary = f"{len(rows)} significant change{'s' if len(rows) != 1 else ''}."
    return SectionDraft(
        summary=_claim_summary(assessment, summary + _overflow_note(len(rows))),
        items=tuple(items),
    )


def build_upcoming_section(inputs: BriefInputs) -> SectionDraft:
    publication = inputs.publication(UPCOMING_FIXED_COSTS_KEY)
    assessment = assess_claim(publication)
    if assessment.status == ClaimStatus.WITHHELD:
        return SectionDraft(
            summary="Upcoming fixed costs are withheld.",
            items=(
                withheld_item(
                    "upcoming:fixed-costs",
                    "Upcoming fixed costs are not stated.",
                    publication,
                    assessment,
                ),
            ),
        )
    rows = sorted(
        publication.rows or (),
        key=lambda row: (
            str(row.get("expected_date")),
            str(row.get("contract_name")),
            str(row.get("provider")),
        ),
    )
    if not rows:
        return SectionDraft(
            summary=_claim_summary(assessment, "No fixed costs expected in the next 30 days."),
            items=(
                _claim_item(
                    item_id="upcoming:none",
                    severity=BriefSeverity.INFO,
                    headline="No fixed costs expected in the next 30 days.",
                    detail=None,
                    publication=publication,
                    assessment=assessment,
                ),
            ),
        )
    totals: dict[str, Decimal] = {}
    for row in rows:
        currency = str(row.get("currency") or "")
        totals[currency] = totals.get(currency, Decimal(0)) + (
            _decimal(row.get("expected_amount")) or Decimal(0)
        )
    total_text = ", ".join(
        f"{_money(amount)} {currency}".strip() for currency, amount in sorted(totals.items())
    )
    items = []
    for row in rows[:MAX_LIST_ITEMS]:
        amount = _decimal(row.get("expected_amount")) or Decimal(0)
        estimated = str(row.get("confidence") or "").lower() == "estimated"
        items.append(
            _claim_item(
                item_id=f"upcoming:{row.get('contract_name')}:{row.get('expected_date')}",
                severity=BriefSeverity.INFO,
                headline=(
                    f"{row.get('contract_name')} — {_money(amount)} "
                    f"{row.get('currency') or ''}".rstrip()
                    + f" on {row.get('expected_date')}"
                ),
                detail=(
                    f"{row.get('provider')}, {row.get('frequency')}"
                    + ("; amount is estimated." if estimated else ".")
                ),
                publication=publication,
                assessment=assessment,
            )
        )
    summary = (
        f"{len(rows)} fixed cost{'s' if len(rows) != 1 else ''} due in 30 days, "
        f"totalling {total_text}."
    )
    return SectionDraft(
        summary=_claim_summary(assessment, summary + _overflow_note(len(rows))),
        items=tuple(items),
    )


# ---------------------------------------------------------------------------
# battery
# ---------------------------------------------------------------------------

_BATTERY_ESTIMATE_CAVEAT = (
    "Source estimate, not realized savings; review-only, it authorizes no tariff, "
    "contract or battery change."
)


def build_battery_section(inputs: BriefInputs) -> SectionDraft:
    """Latest battery-plan outcome month: verdict, or why no claim is made.

    Publication confidence gates the claim first (withheld / provisional /
    confirmed). A confirmed publication can still carry an
    ``insufficient_evidence`` verdict; that is stated as such, with the
    publication's remediation, never as a savings claim.
    """
    publication = inputs.publication(BATTERY_PLAN_OUTCOME_KEY)
    assessment = assess_claim(publication)
    if assessment.status == ClaimStatus.WITHHELD:
        return SectionDraft(
            summary="The battery-plan outcome is withheld.",
            items=(
                withheld_item(
                    "battery:outcome",
                    "The battery-plan outcome is not stated.",
                    publication,
                    assessment,
                ),
            ),
        )
    rows = sorted(
        publication.rows or (), key=lambda row: str(row.get("decision_month")), reverse=True
    )
    if not rows:
        return SectionDraft(
            summary=_claim_summary(assessment, "No battery-plan outcome is published."),
            items=(
                BriefItem(
                    item_id="battery:none",
                    severity=BriefSeverity.INFO,
                    claim_status=assessment.status,
                    headline="No battery-plan outcome is published.",
                    caveats=assessment.caveats,
                    remediation="Run the refresh-battery-plan-outcome worker command.",
                    confidence=assessment.confidence,
                    evidence=publication_evidence(publication),
                    lineage_publication_key=publication.publication_key,
                ),
            ),
        )
    row = rows[0]
    month = str(row.get("decision_month"))
    verdict = str(row.get("verdict"))
    savings = _decimal(row.get("estimated_savings_eur"))
    cost = _decimal(row.get("effective_monthly_cost_eur"))
    caveats = (*assessment.caveats, _BATTERY_ESTIMATE_CAVEAT)
    if verdict == "benefit_estimated" and savings is not None and cost is not None:
        severity = BriefSeverity.INFO
        headline = (
            f"Battery plan {_month_label(month)}: estimated savings {_money(savings)} EUR "
            f"cover the {_money(cost)} EUR monthly cost."
        )
        remediation = None
    elif verdict == "no_benefit_estimated" and savings is not None and cost is not None:
        severity = BriefSeverity.NOTICE
        headline = (
            f"Battery plan {_month_label(month)}: estimated savings {_money(savings)} EUR "
            f"stay below the {_money(cost)} EUR monthly cost; a review may be due."
        )
        remediation = None
    else:
        severity = BriefSeverity.NOTICE
        headline = (
            f"Battery plan {_month_label(month)}: evidence is insufficient, "
            "so no savings claim is made."
        )
        remediation = str(row.get("remediation") or "") or None
    coverage = _decimal(row.get("coverage_pct"))
    detail = (
        f"Coverage {coverage:g}% of five-minute windows; source {row.get('freshness_status')}."
        if coverage is not None
        else None
    )
    item = BriefItem(
        item_id=f"battery:{month}",
        severity=severity,
        claim_status=assessment.status,
        headline=headline,
        detail=detail,
        caveats=caveats,
        remediation=remediation or assessment.remediation,
        confidence=assessment.confidence,
        evidence=publication_evidence(publication),
        lineage_publication_key=publication.publication_key,
    )
    return SectionDraft(summary=_claim_summary(assessment, headline), items=(item,))


# ---------------------------------------------------------------------------
# policies
# ---------------------------------------------------------------------------

_POLICY_SEVERITY = {
    "breach": BriefSeverity.CRITICAL,
    "warning": BriefSeverity.WARNING,
    "ok": BriefSeverity.INFO,
}


def _policy_confidence(policy: Any) -> BriefConfidence | None:
    if policy.input_verdict is None:
        return None
    return BriefConfidence(
        publication_key=policy.publication_key,
        verdict=str(policy.input_verdict),
        freshness_state=str(policy.input_freshness_state or "unavailable"),
        completeness_pct=policy.input_completeness_pct,
        validation_state="unknown",
        completeness_state="unknown",
        assessed_at=policy.input_assessed_at,
    )


def build_policies_section(inputs: BriefInputs) -> SectionDraft:
    if inputs.policies is None:
        return SectionDraft(
            summary="Policy verdicts are unavailable.",
            items=(
                BriefItem(
                    item_id="policies:engine",
                    severity=BriefSeverity.NOTICE,
                    claim_status=ClaimStatus.WITHHELD,
                    headline="Policy verdicts are not stated.",
                    caveats=("The policy evaluator is not running in this API process.",),
                    remediation=(
                        "Enable the Home Assistant policy runtime so policies are evaluated."
                    ),
                ),
            ),
        )
    if not inputs.policies:
        return SectionDraft(
            summary="No policies are defined.",
            items=(
                BriefItem(
                    item_id="policies:none",
                    severity=BriefSeverity.INFO,
                    claim_status=ClaimStatus.CONFIRMED,
                    headline="No policies are defined.",
                    remediation="Author a policy under Control → Policies to watch a threshold.",
                ),
            ),
        )
    items: list[BriefItem] = []
    passing: list[str] = []
    for policy in sorted(
        inputs.policies,
        key=lambda p: (-_rank(_POLICY_SEVERITY.get(p.verdict, BriefSeverity.NOTICE)), p.policy_id),
    ):
        evidence: list[BriefEvidenceRef] = [
            BriefEvidenceRef(EvidenceKind.POLICY, policy.policy_id, policy.name)
        ]
        if policy.publication_key:
            evidence.append(
                BriefEvidenceRef(
                    EvidenceKind.PUBLICATION, policy.publication_key, policy.publication_key
                )
            )
        confidence = _policy_confidence(policy)
        if policy.verdict == "ok":
            passing.append(policy.policy_id)
            continue
        if policy.verdict in _POLICY_SEVERITY:
            caveats: tuple[str, ...] = ()
            status = ClaimStatus.CONFIRMED
            if confidence is None:
                status = ClaimStatus.PROVISIONAL
                caveats = ("Input confidence is not tracked for this policy.",)
            elif confidence.verdict != "trustworthy":
                status = ClaimStatus.PROVISIONAL
                caveats = (f"Policy input confidence is {confidence.verdict}.",)
            items.append(
                BriefItem(
                    item_id=f"policies:{policy.policy_id}",
                    severity=_POLICY_SEVERITY[policy.verdict],
                    claim_status=status,
                    headline=f"{policy.name}: {policy.verdict}.",
                    detail=policy.reason,
                    caveats=caveats,
                    confidence=confidence,
                    evidence=tuple(evidence),
                    lineage_publication_key=policy.publication_key,
                )
            )
            continue
        # unavailable (or an unknown verdict): no verdict is claimed.
        reason = policy.reason or "No reason was recorded."
        if policy.publication_key and "stale" in reason:
            remediation = (
                f"Upload the missing period for the sources of {policy.publication_key}, "
                "then refresh it."
            )
        else:
            remediation = "Supply the inputs the policy reads, then re-evaluate."
        items.append(
            BriefItem(
                item_id=f"policies:{policy.policy_id}",
                severity=BriefSeverity.NOTICE,
                claim_status=ClaimStatus.WITHHELD,
                headline=f"{policy.name}: no verdict.",
                caveats=(reason,),
                remediation=remediation,
                confidence=confidence,
                evidence=tuple(evidence),
                lineage_publication_key=policy.publication_key,
            )
        )
    if passing:
        items.append(
            BriefItem(
                item_id="policies:passing",
                severity=BriefSeverity.INFO,
                claim_status=ClaimStatus.CONFIRMED,
                headline=f"{len(passing)} polic{'ies' if len(passing) != 1 else 'y'} passing.",
                detail=", ".join(passing),
                evidence=tuple(
                    BriefEvidenceRef(EvidenceKind.POLICY, pid, pid) for pid in passing
                ),
            )
        )
    breaches = sum(1 for p in inputs.policies if p.verdict == "breach")
    warnings = sum(1 for p in inputs.policies if p.verdict == "warning")
    unavailable = sum(1 for p in inputs.policies if p.verdict not in _POLICY_SEVERITY)
    summary = (
        f"{len(inputs.policies)} policies: {breaches} breach, {warnings} warning, "
        f"{len(passing)} ok, {unavailable} without a verdict."
    )
    if inputs.policy_authority_mode:
        summary += f" Authority: {inputs.policy_authority_mode}."
    return SectionDraft(summary=summary, items=tuple(items))


def _rank(severity: BriefSeverity) -> int:
    return list(BriefSeverity).index(severity)


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------


def build_sources_section(inputs: BriefInputs) -> SectionDraft:
    if inputs.sources is None:
        return SectionDraft(
            summary="Source freshness is unavailable.",
            items=(
                BriefItem(
                    item_id="sources:registry",
                    severity=BriefSeverity.NOTICE,
                    claim_status=ClaimStatus.WITHHELD,
                    headline="Source freshness is not stated.",
                    caveats=("The source registry could not be read.",),
                    remediation="Check that the control-plane store is reachable.",
                ),
            ),
        )
    if not inputs.sources:
        return SectionDraft(
            summary="No sources are registered.",
            items=(
                BriefItem(
                    item_id="sources:none",
                    severity=BriefSeverity.NOTICE,
                    claim_status=ClaimStatus.CONFIRMED,
                    headline="No sources are registered.",
                    remediation="Register a source asset under Sources and upload its first export.",
                ),
            ),
        )
    items: list[BriefItem] = []
    current: list[str] = []
    zone = household_zone(inputs.timezone)
    for source in inputs.sources:
        state = source.freshness_state
        evidence: list[BriefEvidenceRef] = [
            BriefEvidenceRef(EvidenceKind.SOURCE, source.source_asset_id, source.name)
        ]
        if source.latest_run_id:
            evidence.append(
                BriefEvidenceRef(EvidenceKind.RUN, source.latest_run_id, f"run {source.latest_run_id}")
            )
        next_expected = (
            local_date(source.next_expected_at, zone).isoformat()
            if source.next_expected_at
            else None
        )
        landed = local_date(source.landed_at, zone).isoformat() if source.landed_at else "never"
        if state == "current":
            current.append(source.name)
            continue
        remediation: str | None
        if state in ("overdue", "missing_period"):
            severity = BriefSeverity.WARNING
            headline = f"{source.name} is {state.replace('_', ' ')}."
            remediation = f"Upload the missing period for {source.name}."
        elif state == "parse_failed":
            severity = BriefSeverity.WARNING
            headline = f"{source.name}: the latest ingest failed."
            remediation = (
                f"Fix the export and retry run {source.latest_run_id}."
                if source.latest_run_id
                else "Fix the export and upload it again."
            )
        elif state == "due_soon":
            severity = BriefSeverity.INFO
            headline = f"{source.name} is due soon."
            remediation = (
                f"Upload the next export by {next_expected}." if next_expected else None
            )
        else:  # unconfigured or unknown
            severity = BriefSeverity.NOTICE
            headline = f"{source.name} has no freshness schedule."
            remediation = (
                f"Configure source freshness for {source.name} so staleness can be judged."
            )
        detail = f"Last ingest {landed}"
        if source.covered_through:
            detail += f", covered through {source.covered_through.isoformat()}"
        if next_expected and state != "due_soon":
            detail += f", next expected {next_expected}"
        items.append(
            BriefItem(
                item_id=f"sources:{source.source_asset_id}",
                severity=severity,
                claim_status=ClaimStatus.CONFIRMED,
                headline=headline,
                detail=detail + ".",
                remediation=remediation,
                evidence=tuple(evidence),
            )
        )
    items.sort(key=lambda item: (-_rank(item.severity), item.item_id))
    if current:
        items.append(
            BriefItem(
                item_id="sources:current",
                severity=BriefSeverity.INFO,
                claim_status=ClaimStatus.CONFIRMED,
                headline=f"{len(current)} of {len(inputs.sources)} sources are current.",
                detail=", ".join(sorted(current)),
            )
        )
    stale = sum(1 for s in inputs.sources if s.freshness_state in ("overdue", "missing_period", "parse_failed"))
    summary = f"{len(current)} of {len(inputs.sources)} sources current"
    summary += f", {stale} need an upload or retry." if stale else "."
    unjudged = any(
        s.freshness_state not in ("current", "due_soon") for s in inputs.sources
    )
    return SectionDraft(
        summary=summary,
        items=tuple(items),
        status_floor=SectionStatus.DEGRADED if unjudged else None,
    )


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def builtin_brief_section_providers() -> tuple[FunctionSectionProvider, ...]:
    return (
        FunctionSectionProvider("money", "Money", 10, (MONTHLY_CASHFLOW_KEY,), build_money_section),
        FunctionSectionProvider(
            "attention", "Needs attention", 20, (ATTENTION_ITEMS_KEY,), build_attention_section
        ),
        FunctionSectionProvider(
            "changes", "What changed", 30, (RECENT_CHANGES_KEY,), build_changes_section
        ),
        FunctionSectionProvider(
            "upcoming", "Coming up", 40, (UPCOMING_FIXED_COSTS_KEY,), build_upcoming_section
        ),
        FunctionSectionProvider(
            "battery", "Battery plan", 45, (BATTERY_PLAN_OUTCOME_KEY,), build_battery_section
        ),
        FunctionSectionProvider("policies", "Policies", 50, (), build_policies_section),
        FunctionSectionProvider("sources", "Sources", 60, (), build_sources_section),
    )


def default_brief_section_registry() -> BriefSectionRegistry:
    """Registry with the built-in sections. Callers may ``register`` more."""
    return BriefSectionRegistry(builtin_brief_section_providers())
