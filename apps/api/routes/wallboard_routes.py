"""Wallboard kiosk API: four read-only panels for /wallboard.

  GET /api/wallboard/services  → service health (reporting marts)
  GET /api/wallboard/devices   → per-room readings (HA bridge entities)
  GET /api/wallboard/events    → ingestion runs + action proposals + HA alerts
  GET /api/wallboard/power     → hourly kWh for one energy meter (HA historian)

Every panel says whether its source is wired (``available``) so the board can
show "not connected" instead of an empty list that looks like "all quiet".
Composition lives in ``packages.application.use_cases.wallboard``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from packages.application.use_cases.wallboard import (
    DEFAULT_EVENT_WINDOW,
    DEFAULT_POWER_WINDOW_HOURS,
    MAX_EVENTS,
    MAX_INTERPOLATION_GAP,
    build_device_readings,
    build_event_feed,
    build_power_series,
    build_service_health,
    energy_meter_candidates,
    power_window_start,
    select_energy_meter,
    to_utc,
)
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService

logger = logging.getLogger(__name__)


class WallboardServiceModel(BaseModel):
    service_id: str
    name: str
    host: str | None = None
    status: Literal["up", "degraded", "down", "unknown"]
    state: str | None = None
    criticality: str | None = None
    uptime_seconds: int | None = None
    cpu_pct: float | None = None
    mem_gb: float | None = None
    metrics_window: str | None = None
    recorded_at: str | None = None
    stale: bool


class WallboardServicesModel(BaseModel):
    available: bool
    generated_at: str
    services: list[WallboardServiceModel]


class WallboardRoomModel(BaseModel):
    room: str | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    power_w: float | None = None
    sensor_count: int
    last_seen: str | None = None


class WallboardDevicesModel(BaseModel):
    available: bool
    generated_at: str
    rooms: list[WallboardRoomModel]


class WallboardEventModel(BaseModel):
    event_id: str
    kind: Literal["ingestion", "proposal", "alert"]
    at: str
    title: str
    detail: str | None = None
    tone: Literal["ok", "warn", "accent", "neutral"]


class WallboardEventSourcesModel(BaseModel):
    runs: bool
    proposals: bool
    alerts: bool


class WallboardEventFeedModel(BaseModel):
    since: str
    generated_at: str
    sources: WallboardEventSourcesModel
    events: list[WallboardEventModel]


class WallboardPowerBucketModel(BaseModel):
    hour_start: str
    hour_end: str
    kwh: float | None = None
    partial: bool


class WallboardPowerMeterModel(BaseModel):
    entity_id: str
    name: str | None = None
    unit: str | None = None


class WallboardPowerSeriesModel(BaseModel):
    available: bool
    status: Literal["ok", "no_meter", "ambiguous", "unavailable"]
    window_hours: int
    unit: Literal["kWh"] = "kWh"
    generated_at: str
    meter: WallboardPowerMeterModel | None = None
    candidates: list[WallboardPowerMeterModel]
    total_kwh: float | None = None
    buckets: list[WallboardPowerBucketModel]


def _meter_model(entity: Any) -> WallboardPowerMeterModel:
    return WallboardPowerMeterModel(
        entity_id=str(entity.get("entity_id")),
        name=entity.get("friendly_name"),
        unit=entity.get("unit"),
    )


def register_wallboard_routes(
    app: FastAPI,
    *,
    transformation_service: TransformationService | None,
    resolved_reporting_service: ReportingService | None,
    run_metadata_repository: Any | None,
    action_proposal_registry: Any | None,
    ha_action_dispatcher: Any | None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    def _reporting() -> ReportingService | None:
        if resolved_reporting_service is not None:
            return resolved_reporting_service
        if transformation_service is not None:
            return ReportingService(transformation_service)
        return None

    def _ha_reporting() -> Any | None:
        reporting = _reporting()
        if reporting is None or not hasattr(reporting, "get_ha_entities"):
            return None
        return reporting

    @app.get("/api/wallboard/services", response_model=WallboardServicesModel)
    async def get_wallboard_services() -> WallboardServicesModel:
        current = now()
        reporting = _reporting()
        if reporting is None:
            return WallboardServicesModel(
                available=False, generated_at=current.isoformat(), services=[]
            )
        rows = build_service_health(
            reporting.get_service_health_current(),
            reporting.get_workload_cost_7d(),
            now=current,
        )
        return WallboardServicesModel(
            available=True,
            generated_at=current.isoformat(),
            services=[WallboardServiceModel.model_validate(row) for row in rows],
        )

    @app.get("/api/wallboard/devices", response_model=WallboardDevicesModel)
    async def get_wallboard_devices() -> WallboardDevicesModel:
        current = now()
        reporting = _ha_reporting()
        if reporting is None:
            return WallboardDevicesModel(
                available=False, generated_at=current.isoformat(), rooms=[]
            )
        rooms = build_device_readings(reporting.get_ha_entities())
        return WallboardDevicesModel(
            available=True,
            generated_at=current.isoformat(),
            rooms=[WallboardRoomModel.model_validate(room) for room in rooms],
        )

    @app.get("/api/wallboard/events", response_model=WallboardEventFeedModel)
    async def get_wallboard_events(
        since: str | None = Query(
            default=None,
            description="ISO-8601 lower bound; defaults to 12 hours ago.",
        ),
    ) -> WallboardEventFeedModel:
        current = now()
        if since is None:
            since_at = current - DEFAULT_EVENT_WINDOW
        else:
            parsed = to_utc(since)
            if parsed is None:
                raise HTTPException(status_code=400, detail="since must be an ISO-8601 timestamp.")
            since_at = parsed

        runs: list[Any] = []
        if run_metadata_repository is not None:
            runs = run_metadata_repository.list_runs(from_date=since_at, limit=MAX_EVENTS)
        proposals: list[dict[str, Any]] = []
        if action_proposal_registry is not None:
            proposals = [proposal.to_dict() for proposal in action_proposal_registry.list_all()]
        alerts: list[dict[str, Any]] = []
        if ha_action_dispatcher is not None:
            alerts = ha_action_dispatcher.get_actions(limit=MAX_EVENTS)

        events = build_event_feed(
            runs=runs, proposals=proposals, alerts=alerts, since=since_at
        )
        return WallboardEventFeedModel(
            since=since_at.isoformat(),
            generated_at=current.isoformat(),
            sources=WallboardEventSourcesModel(
                runs=run_metadata_repository is not None,
                proposals=action_proposal_registry is not None,
                alerts=ha_action_dispatcher is not None,
            ),
            events=[WallboardEventModel.model_validate(event) for event in events],
        )

    @app.get("/api/wallboard/power", response_model=WallboardPowerSeriesModel)
    async def get_wallboard_power(
        window_hours: int = Query(default=DEFAULT_POWER_WINDOW_HOURS, ge=1, le=168),
        entity_id: str | None = Query(
            default=None,
            description="Energy meter entity; defaults to the house meter when it is unambiguous.",
        ),
    ) -> WallboardPowerSeriesModel:
        current = now()
        empty_buckets = build_power_series([], unit=None, now=current, window_hours=window_hours)
        reporting = _ha_reporting()
        if reporting is None or not hasattr(reporting, "get_ha_state_changes_since"):
            return WallboardPowerSeriesModel(
                available=False,
                status="unavailable",
                window_hours=window_hours,
                generated_at=current.isoformat(),
                candidates=[],
                buckets=[WallboardPowerBucketModel.model_validate(b) for b in empty_buckets],
            )
        candidates = energy_meter_candidates(reporting.get_ha_entities())
        meter, status = select_energy_meter(candidates, entity_id=entity_id)
        buckets = empty_buckets
        if meter is not None:
            since = power_window_start(current, window_hours) - MAX_INTERPOLATION_GAP
            readings = reporting.get_ha_state_changes_since(
                [str(meter.get("entity_id"))], since=since
            )
            buckets = build_power_series(
                readings, unit=meter.get("unit"), now=current, window_hours=window_hours
            )
        known = [bucket["kwh"] for bucket in buckets if bucket["kwh"] is not None]
        return WallboardPowerSeriesModel(
            available=True,
            status=status,  # type: ignore[arg-type]
            window_hours=window_hours,
            generated_at=current.isoformat(),
            meter=_meter_model(meter) if meter is not None else None,
            candidates=[_meter_model(candidate) for candidate in candidates],
            total_kwh=round(sum(known), 3) if known else None,
            buckets=[WallboardPowerBucketModel.model_validate(b) for b in buckets],
        )
