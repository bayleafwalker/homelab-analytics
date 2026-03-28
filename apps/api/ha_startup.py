from __future__ import annotations

from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from packages.platform.capability_types import CapabilityPack
from packages.pipelines.ha_action_proposals import ApprovalActionRegistry
from packages.pipelines.ha_policy import HaPolicyEvaluator
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.settings import AppSettings


@dataclass(frozen=True)
class HaStartupRuntime:
    bridge: Any | None
    policy_evaluator: HaPolicyEvaluator
    action_proposal_registry: ApprovalActionRegistry
    action_dispatcher: Any | None
    mqtt_publisher: Any | None


def _format_decimal(value: Decimal, *, precision: str = "0.01") -> str:
    quantized = value.quantize(Decimal(precision))
    normalized = format(quantized, "f").rstrip("0").rstrip(".")
    return normalized or "0"


def _decimal_from_value(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _compute_peak_tariff_active(
    electricity_rows: list[dict],
    *,
    now: datetime | None = None,
) -> str:
    if not electricity_rows:
        return "unavailable"
    current = (now or datetime.now()).astimezone()
    if current.weekday() >= 5:
        return "off_peak"
    return "peak" if 7 <= current.hour < 22 else "off_peak"


def _compute_electricity_cost_forecast_today(
    reporting_service: ReportingService,
    *,
    now: datetime | None = None,
) -> str:
    current = (now or datetime.now()).astimezone()
    try:
        day_rows = reporting_service.get_utility_cost_summary(
            utility_type="electricity",
            granularity="day",
        )
    except Exception:
        day_rows = []

    period_rows = [
        row
        for row in day_rows
        if row.get("period_day") or row.get("period_start") or row.get("period")
    ]
    if period_rows:
        latest_period = max(
            str(
                row.get("period_day") or row.get("period_start") or row.get("period")
            )
            for row in period_rows
        )
        latest_total = Decimal("0")
        for row in period_rows:
            period_value = str(
                row.get("period_day") or row.get("period_start") or row.get("period")
            )
            if period_value == latest_period:
                latest_total += _decimal_from_value(row.get("billed_amount"))
        return _format_decimal(latest_total)

    try:
        trend_rows = reporting_service.get_utility_cost_trend_monthly(
            utility_type="electricity"
        )
    except Exception:
        trend_rows = []

    if not trend_rows:
        return "unavailable"

    latest_row = max(trend_rows, key=lambda row: str(row.get("billing_month") or ""))
    total_cost = _decimal_from_value(latest_row.get("total_cost"))
    days_in_month = monthrange(current.year, current.month)[1]
    if days_in_month <= 0:
        return "unavailable"
    forecast = total_cost / Decimal(days_in_month)
    return _format_decimal(cast(Decimal, forecast))


def _compute_maintenance_state(reporting_service: ReportingService) -> tuple[str, str]:
    try:
        service_rows = reporting_service.get_service_health_current()
    except Exception:
        service_rows = []
    try:
        storage_rows = reporting_service.get_storage_risk()
    except Exception:
        storage_rows = []

    issue_count = sum(
        1
        for row in service_rows
        if str(row.get("state") or "").lower() in {"degraded", "stopped"}
    ) + sum(
        1
        for row in storage_rows
        if str(row.get("risk_tier") or "").lower() in {"warn", "crit"}
    )
    return ("on" if issue_count > 0 else "off"), str(issue_count)


def _compute_contract_renewal_due_count(reporting_service: ReportingService) -> str:
    try:
        return str(len(reporting_service.get_contract_renewal_watchlist()))
    except Exception:
        return "unavailable"


def build_ha_startup_runtime(
    settings: AppSettings,
    *,
    transformation_service: TransformationService,
    reporting_service: ReportingService,
    capability_packs: Sequence[CapabilityPack],
) -> HaStartupRuntime:
    from packages.pipelines.ha_action_dispatcher import HaActionDispatcher
    from packages.pipelines.ha_bridge import HaBridgeWorker
    from packages.pipelines.ha_contract_renderer import HaContractRenderer
    from packages.pipelines.ha_mqtt_publisher import HaMqttPublisher

    ha_bridge = None
    if settings.ha_url and settings.ha_token:
        ha_bridge = HaBridgeWorker(
            transformation_service.ingest_ha_states,
            ha_url=settings.ha_url,
            ha_token=settings.ha_token,
        )

    def _policy_fetch_fn() -> dict:
        if ha_bridge is not None:
            bridge_status = ha_bridge.get_status()
            bridge_last_sync_at = bridge_status.get("last_sync_at")
            bridge_connected = bridge_status.get("connected", False)
        else:
            bridge_last_sync_at = None
            bridge_connected = False
        try:
            budget_rows = transformation_service.get_budget_progress_current()
        except Exception:
            budget_rows = []
        try:
            ha_entities = transformation_service.get_ha_entities()
        except Exception:
            ha_entities = []
        return {
            "bridge_connected": bridge_connected,
            "bridge_last_sync_at": bridge_last_sync_at,
            "budget_rows": budget_rows,
            "ha_entities": ha_entities,
        }

    ha_policy_evaluator = HaPolicyEvaluator(_policy_fetch_fn)
    ha_action_proposal_registry = ApprovalActionRegistry()

    ha_action_dispatcher = None
    if settings.ha_url and settings.ha_token:
        ha_action_dispatcher = HaActionDispatcher(
            ha_url=settings.ha_url,
            ha_token=settings.ha_token,
            evaluator=ha_policy_evaluator,
            proposal_registry=ha_action_proposal_registry,
        )

    ha_mqtt_publisher = None
    if settings.ha_mqtt_broker_url:
        ha_contract_renderer = HaContractRenderer(
            reporting_service,
            capability_packs=capability_packs,
        )

        def _mqtt_fetch_fn() -> dict:
            if ha_bridge is None:
                bridge_status = {
                    "connected": False,
                    "last_sync_at": None,
                    "reconnect_count": 0,
                }
            else:
                bridge_status = ha_bridge.get_status()
            if ha_action_dispatcher is None:
                approval_status = {
                    "approval_tracked_count": 0,
                    "approval_pending_count": 0,
                }
            else:
                approval_status = ha_action_dispatcher.get_status()
            platform_state: dict = {
                "bridge_connected": bridge_status["connected"],
                "bridge_last_sync_at": bridge_status["last_sync_at"],
                "bridge_reconnect_count": bridge_status["reconnect_count"],
                "approval_tracked_count": approval_status["approval_tracked_count"],
                "approval_pending_count": approval_status["approval_pending_count"],
            }
            try:
                electricity_rows = reporting_service.get_electricity_price_current()
            except Exception:
                electricity_rows = []
            platform_state["peak_tariff_active"] = _compute_peak_tariff_active(
                electricity_rows
            )

            platform_state["electricity_cost_forecast_today"] = (
                _compute_electricity_cost_forecast_today(reporting_service)
            )
            maintenance_due, maintenance_issue_count = _compute_maintenance_state(
                reporting_service
            )
            platform_state["maintenance_due"] = maintenance_due
            platform_state["maintenance_issue_count"] = maintenance_issue_count
            platform_state["contract_renewal_due_count"] = (
                _compute_contract_renewal_due_count(reporting_service)
            )
            for result in ha_policy_evaluator.evaluate():
                platform_state[f"policy_{result.id}"] = result.verdict
            platform_state.update(ha_contract_renderer.render_states())
            return platform_state

        ha_mqtt_publisher = HaMqttPublisher(
            _mqtt_fetch_fn,
            broker_url=settings.ha_mqtt_broker_url,
            username=settings.ha_mqtt_username,
            password=settings.ha_mqtt_password,
            action_dispatcher=ha_action_dispatcher,
            entities=ha_contract_renderer.entity_definitions(),
        )

    return HaStartupRuntime(
        bridge=ha_bridge,
        policy_evaluator=ha_policy_evaluator,
        action_proposal_registry=ha_action_proposal_registry,
        action_dispatcher=ha_action_dispatcher,
        mqtt_publisher=ha_mqtt_publisher,
    )
