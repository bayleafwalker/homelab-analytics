"""Home Assistant WebSocket bridge — Phase 2 live subscription worker.

The bridge connects to HA's WebSocket API, subscribes to ``state_changed``
events, and calls ``ingest_fn`` for each incoming state.  It runs as a
long-lived asyncio task alongside uvicorn (started/stopped via FastAPI
lifespan).

Resilience model (from architecture doc):
- Exponential backoff on disconnect: 1 s → 2 s → 4 s → … → 60 s cap.
- Short gap (< ``_GAP_REPLAY_SECONDS``): replay missed states via HA
  history REST endpoint before resuming the WS subscription.
- Long gap: full state resync via ``GET /api/states``.

Configuration (via AppSettings):
    HOMELAB_ANALYTICS_HA_URL   — e.g. ``http://homeassistant.local:8123``
    HOMELAB_ANALYTICS_HA_TOKEN — HA long-lived access token
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from packages.adapters.contracts import AdapterRuntimeStatus

import httpx
import websockets

logger = logging.getLogger("homelab_analytics.ha_bridge")

_BACKOFF_BASE: float = 1.0
_BACKOFF_MAX: float = 60.0
_GAP_REPLAY_SECONDS: int = 300  # use history API for gaps < 5 min


def _ws_url_from_ha_url(ha_url: str) -> str:
    """Convert an HTTP HA base URL to its WebSocket equivalent."""
    url = ha_url.rstrip("/")
    if url.startswith("https://"):
        url = "wss://" + url[len("https://"):]
    elif url.startswith("http://"):
        url = "ws://" + url[len("http://"):]
    return url + "/api/websocket"


# Type alias for the ingest callable expected by the bridge.
# Matches the signature of TransformationService.ingest_ha_states.
IngestFn = Callable[..., int]


class HaBridgeWorker:
    """Long-running WebSocket bridge worker.

    Parameters
    ----------
    ingest_fn:
        Callable with signature ``(states, *, run_id, source_system) -> int``.
        In production this is ``transformation_service.ingest_ha_states``.
    ha_url:
        Base URL of the HA instance, e.g. ``http://homeassistant.local:8123``.
    ha_token:
        HA long-lived access token.
    """

    def __init__(self, ingest_fn: IngestFn, *, ha_url: str, ha_token: str) -> None:
        self._ingest_fn = ingest_fn
        self._ha_url = ha_url.rstrip("/")
        self._ha_token = ha_token
        self._ws_url = _ws_url_from_ha_url(self._ha_url)

        self._running: bool = False
        self._task: asyncio.Task | None = None

        # Status fields — read by get_status()
        self.connected: bool = False
        self.last_sync_at: str | None = None
        self.reconnect_count: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Schedule the bridge loop as an asyncio background task."""
        self._running = True
        self._task = asyncio.create_task(self._run(), name="ha_bridge")
        logger.info("HA bridge worker started (target: %s)", self._ha_url)

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.connected = False
        logger.info("HA bridge worker stopped")

    def get_status(self) -> dict[str, Any]:
        """Return current bridge health snapshot."""
        return {
            "connected": self.connected,
            "last_sync_at": self.last_sync_at,
            "reconnect_count": self.reconnect_count,
        }

    def get_runtime_status(self) -> AdapterRuntimeStatus:
        """Return a typed runtime status snapshot for the adapter layer."""
        from packages.adapters.contracts import AdapterRuntimeStatus

        return AdapterRuntimeStatus(
            enabled=True,
            connected=self.connected,
            last_activity_at=self.last_sync_at,
            error_count=0,
            extra={"reconnect_count": self.reconnect_count},
        )

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        backoff = _BACKOFF_BASE
        disconnected_at: str | None = None

        while self._running:
            try:
                await self._connect_and_subscribe()
                # Clean loop exit means we were asked to stop.
                backoff = _BACKOFF_BASE
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    "HA bridge connection lost",
                    extra={"error": str(exc), "backoff_seconds": backoff},
                )
            finally:
                self.connected = False

            if not self._running:
                break

            disconnected_at = disconnected_at or datetime.now(UTC).isoformat()
            self.reconnect_count += 1
            logger.info("HA bridge reconnecting in %.1f s", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

            # Replay missed events before resuming the WS subscription.
            if disconnected_at:
                await self._replay_gap(disconnected_at)
                disconnected_at = None

    async def _connect_and_subscribe(self) -> None:
        async with websockets.connect(self._ws_url) as ws:  # type: ignore[attr-defined]
            await self._handshake(ws)

            # Subscribe to state_changed events.
            await ws.send(json.dumps({
                "id": 1,
                "type": "subscribe_events",
                "event_type": "state_changed",
            }))
            ack = json.loads(await ws.recv())
            if not (ack.get("type") == "result" and ack.get("success")):
                raise RuntimeError(f"HA subscribe_events failed: {ack}")

            self.connected = True
            logger.info("HA bridge subscribed to state_changed events")

            async for raw in ws:
                if not self._running:
                    return
                try:
                    self._handle_event(json.loads(raw))
                except Exception as exc:
                    logger.warning("HA bridge event error", extra={"error": str(exc)})

    async def _handshake(self, ws: Any) -> None:
        msg = json.loads(await ws.recv())
        if msg.get("type") != "auth_required":
            raise RuntimeError(f"Expected auth_required, got: {msg.get('type')}")
        await ws.send(json.dumps({"type": "auth", "access_token": self._ha_token}))
        msg = json.loads(await ws.recv())
        if msg.get("type") == "auth_invalid":
            raise RuntimeError("HA WebSocket auth failed — check HOMELAB_ANALYTICS_HA_TOKEN")
        if msg.get("type") != "auth_ok":
            raise RuntimeError(f"Unexpected auth response: {msg}")

    def _handle_event(self, msg: dict[str, Any]) -> None:
        """Process one WS message; ingest state if it's a state_changed event."""
        if msg.get("type") != "event":
            return
        event = msg.get("event", {})
        if event.get("event_type") != "state_changed":
            return
        new_state = event.get("data", {}).get("new_state")
        if not new_state:
            return

        run_id = uuid.uuid4().hex[:16]
        self._ingest_fn([new_state], run_id=run_id, source_system="ha_websocket")
        self.last_sync_at = datetime.now(UTC).isoformat()

    # ------------------------------------------------------------------
    # Gap replay (REST backfill on reconnection)
    # ------------------------------------------------------------------

    async def _replay_gap(self, since: str) -> None:
        try:
            gap_seconds = (datetime.now(UTC) - datetime.fromisoformat(since)).total_seconds()
        except ValueError:
            gap_seconds = _GAP_REPLAY_SECONDS + 1  # treat parse failure as long gap

        if gap_seconds > _GAP_REPLAY_SECONDS:
            logger.info("HA bridge gap %.0f s — performing full state resync", gap_seconds)
            await self._full_state_resync()
        else:
            logger.info("HA bridge gap %.0f s — replaying history since %s", gap_seconds, since)
            await self._history_replay(since)

    async def _history_replay(self, since: str) -> None:
        """Fetch HA history for the gap period and ingest missed states."""
        url = f"{self._ha_url}/api/history/period/{since}"
        headers = {"Authorization": f"Bearer {self._ha_token}"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(
                    "HA history replay request failed",
                    extra={"status": resp.status_code},
                )
                return
            # history/period returns list[list[state_obj]] — one list per entity.
            history: list[list[dict]] = resp.json()
            states = [s for entity_history in history for s in entity_history if s.get("entity_id")]
            if states:
                run_id = f"gap-replay-{uuid.uuid4().hex[:8]}"
                self._ingest_fn(states, run_id=run_id, source_system="ha_gap_replay")
                logger.info("HA history replay ingested %d states", len(states))
        except Exception as exc:
            logger.warning("HA history replay error", extra={"error": str(exc)})

    async def _full_state_resync(self) -> None:
        """Fetch all current entity states from HA REST and ingest them."""
        url = f"{self._ha_url}/api/states"
        headers = {"Authorization": f"Bearer {self._ha_token}"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(
                    "HA full resync request failed",
                    extra={"status": resp.status_code},
                )
                return
            states: list[dict] = resp.json()
            if states:
                run_id = f"full-resync-{uuid.uuid4().hex[:8]}"
                self._ingest_fn(states, run_id=run_id, source_system="ha_resync")
                logger.info("HA full resync ingested %d states", len(states))
        except Exception as exc:
            logger.warning("HA full resync error", extra={"error": str(exc)})
