from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Literal

_log = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException

from apps.api.response_models import (
    AnswerConfidenceSummary,
    AssistantAnswerResponseModel,
    AssistantSourceModel,
)

if TYPE_CHECKING:
    from packages.storage.control_plane import ControlPlaneStore
from packages.pipelines.composition.publication_contract_inputs import (
    HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS,
    build_household_publication_relation_map,
)
from packages.pipelines.publication_confidence_service import (
    get_latest_publication_confidence,
)
from packages.pipelines.reporting_service import ReportingService
from packages.platform.capability_types import CapabilityPack
from packages.platform.publication_confidence import PublicationConfidenceSnapshot
from packages.platform.publication_contracts import (
    build_publication_contracts,
    build_ui_descriptor_contracts,
)
from packages.platform.publication_index import (
    PublicationSemanticIndexEntry,
    build_publication_semantic_index,
)
from packages.shared.extensions import ExtensionRegistry

_REPORT_PATH_BY_PUBLICATION_KEY: dict[str, str] = {
    "mart_monthly_cashflow": "/reports/monthly-cashflow",
    "mart_spend_by_category_monthly": "/reports/spend-by-category-monthly",
    "mart_upcoming_fixed_costs_30d": "/reports/upcoming-fixed-costs",
    "mart_utility_cost_summary": "/reports/utility-cost-summary",
    "mart_utility_cost_trend_monthly": "/reports/utility-cost-trend",
    "mart_usage_vs_price_summary": "/reports/usage-vs-price",
    "mart_contract_price_current": "/reports/contract-prices",
    "mart_electricity_price_current": "/reports/electricity-prices",
    "mart_open_attention_items": "/reports/attention-items",
    "mart_recent_significant_changes": "/reports/recent-changes",
    "mart_current_operating_baseline": "/reports/operating-baseline",
    "mart_homelab_roi": "/reports/homelab-roi",
}

_FINANCE_KEYWORDS = {
    "burn",
    "cash",
    "cashflow",
    "cost",
    "debt",
    "expense",
    "expenses",
    "income",
    "loan",
    "monthly",
    "money",
    "spend",
    "subscription",
    "budget",
}
_UTILITIES_KEYWORDS = {
    "bill",
    "bills",
    "contract",
    "electricity",
    "meter",
    "price",
    "tariff",
    "usage",
    "utility",
    "utilities",
    "renewal",
}
_OPERATIONS_KEYWORDS = {
    "attention",
    "baseline",
    "drift",
    "health",
    "homelab",
    "operations",
    "operating",
    "roi",
    "risk",
    "service",
    "storage",
    "backup",
    "workload",
}


