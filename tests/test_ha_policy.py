"""Tests for HaPolicyEvaluator — Phase 4 policy evaluation engine.

Tests cover the three built-in policy functions (budget_status,
monthly_spend_rate, bridge_health) and the HaPolicyEvaluator class, using
only synchronous logic — no DB or network required.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from packages.pipelines.ha_policy import (
    _BUILTIN_POLICIES,
    HaPolicyEvaluator,
    PolicyResult,
    _evaluate_bridge_health,
    _evaluate_budget_status,
    _evaluate_monthly_spend_rate,
    _evaluate_declarative_rule,
    _PolicyDef,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)  # day 15 of 31 → 48.4% elapsed

def _budget_row(utilization_pct: float) -> dict:
    return {
        "budget_name": "household",
        "category_id": "groceries",
        "target_amount": "1000.00",
        "spent_amount": str(utilization_pct * 10),
        "remaining": str(1000.0 - utilization_pct * 10),
        "utilization_pct": str(utilization_pct),
        "currency": "EUR",
    }


# ---------------------------------------------------------------------------
# budget_status
# ---------------------------------------------------------------------------

class BudgetStatusTests(unittest.TestCase):
    def test_no_rows_returns_unavailable(self) -> None:
        verdict, value = _evaluate_budget_status({}, _NOW)
        self.assertEqual("unavailable", verdict)
        self.assertIsNone(value)

    def test_empty_list_returns_unavailable(self) -> None:
        verdict, value = _evaluate_budget_status({"budget_rows": []}, _NOW)
        self.assertEqual("unavailable", verdict)
        self.assertIsNone(value)

    def test_low_utilization_returns_ok(self) -> None:
        verdict, _ = _evaluate_budget_status({"budget_rows": [_budget_row(50.0)]}, _NOW)
        self.assertEqual("ok", verdict)

    def test_at_warning_threshold_returns_warning(self) -> None:
        verdict, _ = _evaluate_budget_status({"budget_rows": [_budget_row(80.0)]}, _NOW)
        self.assertEqual("warning", verdict)

    def test_above_warning_threshold_returns_warning(self) -> None:
        verdict, _ = _evaluate_budget_status({"budget_rows": [_budget_row(95.0)]}, _NOW)
        self.assertEqual("warning", verdict)

    def test_over_100_pct_returns_breach(self) -> None:
        verdict, value = _evaluate_budget_status({"budget_rows": [_budget_row(110.0)]}, _NOW)
        self.assertEqual("breach", verdict)
        self.assertIn("110.0%", value)

    def test_max_across_multiple_rows(self) -> None:
        rows = [_budget_row(30.0), _budget_row(105.0), _budget_row(70.0)]
        verdict, _ = _evaluate_budget_status({"budget_rows": rows}, _NOW)
        self.assertEqual("breach", verdict)

    def test_value_contains_percentage(self) -> None:
        _, value = _evaluate_budget_status({"budget_rows": [_budget_row(55.0)]}, _NOW)
        self.assertIn("%", value)


# ---------------------------------------------------------------------------
# monthly_spend_rate
# ---------------------------------------------------------------------------

class MonthlySpendRateTests(unittest.TestCase):
    def test_no_rows_returns_unavailable(self) -> None:
        verdict, _ = _evaluate_monthly_spend_rate({"budget_rows": []}, _NOW)
        self.assertEqual("unavailable", verdict)

    def test_spend_below_pace_returns_ok(self) -> None:
        # 48.4% of month elapsed; spend at 30% → well under pace
        verdict, _ = _evaluate_monthly_spend_rate({"budget_rows": [_budget_row(30.0)]}, _NOW)
        self.assertEqual("ok", verdict)

    def test_spend_ahead_of_pace_returns_warning(self) -> None:
        # 48.4% elapsed; spend at 70% → more than 15 pct-points ahead of pace
        verdict, _ = _evaluate_monthly_spend_rate({"budget_rows": [_budget_row(70.0)]}, _NOW)
        self.assertEqual("warning", verdict)

    def test_over_budget_returns_breach(self) -> None:
        verdict, _ = _evaluate_monthly_spend_rate({"budget_rows": [_budget_row(105.0)]}, _NOW)
        self.assertEqual("breach", verdict)

    def test_value_contains_spent_and_elapsed(self) -> None:
        _, value = _evaluate_monthly_spend_rate({"budget_rows": [_budget_row(40.0)]}, _NOW)
        self.assertIn("spent", value)
        self.assertIn("elapsed", value)


# ---------------------------------------------------------------------------
# bridge_health
# ---------------------------------------------------------------------------

class BridgeHealthTests(unittest.TestCase):
    def test_no_last_sync_returns_unavailable(self) -> None:
        verdict, _ = _evaluate_bridge_health({}, _NOW)
        self.assertEqual("unavailable", verdict)

    def test_none_last_sync_returns_unavailable(self) -> None:
        verdict, _ = _evaluate_bridge_health({"bridge_last_sync_at": None}, _NOW)
        self.assertEqual("unavailable", verdict)

    def test_recent_sync_returns_ok(self) -> None:
        recent = (_NOW - timedelta(seconds=60)).isoformat()
        verdict, _ = _evaluate_bridge_health({"bridge_last_sync_at": recent}, _NOW)
        self.assertEqual("ok", verdict)

    def test_stale_sync_returns_warning(self) -> None:
        stale = (_NOW - timedelta(seconds=400)).isoformat()
        verdict, _ = _evaluate_bridge_health({"bridge_last_sync_at": stale}, _NOW)
        self.assertEqual("warning", verdict)

    def test_exactly_at_threshold_returns_warning(self) -> None:
        at_threshold = (_NOW - timedelta(seconds=300)).isoformat()
        # >300 is stale; exactly 300 is still ok (not strictly >)
        verdict, _ = _evaluate_bridge_health({"bridge_last_sync_at": at_threshold}, _NOW)
        self.assertEqual("ok", verdict)

    def test_invalid_timestamp_returns_unavailable(self) -> None:
        verdict, _ = _evaluate_bridge_health({"bridge_last_sync_at": "not-a-date"}, _NOW)
        self.assertEqual("unavailable", verdict)

    def test_value_contains_seconds(self) -> None:
        recent = (_NOW - timedelta(seconds=45)).isoformat()
        _, value = _evaluate_bridge_health({"bridge_last_sync_at": recent}, _NOW)
        self.assertIn("s since last sync", value)


# ---------------------------------------------------------------------------
# HaPolicyEvaluator
# ---------------------------------------------------------------------------

class PolicyEvaluatorTests(unittest.TestCase):
    def _evaluator(self, context: dict | None = None) -> HaPolicyEvaluator:
        ctx = context if context is not None else {}
        return HaPolicyEvaluator(lambda: ctx)

    def test_evaluate_returns_three_results(self) -> None:
        evaluator = self._evaluator()
        results = evaluator.evaluate()
        self.assertEqual(4, len(results))

    def test_evaluate_result_ids(self) -> None:
        evaluator = self._evaluator()
        ids = {r.id for r in evaluator.evaluate()}
        self.assertEqual(
            {"budget_status", "monthly_spend_rate", "bridge_health", "kitchen_light_request"},
            ids,
        )

    def test_result_to_dict_keys(self) -> None:
        evaluator = self._evaluator()
        d = evaluator.evaluate()[0].to_dict()
        for key in (
            "id",
            "name",
            "description",
            "verdict",
            "value",
            "evaluated_at",
            "approval_required",
            "input_freshness",
        ):
            self.assertIn(key, d)

    def test_get_results_empty_before_evaluate(self) -> None:
        evaluator = self._evaluator()
        self.assertEqual([], evaluator.get_results())

    def test_get_results_returns_cache_after_evaluate(self) -> None:
        evaluator = self._evaluator()
        first = evaluator.evaluate()
        self.assertIs(first, evaluator.get_results())

    def test_fetch_error_yields_unavailable_verdicts(self) -> None:
        def bad_fetch():
            raise RuntimeError("db offline")
        evaluator = HaPolicyEvaluator(bad_fetch)
        results = evaluator.evaluate()
        self.assertTrue(all(r.verdict == "unavailable" for r in results))

    def test_all_unavailable_when_no_data(self) -> None:
        evaluator = self._evaluator({})
        verdicts = {r.verdict for r in evaluator.evaluate()}
        self.assertEqual({"unavailable"}, verdicts)

    def test_policy_count_matches_registry(self) -> None:
        evaluator = self._evaluator()
        self.assertEqual(len(_BUILTIN_POLICIES), len(evaluator.evaluate()))

    def test_policy_registry_propagates_approval_required(self) -> None:
        def eval_ok(context: dict, now: datetime) -> tuple[str, str | None]:
            return "warning", "123.4%"

        sentinel = _PolicyDef(
            id="device_control",
            name="Device Control",
            description="Approval-gated device control proposal.",
            evaluate_fn=eval_ok,
            approval_required=True,
        )
        original = list(_BUILTIN_POLICIES)
        try:
            _BUILTIN_POLICIES.append(sentinel)
            results = self._evaluator({}).evaluate()
        finally:
            _BUILTIN_POLICIES[:] = original

        match = next(r for r in results if r.id == "device_control")
        self.assertIsInstance(match, PolicyResult)
        self.assertTrue(match.approval_required)
        self.assertEqual(match.to_dict()["approval_required"], True)

    def test_kitchen_light_request_policy_uses_helper_entity(self) -> None:
        evaluator = self._evaluator(
            {
                "ha_entities": [
                    {
                        "entity_id": "input_boolean.hla_kitchen_light_request",
                        "last_state": "on",
                    }
                ]
            }
        )
        result = next(r for r in evaluator.evaluate() if r.id == "kitchen_light_request")
        self.assertEqual("warning", result.verdict)
        self.assertTrue(result.approval_required)
        self.assertIn("approval_action", result.metadata)
        self.assertEqual(
            result.metadata["approval_action"]["service"],
            "turn_on",
        )
        self.assertEqual(
            result.to_dict()["metadata"]["approval_action"]["domain"],
            "light",
        )

    def test_to_dict_includes_input_freshness_none_when_not_set(self) -> None:
        evaluator = self._evaluator()
        results = evaluator.evaluate()
        # All results should have input_freshness as None when no control_plane_store is set
        for result in results:
            d = result.to_dict()
            self.assertIsNone(d["input_freshness"])

    def test_to_dict_includes_input_freshness_when_set(self) -> None:
        from packages.pipelines.ha_policy import ConfidenceSummary

        result = PolicyResult(
            id="test_policy",
            name="Test Policy",
            description="Test description",
            verdict="ok",
            value="100%",
            evaluated_at=_NOW.isoformat(),
            approval_required=False,
            input_freshness=ConfidenceSummary(
                verdict="TRUSTWORTHY",
                freshness_state="CURRENT",
                completeness_pct=95,
                assessed_at=_NOW,
            ),
        )
        d = result.to_dict()
        self.assertIsNotNone(d["input_freshness"])
        self.assertEqual("TRUSTWORTHY", d["input_freshness"]["verdict"])
        self.assertEqual("CURRENT", d["input_freshness"]["freshness_state"])
        self.assertEqual(95, d["input_freshness"]["completeness_pct"])
        self.assertEqual(_NOW.isoformat(), d["input_freshness"]["assessed_at"])


# ---------------------------------------------------------------------------
# Registry integration tests
# ---------------------------------------------------------------------------

import json
from packages.storage.control_plane import PolicyDefinitionCreate, PolicyDefinitionRecord


def _make_record(
    policy_id: str,
    rule_doc: dict,
    *,
    enabled: bool = True,
    source_kind: str = "operator",
) -> PolicyDefinitionRecord:
    now = datetime.now(UTC)
    return PolicyDefinitionRecord(
        policy_id=policy_id,
        display_name=f"Policy {policy_id}",
        policy_kind=rule_doc.get("rule_kind", "unknown"),
        rule_schema_version="1.0",
        rule_document=json.dumps(rule_doc),
        enabled=enabled,
        source_kind=source_kind,
        description=None,
        creator=None,
        created_at=now,
        updated_at=now,
    )


class _FakeRegistryStore:
    def __init__(self, records: list[PolicyDefinitionRecord]) -> None:
        self._records = records

    def list_policy_definitions(
        self, *, source_kind: str | None = None, enabled_only: bool = False
    ) -> list[PolicyDefinitionRecord]:
        result = self._records
        if enabled_only:
            result = [r for r in result if r.enabled]
        if source_kind is not None:
            result = [r for r in result if r.source_kind == source_kind]
        return result


_VALUE_RULE = {
    "rule_kind": "publication_value_comparison",
    "publication_key": "monthly_cashflow",
    "field_name": "net",
    "operator": "lt",
    "threshold": 0,
}

_HA_RULE = {
    "rule_kind": "ha_helper_state_comparison",
    "entity_id": "input_boolean.kitchen",
    "operator": "eq",
    "expected_value": "on",
}


class RegistryIntegrationTests(unittest.TestCase):
    def test_no_registry_store_returns_only_builtins(self) -> None:
        evaluator = HaPolicyEvaluator(lambda: {})
        results = evaluator.evaluate()
        ids = {r.id for r in results}
        self.assertEqual({"budget_status", "monthly_spend_rate", "bridge_health", "kitchen_light_request"}, ids)

    def test_registry_policy_appended_to_results(self) -> None:
        store = _FakeRegistryStore([_make_record("my_registry_policy", _VALUE_RULE)])
        evaluator = HaPolicyEvaluator(
            lambda: {"publication_monthly_cashflow": [{"net": -100}]},
            policy_registry_store=store,
        )
        results = evaluator.evaluate()
        ids = {r.id for r in results}
        self.assertIn("my_registry_policy", ids)
        reg_result = next(r for r in results if r.id == "my_registry_policy")
        self.assertEqual("breach", reg_result.verdict)

    def test_disabled_registry_policy_not_evaluated(self) -> None:
        store = _FakeRegistryStore([_make_record("disabled_policy", _VALUE_RULE, enabled=False)])
        evaluator = HaPolicyEvaluator(lambda: {}, policy_registry_store=store)
        results = evaluator.evaluate()
        self.assertNotIn("disabled_policy", {r.id for r in results})

    def test_registry_store_failure_is_graceful(self) -> None:
        class _BrokenStore:
            def list_policy_definitions(self, **_):
                raise RuntimeError("store offline")

        evaluator = HaPolicyEvaluator(lambda: {}, policy_registry_store=_BrokenStore())
        results = evaluator.evaluate()
        self.assertEqual(len(_BUILTIN_POLICIES), len(results))

    def test_registry_policy_with_invalid_rule_returns_unavailable(self) -> None:
        record = _make_record("bad_rule", {"rule_kind": "exec_python", "code": "bad"})
        store = _FakeRegistryStore([record])
        evaluator = HaPolicyEvaluator(lambda: {}, policy_registry_store=store)
        results = evaluator.evaluate()
        reg = next(r for r in results if r.id == "bad_rule")
        self.assertEqual("unavailable", reg.verdict)


class DeclarativeRuleEvaluationTests(unittest.TestCase):
    _NOW = datetime.now(UTC)

    def test_publication_value_comparison_breach(self) -> None:
        rule = {"rule_kind": "publication_value_comparison", "publication_key": "monthly_cashflow", "field_name": "net", "operator": "lt", "threshold": 0}
        ctx = {"publication_monthly_cashflow": [{"net": "-500"}]}
        verdict, value = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("breach", verdict)

    def test_publication_value_comparison_ok(self) -> None:
        # operator "lt 0" is the breach condition; net=1200 does not breach it
        rule = {"rule_kind": "publication_value_comparison", "publication_key": "monthly_cashflow", "field_name": "net", "operator": "lt", "threshold": 0}
        ctx = {"publication_monthly_cashflow": [{"net": "1200"}]}
        verdict, value = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("ok", verdict)

    def test_publication_value_comparison_missing_data_unavailable(self) -> None:
        rule = {"rule_kind": "publication_value_comparison", "publication_key": "monthly_cashflow", "field_name": "net", "operator": "lt", "threshold": 0}
        verdict, _ = _evaluate_declarative_rule(rule, {}, self._NOW, None)
        self.assertEqual("unavailable", verdict)

    def test_ha_helper_state_eq_ok(self) -> None:
        rule = {"rule_kind": "ha_helper_state_comparison", "entity_id": "input_boolean.kitchen", "operator": "eq", "expected_value": "on"}
        ctx = {"ha_entities": [{"entity_id": "input_boolean.kitchen", "state": "on"}]}
        verdict, value = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("ok", verdict)
        self.assertEqual("on", value)

    def test_ha_helper_state_eq_breach(self) -> None:
        rule = {"rule_kind": "ha_helper_state_comparison", "entity_id": "input_boolean.kitchen", "operator": "eq", "expected_value": "on"}
        ctx = {"ha_entities": [{"entity_id": "input_boolean.kitchen", "state": "off"}]}
        verdict, _ = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("breach", verdict)

    def test_ha_helper_entity_missing_unavailable(self) -> None:
        rule = {"rule_kind": "ha_helper_state_comparison", "entity_id": "input_boolean.kitchen", "operator": "eq", "expected_value": "on"}
        verdict, _ = _evaluate_declarative_rule(rule, {"ha_entities": []}, self._NOW, None)
        self.assertEqual("unavailable", verdict)

    def test_freshness_comparison_no_store_unavailable(self) -> None:
        rule = {"rule_kind": "publication_freshness_comparison", "publication_key": "monthly_cashflow", "operator": "lt", "threshold_hours": 48.0}
        verdict, _ = _evaluate_declarative_rule(rule, {}, self._NOW, None)
        self.assertEqual("unavailable", verdict)

    def test_unknown_rule_kind_unavailable(self) -> None:
        verdict, _ = _evaluate_declarative_rule({"rule_kind": "exec_python"}, {}, self._NOW, None)
        self.assertEqual("unavailable", verdict)
