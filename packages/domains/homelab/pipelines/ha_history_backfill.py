"""Backfill Home Assistant state history for named entities over a closed window.

The live bridge only captures states from the moment it connects (plus a short
gap replay). Evidence over an already closed month — the Kotiakku battery-plan
assessment needs every five-minute window of it — has to be read back from the
HA recorder. This module pulls ``GET /api/history/period/{start}`` in bounded
chunks for an explicit entity list and hands the states to an idempotent
ingest (``ingest_ha_history_states``): re-running a window adds nothing.

``significant_changes_only=0`` is required: the Kotiakku measurement sensors
move their period attributes every five minutes even when the value repeats,
and HA drops such attribute-only changes from the default history response.

Read-only toward Home Assistant. What HA's recorder has purged cannot be
recovered here; the assessment reports the resulting coverage gap rather than
filling it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

HistoryFetch = Callable[[str, dict[str, str], dict[str, str]], list[list[dict[str, Any]]]]
HistoryIngest = Callable[..., dict[str, int]]

DEFAULT_CHUNK = timedelta(days=1)


@dataclass(frozen=True)
class HaHistoryBackfillResult:
    run_id: str
    start: datetime
    end: datetime
    entity_ids: tuple[str, ...]
    chunks: int
    received: int
    inserted: int
    skipped_existing: int
    states_by_entity: dict[str, int]
    failed_chunks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "entity_ids": list(self.entity_ids),
            "chunks": self.chunks,
            "received": self.received,
            "inserted": self.inserted,
            "skipped_existing": self.skipped_existing,
            "states_by_entity": self.states_by_entity,
            "entities_without_history": [
                entity_id for entity_id in self.entity_ids if not self.states_by_entity.get(entity_id)
            ],
            "failed_chunks": list(self.failed_chunks),
        }


def httpx_history_fetch(timeout: float = 120.0) -> HistoryFetch:
    def fetch(
        url: str, headers: dict[str, str], params: dict[str, str]
    ) -> list[list[dict[str, Any]]]:
        response = httpx.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    return fetch


def backfill_ha_history(
    ingest: HistoryIngest,
    *,
    ha_url: str,
    ha_token: str,
    entity_ids: Sequence[str],
    start: datetime,
    end: datetime,
    fetch: HistoryFetch | None = None,
    chunk: timedelta = DEFAULT_CHUNK,
    run_id: str | None = None,
) -> HaHistoryBackfillResult:
    """Read HA history for ``entity_ids`` over ``[start, end)`` and ingest it."""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must include a timezone offset.")
    if end <= start:
        raise ValueError("end must be after start.")
    if not entity_ids:
        raise ValueError("At least one entity id is required.")
    if chunk <= timedelta(0):
        raise ValueError("chunk must be positive.")
    resolved_fetch = fetch or httpx_history_fetch()
    resolved_run_id = run_id or f"ha-history-backfill-{uuid.uuid4().hex[:8]}"
    entities = tuple(dict.fromkeys(entity_ids))
    headers = {"Authorization": f"Bearer {ha_token}"}
    base = ha_url.rstrip("/")
    counts = {"received": 0, "inserted": 0, "skipped_existing": 0}
    by_entity: dict[str, int] = {}
    failed: list[str] = []
    chunks = 0
    cursor = start.astimezone(UTC)
    stop = end.astimezone(UTC)
    while cursor < stop:
        upper = min(cursor + chunk, stop)
        chunks += 1
        try:
            history = resolved_fetch(
                f"{base}/api/history/period/{quote(cursor.isoformat(), safe='')}",
                headers,
                {
                    "end_time": upper.isoformat(),
                    "filter_entity_id": ",".join(entities),
                    "significant_changes_only": "0",
                },
            )
        except (httpx.HTTPError, ValueError) as exc:
            failed.append(f"{cursor.isoformat()}: {type(exc).__name__}")
            cursor = upper
            continue
        states = [
            state
            for entity_history in history
            for state in entity_history
            if isinstance(state, dict) and state.get("entity_id") in entities
        ]
        for state in states:
            by_entity[state["entity_id"]] = by_entity.get(state["entity_id"], 0) + 1
        summary = ingest(states, run_id=resolved_run_id, source_system="ha_history_backfill")
        for key in counts:
            counts[key] += int(summary.get(key, 0))
        cursor = upper
    return HaHistoryBackfillResult(
        run_id=resolved_run_id,
        start=start,
        end=end,
        entity_ids=entities,
        chunks=chunks,
        received=counts["received"],
        inserted=counts["inserted"],
        skipped_existing=counts["skipped_existing"],
        states_by_entity=by_entity,
        failed_chunks=tuple(failed),
    )