def _normalize_tokens(question: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", question.lower()))


def _infer_domain(question: str, requested_domain: str) -> str:
    if requested_domain != "auto":
        return requested_domain
    tokens = _normalize_tokens(question)
    if tokens & _FINANCE_KEYWORDS:
        return "finance"
    if tokens & _UTILITIES_KEYWORDS:
        return "utilities"
    if tokens & _OPERATIONS_KEYWORDS:
        return "operations"
    return "finance"


def _publication_source(
    publication_index_by_key: dict[str, PublicationSemanticIndexEntry],
    publication_key: str,
    *,
    rationale: str,
    confidence_by_key: dict[str, PublicationConfidenceSnapshot] | None = None,
) -> AssistantSourceModel:
    entry = publication_index_by_key.get(publication_key)
    publication_display_name = publication_key
    summary = ""
    if entry is not None:
        publication_display_name = entry.publication.display_name
        summary = entry.summary
    confidence = (confidence_by_key or {}).get(publication_key)
    return AssistantSourceModel(
        publication_key=publication_key,
        publication_display_name=publication_display_name,
        publication_index_path=f"/contracts/publication-index/{publication_key}",
        report_path=_REPORT_PATH_BY_PUBLICATION_KEY.get(publication_key),
        summary=summary or f"{publication_display_name} publication contract.",
        rationale=rationale,
        confidence_verdict=str(confidence.confidence_verdict) if confidence is not None else None,
        freshness_state=str(confidence.freshness_state) if confidence is not None else None,
        assessed_at=confidence.assessed_at.isoformat() if confidence is not None else None,
    )


_STALE_VERDICTS = {"degraded", "unreliable", "unavailable"}


def _build_answer_confidence(sources: list[AssistantSourceModel]) -> AnswerConfidenceSummary | None:
    """Derive a worst-case confidence summary from the source list.

    Returns None when no source carries confidence data.
    """
    verdicts = [s.confidence_verdict for s in sources if s.confidence_verdict is not None]
    if not verdicts:
        return None

    _VERDICT_RANK = {"trustworthy": 0, "degraded": 1, "unreliable": 2, "unavailable": 3}
    worst = max(verdicts, key=lambda v: _VERDICT_RANK.get(v, 0))
    stale_count = sum(1 for v in verdicts if v in _STALE_VERDICTS)

    note: str | None = None
    if worst in _STALE_VERDICTS:
        note = (
            f"{stale_count} of {len(verdicts)} source(s) are not fully current; "
            "treat this answer as indicative rather than authoritative."
        )

    return AnswerConfidenceSummary(
        overall_verdict=worst,
        stale_source_count=stale_count,
        total_source_count=len(verdicts),
        note=note,
    )


def _first_non_empty_row(
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    return rows[0] if rows else None


def _last_non_empty_row(
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    return rows[-1] if rows else None


def _coerce_text(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, Decimal):
        return f"{value}"
    return str(value)


def _build_finance_answer(
    reporting_service: ReportingService,
    publication_index_by_key: dict[str, PublicationSemanticIndexEntry],
    to_jsonable: Callable[[Any], Any],
    confidence_by_key: dict[str, PublicationConfidenceSnapshot] | None = None,
) -> AssistantAnswerResponseModel:
    cashflow_rows = reporting_service.get_monthly_cashflow()
    spend_rows = reporting_service.get_spend_by_category_monthly()
    upcoming_rows = reporting_service.get_upcoming_fixed_costs_30d()

    answer_parts: list[str] = []
    latest_cashflow = _last_non_empty_row(cashflow_rows)
    if latest_cashflow is not None:
        answer_parts.append(
            "Latest monthly cashflow "
            f"({latest_cashflow.get('booking_month')}) shows income "
            f"{_coerce_text(latest_cashflow.get('income'))}, expense "
            f"{_coerce_text(latest_cashflow.get('expense'))}, and net "
            f"{_coerce_text(latest_cashflow.get('net'))}."
        )
    else:
        answer_parts.append("No monthly cashflow rows are available yet.")

    top_spend = _first_non_empty_row(spend_rows)
    if top_spend is not None:
        spend_label = top_spend.get("category") or top_spend.get("counterparty_name") or "uncategorized"
        answer_parts.append(
            f"Top spend bucket is {spend_label} in {top_spend.get('booking_month')} "
            f"at {_coerce_text(top_spend.get('total_expense'))}."
        )

    next_fixed_cost = _first_non_empty_row(upcoming_rows)
    if next_fixed_cost is not None:
        answer_parts.append(
            f"Upcoming fixed cost watchlist highlights {next_fixed_cost.get('contract_name')} "
            f"on {next_fixed_cost.get('expected_date')}."
        )

    evidence = {
        "monthly_cashflow": to_jsonable(cashflow_rows[:3]),
        "spend_by_category_monthly": to_jsonable(spend_rows[:3]),
        "upcoming_fixed_costs_30d": to_jsonable(upcoming_rows[:3]),
    }
    sources = [
        _publication_source(
            publication_index_by_key,
            "mart_monthly_cashflow",
            rationale="Primary monthly cashflow source for burn and income trend questions.",
            confidence_by_key=confidence_by_key,
        ),
        _publication_source(
            publication_index_by_key,
            "mart_spend_by_category_monthly",
            rationale="Secondary finance source for category and counterparty spend context.",
            confidence_by_key=confidence_by_key,
        ),
        _publication_source(
            publication_index_by_key,
            "mart_upcoming_fixed_costs_30d",
            rationale="Supplementary source for near-term recurring commitments.",
            confidence_by_key=confidence_by_key,
        ),
    ]
    return AssistantAnswerResponseModel(
        question="",
        requested_domain="finance",
        resolved_domain="finance",
        answer=" ".join(answer_parts),
        sources=sources,
        evidence=evidence,
        follow_up_questions=[
            "Ask about the largest spending category or upcoming fixed costs.",
            "Ask which counterparty drove the latest monthly cashflow change.",
        ],
        answer_confidence=_build_answer_confidence(sources),
    )


def _build_utilities_answer(
    reporting_service: ReportingService,
    publication_index_by_key: dict[str, PublicationSemanticIndexEntry],
    to_jsonable: Callable[[Any], Any],
    confidence_by_key: dict[str, PublicationConfidenceSnapshot] | None = None,
) -> AssistantAnswerResponseModel:
    utility_rows = reporting_service.get_utility_cost_summary()
    usage_vs_price_rows = reporting_service.get_usage_vs_price_summary()
    contract_price_rows = reporting_service.get_contract_price_current()
    electricity_price_rows = reporting_service.get_electricity_price_current()

    answer_parts: list[str] = []
    latest_utility = _last_non_empty_row(utility_rows)
    if latest_utility is not None:
        answer_parts.append(
            f"Latest utility cost summary for {latest_utility.get('meter_name')} "
            f"({latest_utility.get('period')}) is billed at "
            f"{_coerce_text(latest_utility.get('billed_amount'))} with unit cost "
            f"{_coerce_text(latest_utility.get('unit_cost'))}."
        )
    else:
        answer_parts.append("No utility cost summary rows are available yet.")

    top_usage_vs_price = _first_non_empty_row(usage_vs_price_rows)
    if top_usage_vs_price is not None:
        answer_parts.append(
            f"Usage-vs-price tracking for {top_usage_vs_price.get('utility_type')} "
            f"covers period {top_usage_vs_price.get('period')}."
        )

    top_contract_price = _first_non_empty_row(contract_price_rows)
    if top_contract_price is not None:
        answer_parts.append(
            f"Contract price watchlist includes {top_contract_price.get('contract_name')} "
            f"for {top_contract_price.get('contract_type')}."
        )

    top_electricity_price = _first_non_empty_row(electricity_price_rows)
    if top_electricity_price is not None:
        answer_parts.append(
            f"Electricity pricing highlights {top_electricity_price.get('contract_name')} "
            f"as the current tariff source."
        )

    evidence = {
        "utility_cost_summary": to_jsonable(utility_rows[:3]),
        "usage_vs_price_summary": to_jsonable(usage_vs_price_rows[:3]),
        "contract_price_current": to_jsonable(contract_price_rows[:3]),
        "electricity_price_current": to_jsonable(electricity_price_rows[:3]),
    }
    sources = [
        _publication_source(
            publication_index_by_key,
            "mart_utility_cost_summary",
            rationale="Primary utility summary source for current bills and coverage status.",
            confidence_by_key=confidence_by_key,
        ),
        _publication_source(
            publication_index_by_key,
            "mart_usage_vs_price_summary",
            rationale="Secondary utility source for usage and price context.",
            confidence_by_key=confidence_by_key,
        ),
        _publication_source(
            publication_index_by_key,
            "mart_contract_price_current",
            rationale="Supplementary price source for current contract pricing.",
            confidence_by_key=confidence_by_key,
        ),
        _publication_source(
            publication_index_by_key,
            "mart_electricity_price_current",
            rationale="Supplementary source for current electricity tariff pricing.",
            confidence_by_key=confidence_by_key,
        ),
    ]
    return AssistantAnswerResponseModel(
        question="",
        requested_domain="utilities",
        resolved_domain="utilities",
        answer=" ".join(answer_parts),
        sources=sources,
        evidence=evidence,
        follow_up_questions=[
            "Ask which meter drives the highest billed amount.",
            "Ask whether any contract or tariff is worth reviewing next.",
        ],
        answer_confidence=_build_answer_confidence(sources),
    )


def _build_operations_answer(
    reporting_service: ReportingService,
    publication_index_by_key: dict[str, PublicationSemanticIndexEntry],
    to_jsonable: Callable[[Any], Any],
    confidence_by_key: dict[str, PublicationConfidenceSnapshot] | None = None,
) -> AssistantAnswerResponseModel:
    attention_rows = reporting_service.get_open_attention_items()
    recent_changes_rows = reporting_service.get_recent_significant_changes()
    baseline_rows = reporting_service.get_current_operating_baseline()
    roi_rows = reporting_service.get_homelab_roi()

    answer_parts: list[str] = []
    if attention_rows:
        severities = [int(row.get("severity") or 0) for row in attention_rows]
        top_attention = max(
            attention_rows,
            key=lambda row: int(row.get("severity") or 0),
        )
        answer_parts.append(
            f"There are {len(attention_rows)} open attention items; the highest-severity item is "
            f"{top_attention.get('title')} (severity {max(severities)})."
        )
    else:
        answer_parts.append("No open attention items are available yet.")

    if recent_changes_rows:
        latest_change = _first_non_empty_row(recent_changes_rows)
        assert latest_change is not None
        answer_parts.append(
            f"Recent significant changes include {latest_change.get('change_type')} "
            f"for {latest_change.get('title')}."
        )

    if baseline_rows:
        baseline_types = ", ".join(sorted({str(row.get("baseline_type")) for row in baseline_rows}))
        answer_parts.append(f"Current operating baseline covers {baseline_types}.")

    if roi_rows:
        latest_roi = _first_non_empty_row(roi_rows)
        assert latest_roi is not None
        answer_parts.append(
            f"Homelab ROI snapshot is {latest_roi.get('roi_state')} with "
            f"{_coerce_text(latest_roi.get('healthy_service_count'))} healthy services "
            f"and {_coerce_text(latest_roi.get('tracked_workload_count'))} tracked workloads."
        )

    evidence = {
        "open_attention_items": to_jsonable(attention_rows[:3]),
        "recent_significant_changes": to_jsonable(recent_changes_rows[:3]),
        "current_operating_baseline": to_jsonable(baseline_rows[:3]),
        "homelab_roi": to_jsonable(roi_rows[:3]),
    }
    sources = [
        _publication_source(
            publication_index_by_key,
            "mart_open_attention_items",
            rationale="Primary operations source for current attention items and priorities.",
            confidence_by_key=confidence_by_key,
        ),
        _publication_source(
            publication_index_by_key,
            "mart_recent_significant_changes",
            rationale="Secondary operations source for recent change context.",
            confidence_by_key=confidence_by_key,
        ),
        _publication_source(
            publication_index_by_key,
            "mart_current_operating_baseline",
            rationale="Baseline source for the current operating picture.",
            confidence_by_key=confidence_by_key,
        ),
        _publication_source(
            publication_index_by_key,
            "mart_homelab_roi",
            rationale="Supplementary homelab operations source for cost and value context.",
            confidence_by_key=confidence_by_key,
        ),
    ]
    return AssistantAnswerResponseModel(
        question="",
        requested_domain="operations",
        resolved_domain="operations",
        answer=" ".join(answer_parts),
        sources=sources,
        evidence=evidence,
        follow_up_questions=[
            "Ask which open attention item is the highest priority.",
            "Ask for the latest operating change or ROI snapshot.",
        ],
        answer_confidence=_build_answer_confidence(sources),
    )


def register_assistant_routes(
    app: FastAPI,
    *,
    capability_packs: tuple[CapabilityPack, ...],
    extension_registry: ExtensionRegistry,
    resolved_reporting_service: ReportingService | None,
    to_jsonable: Callable[[Any], Any],
    control_plane: ControlPlaneStore | None = None,
) -> None:
    publication_contracts = build_publication_contracts(
        capability_packs,
        publication_relations=build_household_publication_relation_map(
            extension_registry=extension_registry,
        ),
        current_dimension_relations=(
            HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.current_dimension_relations
        ),
        current_dimension_contracts=(
            HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.current_dimension_contracts
        ),
    )
    ui_descriptors = build_ui_descriptor_contracts(capability_packs)
    publication_semantic_index = build_publication_semantic_index(
        publication_contracts,
        ui_descriptors,
    )
    publication_index_by_key = {
        entry.publication.publication_key: entry for entry in publication_semantic_index
    }

    def _svc() -> ReportingService:
        if resolved_reporting_service is not None:
            return resolved_reporting_service
        raise HTTPException(
            status_code=404,
            detail="Assistant answer surface requires a reporting service.",
        )

    def _fetch_confidence(publication_keys: list[str]) -> dict[str, PublicationConfidenceSnapshot]:
        if control_plane is None:
            return {}
        result: dict[str, PublicationConfidenceSnapshot] = {}
        try:
            for key in publication_keys:
                snapshot = get_latest_publication_confidence(key, control_plane)
                if snapshot is not None:
                    result[key] = snapshot
        except Exception:
            _log.debug("Confidence lookup unavailable (table may not be migrated yet)", exc_info=True)
            return {}
        return result

    _FINANCE_KEYS = [
        "mart_monthly_cashflow",
        "mart_spend_by_category_monthly",
        "mart_upcoming_fixed_costs_30d",
    ]
    _UTILITIES_KEYS = [
        "mart_utility_cost_summary",
        "mart_usage_vs_price_summary",
        "mart_contract_price_current",
        "mart_electricity_price_current",
    ]
    _OPERATIONS_KEYS = [
        "mart_open_attention_items",
        "mart_recent_significant_changes",
        "mart_current_operating_baseline",
        "mart_homelab_roi",
    ]

    @app.get("/api/assistant/answer", response_model=AssistantAnswerResponseModel)
    async def answer_assistant(
        question: str,
        domain: Literal["auto", "finance", "utilities", "operations"] = "auto",
    ) -> AssistantAnswerResponseModel:
        svc = _svc()
        resolved_domain = _infer_domain(question, domain)
        if resolved_domain == "finance":
            confidence_by_key = _fetch_confidence(_FINANCE_KEYS)
            response = _build_finance_answer(
                svc,
                publication_index_by_key,
                to_jsonable,
                confidence_by_key=confidence_by_key,
            )
        elif resolved_domain == "utilities":
            confidence_by_key = _fetch_confidence(_UTILITIES_KEYS)
            response = _build_utilities_answer(
                svc,
                publication_index_by_key,
                to_jsonable,
                confidence_by_key=confidence_by_key,
            )
        else:
            confidence_by_key = _fetch_confidence(_OPERATIONS_KEYS)
            response = _build_operations_answer(
                svc,
                publication_index_by_key,
                to_jsonable,
                confidence_by_key=confidence_by_key,
            )
        return AssistantAnswerResponseModel(
            question=question,
            requested_domain=domain,
            resolved_domain=resolved_domain,
            answer=response.answer,
            sources=response.sources,
            evidence=response.evidence,
            follow_up_questions=response.follow_up_questions,
            answer_confidence=response.answer_confidence,
        )
