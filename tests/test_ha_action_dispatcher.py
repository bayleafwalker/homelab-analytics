"""Tests for HA Phase 5 — Action dispatcher.

All tests are synchronous and have no external dependencies.  The async
``dispatch`` / ``_execute_action`` methods involve httpx calls and are
covered through the pure-function layer and status/state tests here.
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.pipelines.ha_action_dispatcher import (
    _ACTION_LOG_MAX_SIZE,
    ActionRecord,
    HaActionDispatcher,
    _notification_id,
    build_notification_create_payload,
    build_notification_dismiss_payload,
    determine_actions,
)

_NOW = datetime(2026, 3, 21, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

@dataclass
class _PolicyResult:
    """Minimal PolicyResult stub for testing."""
    id: str
    name: str
    description: str
    verdict: str
    value: str | None
    evaluated_at: str


class _FakeEvaluator:
    """Minimal HaPolicyEvaluator stub."""

    def __init__(self, results: list[_PolicyResult]) -> None:
        self._results = results

    def get_results(self) -> list[_PolicyResult]:
        return self._results


def _make_result(
    policy_id: str = "budget_status",
    policy_name: str = "Budget Status",
    verdict: str = "ok",
    value: str | None = None,
) -> _PolicyResult:
    return _PolicyResult(
        id=policy_id,
        name=policy_name,
        description="desc",
        verdict=verdict,
        value=value,
        evaluated_at=_NOW.isoformat(),
    )


def _make_dispatcher(results: list[_PolicyResult] | None = None) -> HaActionDispatcher:
    evaluator = _FakeEvaluator(results or [])
    return HaActionDispatcher(
        ha_url="http://ha.local:8123",
        ha_token="test_token",
        evaluator=evaluator,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# determine_actions — pure function tests
# ---------------------------------------------------------------------------

class DetermineActionsTests(unittest.TestCase):

    def test_no_transition_ok_returns_empty(self) -> None:
        self.assertEqual(determine_actions("p1", "P1", "ok", "ok"), [])

    def test_no_transition_warning_returns_empty(self) -> None:
        self.assertEqual(determine_actions("p1", "P1", "warning", "warning"), [])

    def test_no_transition_breach_returns_empty(self) -> None:
        self.assertEqual(determine_actions("p1", "P1", "breach", "breach"), [])

    def test_unavailable_returns_empty(self) -> None:
        self.assertEqual(determine_actions("p1", "P1", "unavailable", None), [])

    def test_unavailable_transition_from_ok_returns_empty(self) -> None:
        self.assertEqual(determine_actions("p1", "P1", "unavailable", "ok"), [])

    def test_ok_to_warning_returns_two_creates(self) -> None:
        actions = determine_actions("p1", "P1", "warning", "ok")
        self.assertEqual(len(actions), 2)
        types = [a["type"] for a in actions]
        classes = [a["action_class"] for a in actions]
        self.assertIn("alert", classes)
        self.assertIn("recommendation", classes)
        self.assertTrue(all(t == "create" for t in types))

    def test_ok_to_breach_returns_two_creates(self) -> None:
        actions = determine_actions("p1", "P1", "breach", "ok")
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(a["type"] == "create" for a in actions))

    def test_warning_to_breach_returns_two_creates(self) -> None:
        actions = determine_actions("p1", "P1", "breach", "warning")
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(a["type"] == "create" for a in actions))

    def test_breach_to_warning_returns_two_creates(self) -> None:
        """De-escalation still triggers dispatch since verdict changed."""
        actions = determine_actions("p1", "P1", "warning", "breach")
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(a["type"] == "create" for a in actions))

    def test_breach_to_ok_returns_two_dismissals(self) -> None:
        actions = determine_actions("p1", "P1", "ok", "breach")
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(a["type"] == "dismiss" for a in actions))

    def test_warning_to_ok_returns_two_dismissals(self) -> None:
        actions = determine_actions("p1", "P1", "ok", "warning")
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(a["type"] == "dismiss" for a in actions))

    def test_first_evaluation_warning_dispatches(self) -> None:
        """First eval with previous=None and warning verdict should dispatch."""
        actions = determine_actions("p1", "P1", "warning", None)
        self.assertEqual(len(actions), 2)

    def test_first_evaluation_ok_does_not_dispatch(self) -> None:
        """First eval with previous=None and ok verdict should not dispatch."""
        self.assertEqual(determine_actions("p1", "P1", "ok", None), [])

    def test_ok_to_ok_no_previous_does_not_dispatch(self) -> None:
        # ok with no previous — same as first_eval_ok above
        self.assertEqual(determine_actions("p1", "P1", "ok", None), [])


# ---------------------------------------------------------------------------
# Notification payload builders
# ---------------------------------------------------------------------------

class NotificationPayloadTests(unittest.TestCase):

    def test_notification_id_format_alert(self) -> None:
        nid = _notification_id("budget_status", "alert")
        self.assertEqual(nid, "homelab_analytics_alert_budget_status")

    def test_notification_id_format_recommendation(self) -> None:
        nid = _notification_id("budget_status", "recommendation")
        self.assertEqual(nid, "homelab_analytics_recommendation_budget_status")

    def test_create_payload_has_required_keys(self) -> None:
        payload = build_notification_create_payload(
            "budget_status", "Budget Status", "warning", "85.0%", "alert"
        )
        self.assertIn("title", payload)
        self.assertIn("message", payload)
        self.assertIn("notification_id", payload)

    def test_alert_title_contains_alert_prefix(self) -> None:
        payload = build_notification_create_payload(
            "budget_status", "Budget Status", "warning", None, "alert"
        )
        self.assertIn("Alert:", payload["title"])

    def test_recommendation_title_contains_recommendation_prefix(self) -> None:
        payload = build_notification_create_payload(
            "budget_status", "Budget Status", "warning", None, "recommendation"
        )
        self.assertIn("Recommendation:", payload["title"])

    def test_value_included_in_message_when_present(self) -> None:
        payload = build_notification_create_payload(
            "budget_status", "Budget Status", "warning", "92.5%", "alert"
        )
        self.assertIn("92.5%", payload["message"])

    def test_no_value_message_still_valid(self) -> None:
        payload = build_notification_create_payload(
            "budget_status", "Budget Status", "warning", None, "alert"
        )
        self.assertIsInstance(payload["message"], str)
        self.assertGreater(len(payload["message"]), 0)

    def test_dismiss_payload_has_notification_id(self) -> None:
        payload = build_notification_dismiss_payload("budget_status", "alert")
        self.assertIn("notification_id", payload)
        self.assertEqual(payload["notification_id"], "homelab_analytics_alert_budget_status")


# ---------------------------------------------------------------------------
# ActionRecord dataclass
# ---------------------------------------------------------------------------

class ActionRecordTests(unittest.TestCase):

    def _make_record(self) -> ActionRecord:
        return ActionRecord(
            timestamp=_NOW.isoformat(),
            policy_id="budget_status",
            policy_name="Budget Status",
            verdict="warning",
            previous_verdict="ok",
            action_class="alert",
            action_type="persistent_notification_create",
            target="homelab_analytics_alert_budget_status",
            result="success",
            error=None,
        )

    def test_to_dict_has_all_keys(self) -> None:
        record = self._make_record()
        d = record.to_dict()
        expected_keys = {
            "timestamp", "policy_id", "policy_name", "verdict",
            "previous_verdict", "action_class", "action_type",
            "target", "result", "error",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_to_dict_values_match(self) -> None:
        record = self._make_record()
        d = record.to_dict()
        self.assertEqual(d["policy_id"], "budget_status")
        self.assertEqual(d["verdict"], "warning")
        self.assertEqual(d["previous_verdict"], "ok")
        self.assertEqual(d["action_class"], "alert")
        self.assertIsNone(d["error"])

    def test_construction_with_error(self) -> None:
        record = ActionRecord(
            timestamp=_NOW.isoformat(),
            policy_id="bridge_health",
            policy_name="Bridge Health",
            verdict="warning",
            previous_verdict="ok",
            action_class="recommendation",
            action_type="persistent_notification_create",
            target="homelab_analytics_recommendation_bridge_health",
            result="failure",
            error="Connection refused",
        )
        self.assertEqual(record.error, "Connection refused")
        self.assertEqual(record.result, "failure")


# ---------------------------------------------------------------------------
# HaActionDispatcher — state and status tests (synchronous)
# ---------------------------------------------------------------------------

class HaActionDispatcherTests(unittest.TestCase):

    def test_initial_status_shape(self) -> None:
        d = _make_dispatcher()
        status = d.get_status()
        expected_keys = {
            "enabled", "last_dispatch_at", "dispatch_count",
            "error_count", "action_log_size", "tracked_policies",
        }
        self.assertEqual(set(status.keys()), expected_keys)

    def test_enabled_defaults_true(self) -> None:
        d = _make_dispatcher()
        self.assertTrue(d.get_status()["enabled"])

    def test_initial_dispatch_count_zero(self) -> None:
        d = _make_dispatcher()
        self.assertEqual(d.get_status()["dispatch_count"], 0)

    def test_initial_last_dispatch_at_none(self) -> None:
        d = _make_dispatcher()
        self.assertIsNone(d.get_status()["last_dispatch_at"])

    def test_get_actions_empty_initially(self) -> None:
        d = _make_dispatcher()
        self.assertEqual(d.get_actions(), [])

    def test_get_actions_limit_respected(self) -> None:
        d = _make_dispatcher()
        # Manually populate the log
        for i in range(20):
            d._action_log.append(ActionRecord(
                timestamp=_NOW.isoformat(),
                policy_id=f"p{i}",
                policy_name=f"Policy {i}",
                verdict="warning",
                previous_verdict="ok",
                action_class="alert",
                action_type="persistent_notification_create",
                target=f"homelab_analytics_alert_p{i}",
                result="success",
                error=None,
            ))
        result = d.get_actions(limit=5)
        self.assertEqual(len(result), 5)

    def test_get_actions_newest_first(self) -> None:
        d = _make_dispatcher()
        for i in range(3):
            d._action_log.append(ActionRecord(
                timestamp=f"2026-03-21T12:00:0{i}+00:00",
                policy_id="budget_status",
                policy_name="Budget Status",
                verdict="warning",
                previous_verdict="ok",
                action_class="alert",
                action_type="persistent_notification_create",
                target="homelab_analytics_alert_budget_status",
                result="success",
                error=None,
            ))
        actions = d.get_actions()
        # Newest (index 2) should be first
        self.assertIn("02", actions[0]["timestamp"])

    def test_ring_buffer_caps_at_max_size(self) -> None:
        d = _make_dispatcher()
        for i in range(_ACTION_LOG_MAX_SIZE + 20):
            record = ActionRecord(
                timestamp=_NOW.isoformat(),
                policy_id="budget_status",
                policy_name="Budget Status",
                verdict="warning",
                previous_verdict="ok",
                action_class="alert",
                action_type="persistent_notification_create",
                target="homelab_analytics_alert_budget_status",
                result="success",
                error=None,
            )
            d._append_log(record)
        self.assertEqual(len(d._action_log), _ACTION_LOG_MAX_SIZE)

    def test_previous_verdicts_tracked(self) -> None:
        """After _previous_verdicts is set directly, get_status reflects it."""
        d = _make_dispatcher()
        d._previous_verdicts["budget_status"] = "warning"
        d._previous_verdicts["bridge_health"] = "ok"
        self.assertEqual(d.get_status()["tracked_policies"], 2)

    def test_action_log_size_in_status(self) -> None:
        d = _make_dispatcher()
        for i in range(5):
            d._action_log.append(ActionRecord(
                timestamp=_NOW.isoformat(),
                policy_id="p",
                policy_name="P",
                verdict="warning",
                previous_verdict="ok",
                action_class="alert",
                action_type="persistent_notification_create",
                target="t",
                result="success",
                error=None,
            ))
        self.assertEqual(d.get_status()["action_log_size"], 5)


if __name__ == "__main__":
    unittest.main()
