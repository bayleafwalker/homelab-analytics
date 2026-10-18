"""Morning brief API (Kotona Stage B1).

- ``GET /api/briefing`` — deterministic morning brief composed from
  reporting publications, policy verdicts, source freshness and publication
  confidence. No LLM is involved; see
  ``packages/application/use_cases/morning_brief.py`` for the honesty
  contract and the section extension point.

The route only gathers inputs (reporting layer, control plane, policy
engine) and delegates composition to the use-case.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Callable, Mapping, Sequence

from fastapi import FastAPI

from apps.api.response_models import MorningBriefResponseModel
from packages.application.use_cases.morning_brief import (
    BriefSectionRegistry,
    compose_morning_brief,
    gather_brief_inputs,
)
from packages.application.use_cases.morning_brief_sections import (
    ATTENTION_ITEMS_KEY,
    BATTERY_PLAN_OUTCOME_KEY,
    MONTHLY_CASHFLOW_KEY,
    RECENT_CHANGES_KEY,
    UPCOMING_FIXED_COSTS_KEY,
    default_brief_section_registry,
)
from packages.application.use_cases.source_freshness_overview import (
    build_source_freshness_views,
)
from packages.pipelines.reporting_service import ReportingService

_log = logging.getLogger(__name__)


class ReportingPublicationReader:
    """Reads brief publications through the reporting layer only.

    Extension point: a new brief section that reads another publication adds
    its ``publication_key → ReportingService`` accessor here (or passes a
    reader with ``extra_readers``). Keys without an accessor raise
    ``KeyError`` and the section is withheld rather than invented.
    """

    def __init__(
        self,
        reporting_service: ReportingService,
        extra_readers: Mapping[str, Callable[[ReportingService], Sequence[Mapping[str, Any]]]]
        | None = None,
    ) -> None:
        self._reporting_service = reporting_service
        self._readers: dict[str, Callable[[ReportingService], Sequence[Mapping[str, Any]]]] = {
            MONTHLY_CASHFLOW_KEY: lambda svc: svc.get_monthly_cashflow(),
            ATTENTION_ITEMS_KEY: lambda svc: svc.get_open_attention_items(),
            RECENT_CHANGES_KEY: lambda svc: svc.get_recent_significant_changes(),
            UPCOMING_FIXED_COSTS_KEY: lambda svc: svc.get_upcoming_fixed_costs_30d(),
            BATTERY_PLAN_OUTCOME_KEY: lambda svc: svc.get_battery_plan_outcome(),
        }
        if extra_readers:
            self._readers.update(extra_readers)

    def read_publication(self, publication_key: str) -> Sequence[Mapping[str, Any]]:
        reader = self._readers.get(publication_key)
        if reader is None:
            raise KeyError(f"No brief reader for publication {publication_key!r}")
        return reader(self._reporting_service)


def register_briefing_routes(
    app: FastAPI,
    *,
    resolved_reporting_service: ReportingService | None,
    control_plane: Any,
    metadata_repository: Any,
    ha_policy_evaluator: Any = None,
    blob_store: Any = None,
    section_registry: BriefSectionRegistry | None = None,
    clock: Callable[[], datetime] | None = None,
) -> None:
    """Register the morning brief route."""

    registry = section_registry or default_brief_section_registry()
    now_fn = clock or (lambda: datetime.now(UTC))
    reader = (
        ReportingPublicationReader(resolved_reporting_service)
        if resolved_reporting_service is not None
        else None
    )

    def _policy_inputs() -> tuple[list[dict[str, Any]] | None, str | None]:
        if ha_policy_evaluator is None:
            return None, None
        try:
            results = [result.to_dict() for result in ha_policy_evaluator.evaluate()]
        except Exception:
            _log.warning("Policy evaluation failed for the morning brief", exc_info=True)
            return None, None
        mode: str | None = None
        get_authority = getattr(ha_policy_evaluator, "get_authority_status", None)
        if get_authority is not None:
            try:
                mode = get_authority().to_dict().get("mode")
            except Exception:
                mode = None
        return results, mode

    def _source_views(as_of: Any) -> list[Any] | None:
        if control_plane is None or metadata_repository is None:
            return None
        try:
            return build_source_freshness_views(
                control_plane, metadata_repository, as_of=as_of, blob_store=blob_store
            )
        except Exception:
            _log.warning("Source freshness unavailable for the morning brief", exc_info=True)
            return None

    @app.get("/api/briefing", response_model=MorningBriefResponseModel)
    async def get_briefing() -> dict[str, Any]:
        generated_at = now_fn()
        as_of = generated_at.date()
        policy_results, authority_mode = _policy_inputs()
        inputs = gather_brief_inputs(
            as_of=as_of,
            generated_at=generated_at,
            registry=registry,
            reader=reader,
            confidence_store=control_plane,
            policy_results=policy_results,
            policy_authority_mode=authority_mode,
            source_views=_source_views(as_of),
        )
        return compose_morning_brief(inputs, registry).as_dict()
