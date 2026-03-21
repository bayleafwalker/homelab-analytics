"""HA Phase 5 — Outbound action dispatcher.

Consumes policy verdicts from the HaPolicyEvaluator and dispatches two classes
of outbound HA service calls:

    Recommendation — persistent notification surfacing policy guidance (no side effect)
    Alert          — persistent notification flagging a policy breach or warning

Actions are triggered by verdict *transitions* (same verdict on consecutive
cycles = no dispatch).  On return to ``ok`` the corresponding HA notifications
are dismissed.

Built-in action mapping:
    ok              → dismiss alert + recommendation (if previously warning/breach)
    warning/breach  → create alert + create recommendation
    unavailable     → no action

HA REST endpoints used:
    POST {ha_url}/api/services/persistent_notification/create
    POST {ha_url}/api/services/persistent_notification/dismiss

Configuration: reuses existing ``ha_url`` + ``ha_token`` from AppSettings.
No new settings required.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from packages.pipelines.ha_policy import HaPolicyEvaluator, PolicyResult

logger = logging.getLogger("homelab_analytics.ha_action_dispatcher")

ActionClass = Literal["recommendation", "alert"]
ActionResult = Literal["success", "failure", "dismissed"]

_NOTIFICATION_ID_PREFIX = "homelab_analytics"
_ACTION_LOG_MAX_SIZE = 100
_HTTP_TIMEOUT = 10.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ActionRecord:
    """One dispatched action in the in-memory log."""

    timestamp: str
    policy_id: str
    policy_name: str
    verdict: str
    previous_verdict: str | None
    action_class: ActionClass
    action_type: str  # "persistent_notification_create" | "persistent_notification_dismiss"
    target: str       # HA notification_id
    result: ActionResult
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "verdict": self.verdict,
            "previous_verdict": self.previous_verdict,
            "action_class": self.action_class,
            "action_type": self.action_type,
            "target": self.target,
            "result": self.result,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def _notification_id(policy_id: str, action_class: ActionClass) -> str:
    """Return the HA notification_id for a policy + action class combination."""
    return f"{_NOTIFICATION_ID_PREFIX}_{action_class}_{policy_id}"


def determine_actions(
    policy_id: str,
    policy_name: str,
    current_verdict: str,
    previous_verdict: str | None,
) -> list[dict[str, Any]]:
    """Return a list of action descriptors to execute for a verdict transition.

    Returns an empty list when no action is needed (no transition, or
    unavailable verdict).  Each descriptor is a dict with keys:
        ``action_class``  — "alert" or "recommendation"
        ``type``          — "create" or "dismiss"
    """
    if current_verdict == "unavailable":
        return []
    if current_verdict == previous_verdict:
        return []

    if current_verdict in ("warning", "breach"):
        # Verdict has transitioned to an actionable state — create both classes.
        return [
            {"action_class": "alert", "type": "create"},
            {"action_class": "recommendation", "type": "create"},
        ]

    if current_verdict == "ok":
        # Only dismiss if there was a previous actionable state to clean up.
        if previous_verdict in ("warning", "breach"):
            return [
                {"action_class": "alert", "type": "dismiss"},
                {"action_class": "recommendation", "type": "dismiss"},
            ]

    return []


def build_notification_create_payload(
    policy_id: str,
    policy_name: str,
    verdict: str,
    value: str | None,
    action_class: ActionClass,
) -> dict[str, Any]:
    """Build the JSON body for POST /api/services/persistent_notification/create."""
    notification_id = _notification_id(policy_id, action_class)
    if action_class == "alert":
        title = f"Alert: {policy_name} — {verdict}"
        message = f"Policy '{policy_name}' verdict is {verdict}."
    else:
        title = f"Recommendation: {policy_name}"
        message = f"Policy '{policy_name}' is now {verdict}."
    if value:
        message += f" Current value: {value}."
    return {"title": title, "message": message, "notification_id": notification_id}


def build_notification_dismiss_payload(
    policy_id: str,
    action_class: ActionClass,
) -> dict[str, Any]:
    """Build the JSON body for POST /api/services/persistent_notification/dismiss."""
    return {"notification_id": _notification_id(policy_id, action_class)}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class HaActionDispatcher:
    """Dispatches recommendation and alert actions to HA on policy verdict transitions.

    Parameters
    ----------
    ha_url:
        Base URL of the HA instance, e.g. ``http://homeassistant.local:8123``.
    ha_token:
        HA long-lived access token.
    evaluator:
        ``HaPolicyEvaluator`` instance whose cached results are read by
        ``dispatch_from_cache()``.
    """

    def __init__(
        self,
        *,
        ha_url: str,
        ha_token: str,
        evaluator: HaPolicyEvaluator,
    ) -> None:
        self._ha_url = ha_url.rstrip("/")
        self._ha_token = ha_token
        self._evaluator = evaluator

        self._previous_verdicts: dict[str, str] = {}
        self._action_log: list[ActionRecord] = []

        self.last_dispatch_at: str | None = None
        self.dispatch_count: int = 0
        self.error_count: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def dispatch_from_cache(self) -> list[ActionRecord]:
        """Read cached policy results from the evaluator and dispatch actions.

        Called from the MQTT publish cycle immediately after
        ``ha_policy_evaluator.evaluate()`` has run.
        """
        results = self._evaluator.get_results()
        if not results:
            return []
        return await self.dispatch(results)

    async def dispatch(self, policy_results: list[PolicyResult]) -> list[ActionRecord]:
        """Process policy results and dispatch actions for verdict transitions.

        Returns the list of ``ActionRecord`` objects created during this call.
        """
        records: list[ActionRecord] = []
        for result in policy_results:
            prev = self._previous_verdicts.get(result.id)
            actions = determine_actions(result.id, result.name, result.verdict, prev)
            for action in actions:
                record = await self._execute_action(result, action, prev)
                records.append(record)
                self._append_log(record)
                if record.result == "failure":
                    self.error_count += 1
            # Always update previous verdict, even if no actions dispatched.
            self._previous_verdicts[result.id] = result.verdict

        if records:
            self.last_dispatch_at = datetime.now(UTC).isoformat()
            self.dispatch_count += 1

        return records

    def get_actions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent action records, newest first."""
        tail = self._action_log[-limit:] if limit < len(self._action_log) else self._action_log
        return [r.to_dict() for r in reversed(tail)]

    def get_status(self) -> dict[str, Any]:
        """Return dispatcher health snapshot."""
        return {
            "enabled": True,
            "last_dispatch_at": self.last_dispatch_at,
            "dispatch_count": self.dispatch_count,
            "error_count": self.error_count,
            "action_log_size": len(self._action_log),
            "tracked_policies": len(self._previous_verdicts),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _execute_action(
        self,
        result: PolicyResult,
        action: dict[str, Any],
        prev: str | None,
    ) -> ActionRecord:
        """Make the HTTP call to HA and return an ActionRecord."""
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for action dispatch. "
                "Install it with: pip install 'httpx>=0.24'"
            ) from exc

        action_class: ActionClass = action["action_class"]
        action_type_key: str = action["type"]

        if action_type_key == "create":
            url = f"{self._ha_url}/api/services/persistent_notification/create"
            payload = build_notification_create_payload(
                result.id, result.name, result.verdict, result.value, action_class
            )
            action_type = "persistent_notification_create"
            result_on_success: ActionResult = "success"
        else:
            url = f"{self._ha_url}/api/services/persistent_notification/dismiss"
            payload = build_notification_dismiss_payload(result.id, action_class)
            action_type = "persistent_notification_dismiss"
            result_on_success = "dismissed"

        target = _notification_id(result.id, action_class)

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._ha_token}"},
                )
            if resp.status_code < 300:
                action_result: ActionResult = result_on_success
                error = None
            else:
                action_result = "failure"
                error = f"HTTP {resp.status_code}"
        except Exception as exc:
            action_result = "failure"
            error = str(exc)

        if action_result == "failure":
            logger.warning(
                "HA action dispatch failed",
                extra={
                    "policy_id": result.id,
                    "action_class": action_class,
                    "action_type": action_type,
                    "error": error,
                },
            )
        else:
            logger.debug(
                "HA action dispatched",
                extra={
                    "policy_id": result.id,
                    "action_class": action_class,
                    "action_type": action_type,
                    "target": target,
                },
            )

        return ActionRecord(
            timestamp=datetime.now(UTC).isoformat(),
            policy_id=result.id,
            policy_name=result.name,
            verdict=result.verdict,
            previous_verdict=prev,
            action_class=action_class,
            action_type=action_type,
            target=target,
            result=action_result,
            error=error,
        )

    def _append_log(self, record: ActionRecord) -> None:
        """Append to ring buffer, evicting oldest entries past max size."""
        self._action_log.append(record)
        if len(self._action_log) > _ACTION_LOG_MAX_SIZE:
            self._action_log = self._action_log[-_ACTION_LOG_MAX_SIZE:]
