"""Wallboard read models: service health, room readings, event feed, power.

The /wallboard kiosk shows four live panels. Each is composed here from data
the platform already publishes or already keeps in a control-plane store:

- services: ``mart_service_health_current`` joined to ``mart_workload_cost_7d``
  for CPU/memory (reporting layer);
- devices: current HA bridge entities (``dim_ha_entity``) grouped by area;
- events: ingestion run metadata, the action-proposal queue and the HA
  dispatcher's alert log;
- power: the HA bridge historian for one cumulative energy meter, bucketed
  into hours of the household clock (``HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE``).

Nothing here reads landing payloads. Where a value is not known it stays
``None`` so the UI can say "unknown" rather than draw a zero.

All timestamps are normalised to aware UTC before comparison; the household
zone only decides where power-bucket boundaries fall and how they are labelled.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal
from zoneinfo import ZoneInfo

ServiceStatus = Literal["up", "degraded", "down", "unknown"]
EventKind = Literal["ingestion", "proposal", "alert"]
EventTone = Literal["ok", "warn", "accent", "neutral"]

SERVICE_STALE_AFTER = timedelta(hours=1)
DEFAULT_EVENT_WINDOW = timedelta(hours=12)
MAX_EVENTS = 100
DEFAULT_POWER_WINDOW_HOURS = 24
# A historian gap longer than this is not interpolated: the hours it spans
# are reported as unknown instead of being given an invented share.
MAX_INTERPOLATION_GAP = timedelta(hours=2)

_UP_STATES = frozenset({"running", "up", "ok", "healthy", "online", "on"})
_DEGRADED_STATES = frozenset({"degraded", "warning", "warn", "starting", "restarting"})
_DOWN_STATES = frozenset(
    {"stopped", "down", "failed", "error", "exited", "offline", "off", "dead", "crashed"}
)
_METER_PREFERENCE_TOKENS = ("grid", "main", "total", "house", "home")
_ENERGY_UNIT_FACTORS = {"wh": Decimal("0.001"), "kwh": Decimal("1"), "mwh": Decimal("1000")}
_POWER_UNIT_FACTORS = {"w": Decimal("1"), "kw": Decimal("1000")}
_TEMPERATURE_UNITS = frozenset({"°c", "c", "°f", "f"})


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def to_utc(value: Any) -> datetime | None:
    """Parse ``value`` into an aware UTC datetime; naive values are UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _float(value: Decimal | None, places: int) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def normalize_service_status(state: Any) -> ServiceStatus:
    text = str(state or "").strip().lower()
    if text in _UP_STATES:
        return "up"
    if text in _DEGRADED_STATES:
        return "degraded"
    if text in _DOWN_STATES:
        return "down"
    return "unknown"


def _match_workload(
    service: Mapping[str, Any],
    workloads: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    service_id = _text(service.get("service_id"))
    for workload in workloads:
        if service_id and _text(workload.get("workload_id")) == service_id:
            return workload
    name = (_text(service.get("service_name")) or "").lower()
    host = _text(service.get("host"))
    if not name:
        return None
    for workload in workloads:
        if (_text(workload.get("display_name")) or "").lower() != name:
            continue
        workload_host = _text(workload.get("host"))
        if host is None or workload_host is None or workload_host == host:
            return workload
    return None


def build_service_health(
    service_rows: Iterable[Mapping[str, Any]],
    workload_rows: Iterable[Mapping[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """One row per service: name, host, status, uptime and CPU/memory.

    CPU and memory are 7-day averages from the workload mart, attached only
    when a workload matches the service by id, or by name on the same host.
    Unmatched services keep ``None``. A reading older than
    ``SERVICE_STALE_AFTER`` is flagged ``stale`` so the board does not show a
    week-old "up" as current.
    """
    now_utc = to_utc(now) or datetime.now(UTC)
    workloads = list(workload_rows)
    rows: list[dict[str, Any]] = []
    for service in service_rows:
        recorded_at = to_utc(service.get("recorded_at"))
        workload = _match_workload(service, workloads)
        uptime = _number(service.get("uptime_seconds"))
        rows.append(
            {
                "service_id": str(service.get("service_id") or ""),
                "name": _text(service.get("service_name"))
                or str(service.get("service_id") or ""),
                "host": _text(service.get("host")),
                "status": normalize_service_status(service.get("state")),
                "state": _text(service.get("state")),
                "criticality": _text(service.get("criticality")),
                "uptime_seconds": int(uptime) if uptime is not None else None,
                "cpu_pct": _float(_number(workload.get("avg_cpu_pct_7d")), 2)
                if workload
                else None,
                "mem_gb": _float(_number(workload.get("avg_mem_gb_7d")), 3)
                if workload
                else None,
                "metrics_window": "7d_avg" if workload else None,
                "recorded_at": _iso(recorded_at),
                "stale": recorded_at is None or now_utc - recorded_at > SERVICE_STALE_AFTER,
            }
        )
    order = {"down": 0, "degraded": 1, "unknown": 2, "up": 3}
    rows.sort(key=lambda row: (order[row["status"]], row["name"].lower()))
    return rows


# ---------------------------------------------------------------------------
# Devices (per-room readings)
# ---------------------------------------------------------------------------


def _measure_for(entity: Mapping[str, Any]) -> str | None:
    if str(entity.get("entity_class") or "") != "sensor":
        return None
    entity_id = str(entity.get("entity_id") or "").lower()
    name = str(entity.get("friendly_name") or "").lower()
    unit = str(entity.get("unit") or "").strip().lower()
    if unit in _POWER_UNIT_FACTORS:
        return "power"
    if unit in _TEMPERATURE_UNITS or (
        "temperature" in entity_id and unit in ("", *_TEMPERATURE_UNITS)
    ):
        return "temperature"
    if unit == "%" and ("humidity" in entity_id or "humidity" in name):
        return "humidity"
    return None


def _celsius(value: Decimal, unit: str) -> Decimal:
    if unit in ("°f", "f"):
        return (value - Decimal(32)) * Decimal(5) / Decimal(9)
    return value


def build_device_readings(entity_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Group current HA sensor states into per-room readings.

    Temperature (°C) and humidity (%) average the room's sensors; power (W)
    sums them. A room with a sensor whose state is not numeric (for example
    ``unavailable``) still appears, with that measure ``None``. Sensors with
    no HA area are grouped under ``room=None``.
    """
    rooms: dict[str | None, dict[str, Any]] = {}
    for entity in entity_rows:
        measure = _measure_for(entity)
        if measure is None:
            continue
        room_key = _text(entity.get("area"))
        room = rooms.setdefault(
            room_key,
            {"values": {"temperature": [], "humidity": [], "power": []}, "seen": [], "count": 0},
        )
        room["count"] += 1
        seen = to_utc(entity.get("last_seen"))
        if seen is not None:
            room["seen"].append(seen)
        value = _number(entity.get("last_state"))
        if value is None:
            continue
        unit = str(entity.get("unit") or "").strip().lower()
        if measure == "temperature":
            value = _celsius(value, unit)
        elif measure == "power":
            value = value * _POWER_UNIT_FACTORS[unit]
        room["values"][measure].append(value)

    result: list[dict[str, Any]] = []
    for room_key, room in rooms.items():
        values = room["values"]

        def mean(items: list[Decimal]) -> Decimal | None:
            return sum(items, Decimal(0)) / len(items) if items else None

        result.append(
            {
                "room": room_key,
                "temperature_c": _float(mean(values["temperature"]), 1),
                "humidity_pct": _float(mean(values["humidity"]), 0),
                "power_w": _float(sum(values["power"], Decimal(0)), 0)
                if values["power"]
                else None,
                "sensor_count": room["count"],
                "last_seen": _iso(max(room["seen"])) if room["seen"] else None,
            }
        )
    result.sort(key=lambda row: (row["room"] is None, (row["room"] or "").lower()))
    return result


# ---------------------------------------------------------------------------
# Event feed
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WallboardEvent:
    event_id: str
    kind: EventKind
    at: datetime
    title: str
    detail: str | None
    tone: EventTone

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "at": self.at.isoformat(),
            "title": self.title,
            "detail": self.detail,
            "tone": self.tone,
        }


def _run_events(runs: Iterable[Any]) -> list[WallboardEvent]:
    events: list[WallboardEvent] = []
    for run in runs:
        at = to_utc(getattr(run, "created_at", None))
        if at is None:
            continue
        status = str(getattr(getattr(run, "status", None), "value", getattr(run, "status", "")))
        dataset = str(getattr(run, "dataset_name", "") or "dataset")
        source = _text(getattr(run, "source_name", None))
        rows = getattr(run, "row_count", None)
        if status == "landed":
            title, tone = f"Ingested {dataset}", "ok"
        elif status in ("rejected", "failed"):
            title, tone = f"Ingestion {status}: {dataset}", "warn"
        else:
            title, tone = f"Ingestion {status or 'received'}: {dataset}", "neutral"
        parts = []
        if rows is not None:
            parts.append(f"{rows} rows")
        if source:
            parts.append(f"from {source}")
        events.append(
            WallboardEvent(
                event_id=f"run:{getattr(run, 'run_id', '')}",
                kind="ingestion",
                at=at,
                title=title,
                detail=" ".join(parts) or None,
                tone=tone,  # type: ignore[arg-type]
            )
        )
    return events


# Proposal history kinds (packages/platform/action_proposals.py) as feed
# lines. ``refreshed`` is a re-evaluation with no state change, so it is left
# out of an ambient feed.
_PROPOSAL_HISTORY_LINES: dict[str, tuple[str, EventTone]] = {
    "drafted": ("Proposed", "accent"),
    "reopened": ("Reopened", "accent"),
    "approved": ("Approved", "ok"),
    "dismissed": ("Dismissed", "neutral"),
    "release_failed": ("Release failed", "warn"),
}


def _proposal_events(proposals: Iterable[Mapping[str, Any]]) -> list[WallboardEvent]:
    """One event per proposal lifecycle step.

    Read from the proposal's append-only ``history``: the current snapshot
    loses steps (a failed HA release reverts an approval to pending and clears
    ``approved_at``). Proposals without history fall back to the snapshot
    timestamps.
    """
    events: list[WallboardEvent] = []
    for proposal in proposals:
        action_id = str(proposal.get("action_id") or "")
        name = _text(proposal.get("policy_name")) or _text(proposal.get("policy_id")) or "action"
        summary = _text(proposal.get("source_summary")) or _text(proposal.get("verdict"))
        history = [entry for entry in proposal.get("history") or [] if isinstance(entry, Mapping)]
        if not history:
            history = [
                {"kind": kind, "at": proposal.get(field), "actor": None, "reason": None}
                for kind, field in (
                    ("drafted", "created_at"),
                    ("approved", "approved_at"),
                    ("dismissed", "dismissed_at"),
                )
                if proposal.get(field)
            ]
        for index, entry in enumerate(history):
            kind = str(entry.get("kind") or "")
            line = _PROPOSAL_HISTORY_LINES.get(kind)
            at = to_utc(entry.get("at"))
            if line is None or at is None:
                continue
            verb, tone = line
            if kind == "drafted":
                detail = summary
            elif kind == "release_failed":
                detail = _text(entry.get("reason")) or "the approval was returned to pending"
            else:
                detail = _text(entry.get("reason")) or _text(entry.get("actor"))
            events.append(
                WallboardEvent(
                    event_id=f"proposal:{action_id}:{index}:{kind}",
                    kind="proposal",
                    at=at,
                    title=f"{verb}: {name}",
                    detail=detail,
                    tone=tone,
                )
            )
    return events


def _alert_events(actions: Iterable[Mapping[str, Any]]) -> list[WallboardEvent]:
    events: list[WallboardEvent] = []
    for index, action in enumerate(actions):
        if action.get("action_class") != "alert":
            continue
        at = to_utc(action.get("timestamp"))
        if at is None:
            continue
        name = _text(action.get("policy_name")) or _text(action.get("policy_id")) or "policy"
        verdict = _text(action.get("verdict"))
        dismissed = "dismiss" in str(action.get("action_type") or "")
        failed = action.get("result") == "failure"
        detail = f"delivery failed: {action.get('error')}" if failed else None
        events.append(
            WallboardEvent(
                event_id=f"alert:{action.get('policy_id')}:{at.isoformat()}:{index}",
                kind="alert",
                at=at,
                title=(
                    f"Cleared: {name}"
                    if dismissed
                    else f"Alert: {name}" + (f" ({verdict})" if verdict else "")
                ),
                detail=detail,
                tone="ok" if dismissed and not failed else "warn",
            )
        )
    return events


def build_event_feed(
    *,
    runs: Iterable[Any],
    proposals: Iterable[Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
    since: datetime,
    limit: int = MAX_EVENTS,
) -> list[dict[str, Any]]:
    """Merge the three sources into one newest-first timeline from ``since``."""
    since_utc = to_utc(since) or since
    events = [
        *_run_events(runs),
        *_proposal_events(proposals),
        *_alert_events(alerts),
    ]
    events = [event for event in events if event.at >= since_utc]
    events.sort(key=lambda event: (event.at, event.event_id), reverse=True)
    return [event.to_dict() for event in events[:limit]]


# ---------------------------------------------------------------------------
# Power series
# ---------------------------------------------------------------------------


def energy_meter_candidates(entity_rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        entity
        for entity in entity_rows
        if str(entity.get("entity_class") or "") == "sensor"
        and str(entity.get("unit") or "").strip().lower() in _ENERGY_UNIT_FACTORS
    ]


def select_energy_meter(
    candidates: Sequence[Mapping[str, Any]],
    *,
    entity_id: str | None = None,
) -> tuple[Mapping[str, Any] | None, str]:
    """Pick the meter to chart. Returns (meter, status).

    Summing several meters could double count (a whole-house meter plus a
    plug on the same circuit), so exactly one is used: the requested one, the
    only one, or the only one whose id/name says grid/main/total/house/home.
    Otherwise status is ``ambiguous`` and nothing is charted.
    """
    if entity_id is not None:
        for candidate in candidates:
            if candidate.get("entity_id") == entity_id:
                return candidate, "ok"
        return None, "no_meter"
    if not candidates:
        return None, "no_meter"
    if len(candidates) == 1:
        return candidates[0], "ok"
    preferred = [
        candidate
        for candidate in candidates
        if any(
            token in f"{candidate.get('entity_id', '')} {candidate.get('friendly_name') or ''}".lower()
            for token in _METER_PREFERENCE_TOKENS
        )
    ]
    if len(preferred) == 1:
        return preferred[0], "ok"
    return None, "ambiguous"


def _current_local_hour_start(now_utc: datetime, zone: ZoneInfo | None) -> datetime:
    """The instant the household clock last read HH:00, as aware UTC.

    Measured on the local clock, so a +05:30 zone's hours start at :30 UTC.
    """
    local = now_utc.astimezone(zone or UTC)
    into_hour = timedelta(
        minutes=local.minute, seconds=local.second, microseconds=local.microsecond
    )
    return now_utc - into_hour


def power_window_start(
    now: datetime, window_hours: int, zone: ZoneInfo | None = None
) -> datetime:
    now_utc = to_utc(now) or datetime.now(UTC)
    current_hour = _current_local_hour_start(now_utc, zone)
    return current_hour - timedelta(hours=window_hours - 1)


def build_power_series(
    readings: Iterable[Mapping[str, Any]],
    *,
    unit: str | None,
    now: datetime,
    window_hours: int = DEFAULT_POWER_WINDOW_HOURS,
    zone: ZoneInfo | None = None,
) -> list[dict[str, Any]]:
    """Hourly kWh from a cumulative energy meter's historian rows.

    Buckets are hours of the household clock (``zone``, default UTC): each
    starts when that clock reads HH:00 and lasts one real hour, and
    ``hour_start``/``hour_end`` carry the local offset. Across DST that means
    a spring-forward window has no bucket labelled with the skipped hour and
    a fall-back window has two buckets labelled with the repeated hour (told
    apart by their offsets); every bucket still spans exactly 60 minutes, so
    no energy is double counted or lost. The last bucket is the current,
    partial hour. Each
    consecutive pair of readings contributes its delta to the hours it spans,
    pro rata by time. A drop in the counter is a meter reset, so the new value
    is the delta. A bucket no reading interval covers has ``kwh=None``; gaps
    longer than ``MAX_INTERPOLATION_GAP`` mark the hours they span unknown,
    unless the counter did not move across the gap (then they are zero).
    """
    now_utc = to_utc(now) or datetime.now(UTC)
    start = power_window_start(now_utc, window_hours, zone)
    label_zone = zone or UTC
    factor = _ENERGY_UNIT_FACTORS.get(str(unit or "").strip().lower(), Decimal(1))
    bucket_starts = [start + timedelta(hours=offset) for offset in range(window_hours)]
    totals: list[Decimal | None] = [None] * window_hours
    unknown = [False] * window_hours

    points: list[tuple[datetime, Decimal]] = []
    for row in readings:
        at = to_utc(row.get("changed_at"))
        value = _number(row.get("state"))
        if at is None or value is None or at > now_utc:
            continue
        points.append((at, value * factor))
    points.sort(key=lambda point: point[0])

    def overlapping(lo: datetime, hi: datetime) -> list[tuple[int, float]]:
        spans: list[tuple[int, float]] = []
        for index, bucket_start in enumerate(bucket_starts):
            bucket_end = bucket_start + timedelta(hours=1)
            overlap = (min(hi, bucket_end) - max(lo, bucket_start)).total_seconds()
            if overlap > 0:
                spans.append((index, overlap))
        return spans

    for (prev_at, prev_value), (cur_at, cur_value) in zip(points, points[1:]):
        if cur_at <= prev_at:
            continue
        spans = overlapping(prev_at, cur_at)
        if not spans:
            continue
        delta = cur_value - prev_value
        if delta < 0:
            delta = cur_value
        if cur_at - prev_at > MAX_INTERPOLATION_GAP and delta != 0:
            # An unchanged counter means nothing was used, however long the
            # gap; a changed one cannot be placed within it honestly.
            for index, _ in spans:
                unknown[index] = True
            continue
        duration = (cur_at - prev_at).total_seconds()
        for index, overlap in spans:
            share = delta * Decimal(str(overlap / duration))
            totals[index] = (totals[index] or Decimal(0)) + share

    buckets: list[dict[str, Any]] = []
    for index, bucket_start in enumerate(bucket_starts):
        total = None if unknown[index] else totals[index]
        bucket_end = bucket_start + timedelta(hours=1)
        buckets.append(
            {
                "hour_start": bucket_start.astimezone(label_zone).isoformat(),
                "hour_end": bucket_end.astimezone(label_zone).isoformat(),
                "kwh": _float(total, 3),
                "partial": bucket_end > now_utc,
            }
        )
    return buckets
