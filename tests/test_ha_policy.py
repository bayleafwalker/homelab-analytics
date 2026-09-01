"""Tests for HaPolicyEvaluator — Phase 4 policy evaluation engine.

Tests cover the three built-in policy functions (budget_status,
monthly_spend_rate, bridge_health) and the HaPolicyEvaluator class, using
only synchronous logic — no DB or network required.
"""
from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta

from packages.pipelines.ha_policy import (
    _BUILTIN_POLICIES,
    HaPolicyEvaluator,
    PolicyResult,
    _evaluate_bridge_health,
    _evaluate_budget_status,
    _evaluate_declarative_rule,
    _evaluate_monthly_spend_rate,
    _PolicyDef,
)
from packages.storage.control_plane import PolicyDefinitionRecord

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
        verdict, value, _ = _evaluate_budget_status({}, _NOW)
        self.assertEqual("unavailable", verdict)
        self.assertIsNone(value)

    def test_empty_list_returns_unavailable(self) -> None:
        verdict, value, _ = _evaluate_budget_status({"budget_rows": []}, _NOW)
        self.assertEqual("unavailable", verdict)
        self.assertIsNone(value)

    def test_low_utilization_returns_ok(self) -> None:
        verdict, _, _ = _evaluate_budget_status({"budget_rows": [_budget_row(50.0)]}, _NOW)
        self.assertEqual("ok", verdict)

    def test_at_warning_threshold_returns_warning(self) -> None:
        verdict, _, _ = _evaluate_budget_status({"budget_rows": [_budget_row(80.0)]}, _NOW)
        self.assertEqual("warning", verdict)

    def test_above_warning_threshold_returns_warning(self) -> None:
        verdict, _, _ = _evaluate_budget_status({"budget_rows": [_budget_row(95.0)]}, _NOW)
        self.assertEqual("warning", verdict)

    def test_over_100_pct_returns_breach(self) -> None:
        verdict, value, _ = _evaluate_budget_status({"budget_rows": [_budget_row(110.0)]}, _NOW)
        self.assertEqual("breach", verdict)
        self.assertIn("110.0%", value)

    def test_max_across_multiple_rows(self) -> None:
        rows = [_budget_row(30.0), _budget_row(105.0), _budget_row(70.0)]
        verdict, _, _ = _evaluate_budget_status({"budget_rows": rows}, _NOW)
        self.assertEqual("breach", verdict)

    def test_value_contains_percentage(self) -> None:
        _, value, _ = _evaluate_budget_status({"budget_rows": [_budget_row(55.0)]}, _NOW)
        self.assertIn("%", value)


# ---------------------------------------------------------------------------
# monthly_spend_rate
# ---------------------------------------------------------------------------

class MonthlySpendRateTests(unittest.TestCase):
    def test_no_rows_returns_unavailable(self) -> None:
        verdict, _, _ = _evaluate_monthly_spend_rate({"budget_rows": []}, _NOW)
        self.assertEqual("unavailable", verdict)

    def test_spend_below_pace_returns_ok(self) -> None:
        # 48.4% of month elapsed; spend at 30% → well under pace
        verdict, _, _ = _evaluate_monthly_spend_rate({"budget_rows": [_budget_row(30.0)]}, _NOW)
        self.assertEqual("ok", verdict)

    def test_spend_ahead_of_pace_returns_warning(self) -> None:
        # 48.4% elapsed; spend at 70% → more than 15 pct-points ahead of pace
        verdict, _, _ = _evaluate_monthly_spend_rate({"budget_rows": [_budget_row(70.0)]}, _NOW)
        self.assertEqual("warning", verdict)

    def test_over_budget_returns_breach(self) -> None:
        verdict, _, _ = _evaluate_monthly_spend_rate({"budget_rows": [_budget_row(105.0)]}, _NOW)
        self.assertEqual("breach", verdict)

    def test_value_contains_spent_and_elapsed(self) -> None:
        _, value, _ = _evaluate_monthly_spend_rate({"budget_rows": [_budget_row(40.0)]}, _NOW)
        self.assertIn("spent", value)
        self.assertIn("elapsed", value)


# ---------------------------------------------------------------------------
# bridge_health
# ---------------------------------------------------------------------------

class BridgeHealthTests(unittest.TestCase):
    def test_no_last_sync_returns_unavailable(self) -> None:
        verdict, _, _ = _evaluate_bridge_health({}, _NOW)
        self.assertEqual("unavailable", verdict)

    def test_none_last_sync_returns_unavailable(self) -> None:
        verdict, _, _ = _evaluate_bridge_health({"bridge_last_sync_at": None}, _NOW)
        self.assertEqual("unavailable", verdict)

    def test_recent_sync_returns_ok(self) -> None:
        recent = (_NOW - timedelta(seconds=60)).isoformat()
        verdict, _, _ = _evaluate_bridge_health({"bridge_last_sync_at": recent}, _NOW)
        self.assertEqual("ok", verdict)

    def test_stale_sync_returns_warning(self) -> None:
        stale = (_NOW - timedelta(seconds=400)).isoformat()
        verdict, _, _ = _evaluate_bridge_health({"bridge_last_sync_at": stale}, _NOW)
        self.assertEqual("warning", verdict)

    def test_exactly_at_threshold_returns_warning(self) -> None:
        at_threshold = (_NOW - timedelta(seconds=300)).isoformat()
        # >300 is stale; exactly 300 is still ok (not strictly >)
        verdict, _, _ = _evaluate_bridge_health({"bridge_last_sync_at": at_threshold}, _NOW)
        self.assertEqual("ok", verdict)

    def test_invalid_timestamp_returns_unavailable(self) -> None:
        verdict, _, _ = _evaluate_bridge_health({"bridge_last_sync_at": "not-a-date"}, _NOW)
        self.assertEqual("unavailable", verdict)

    def test_value_contains_seconds(self) -> None:
        recent = (_NOW - timedelta(seconds=45)).isoformat()
        _, value, _ = _evaluate_bridge_health({"bridge_last_sync_at": recent}, _NOW)
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
        verdict, value, _ = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("breach", verdict)

    def test_publication_value_comparison_ok(self) -> None:
        # operator "lt 0" is the breach condition; net=1200 does not breach it
        rule = {"rule_kind": "publication_value_comparison", "publication_key": "monthly_cashflow", "field_name": "net", "operator": "lt", "threshold": 0}
        ctx = {"publication_monthly_cashflow": [{"net": "1200"}]}
        verdict, value, _ = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("ok", verdict)

    def test_publication_value_comparison_missing_data_unavailable(self) -> None:
        rule = {"rule_kind": "publication_value_comparison", "publication_key": "monthly_cashflow", "field_name": "net", "operator": "lt", "threshold": 0}
        verdict, _, _ = _evaluate_declarative_rule(rule, {}, self._NOW, None)
        self.assertEqual("unavailable", verdict)

    def test_ha_helper_state_eq_ok(self) -> None:
        rule = {"rule_kind": "ha_helper_state_comparison", "entity_id": "input_boolean.kitchen", "operator": "eq", "expected_value": "on"}
        ctx = {"ha_entities": [{"entity_id": "input_boolean.kitchen", "state": "on"}]}
        verdict, value, _ = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("ok", verdict)
        self.assertEqual("on", value)

    def test_ha_helper_state_eq_breach(self) -> None:
        rule = {"rule_kind": "ha_helper_state_comparison", "entity_id": "input_boolean.kitchen", "operator": "eq", "expected_value": "on"}
        ctx = {"ha_entities": [{"entity_id": "input_boolean.kitchen", "state": "off"}]}
        verdict, _, _ = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("breach", verdict)

    def test_ha_helper_entity_missing_unavailable(self) -> None:
        rule = {"rule_kind": "ha_helper_state_comparison", "entity_id": "input_boolean.kitchen", "operator": "eq", "expected_value": "on"}
        verdict, _, _ = _evaluate_declarative_rule(rule, {"ha_entities": []}, self._NOW, None)
        self.assertEqual("unavailable", verdict)

    def test_freshness_comparison_no_store_unavailable(self) -> None:
        rule = {"rule_kind": "publication_freshness_comparison", "publication_key": "monthly_cashflow", "operator": "lt", "threshold_hours": 48.0}
        verdict, _, _ = _evaluate_declarative_rule(rule, {}, self._NOW, None)
        self.assertEqual("unavailable", verdict)

    def test_unknown_rule_kind_unavailable(self) -> None:
        verdict, _, _ = _evaluate_declarative_rule({"rule_kind": "exec_python"}, {}, self._NOW, None)
        self.assertEqual("unavailable", verdict)


class DeclarativeRuleReasonTests(unittest.TestCase):
    """Every verdict states why it holds, in terms an operator can act on."""

    _NOW = datetime.now(UTC)

    def _value_rule(self, **overrides: object) -> dict:
        rule = {
            "rule_kind": "publication_value_comparison",
            "publication_key": "monthly_cashflow",
            "field_name": "net",
            "operator": "lt",
            "threshold": 0,
        }
        rule.update(overrides)
        return rule

    def test_breach_reason_names_value_comparison_and_threshold(self) -> None:
        ctx = {"publication_monthly_cashflow": [{"net": "-500"}]}
        verdict, value, reason = _evaluate_declarative_rule(
            self._value_rule(unit="EUR"), ctx, self._NOW, None
        )
        self.assertEqual("breach", verdict)
        self.assertEqual("-500.0", value)
        assert reason is not None
        # The field, the observed value, the comparison and the threshold are
        # all present, so the operator can see what fired without the rule.
        self.assertIn("net", reason)
        self.assertIn("-500", reason)
        self.assertIn("less than", reason)
        self.assertIn("0", reason)
        self.assertIn("EUR", reason)
        self.assertNotIn("not less than", reason)

    def test_ok_reason_states_the_threshold_was_not_crossed(self) -> None:
        ctx = {"publication_monthly_cashflow": [{"net": "1200"}]}
        verdict, _, reason = _evaluate_declarative_rule(
            self._value_rule(), ctx, self._NOW, None
        )
        self.assertEqual("ok", verdict)
        assert reason is not None
        self.assertIn("not less than", reason)

    def test_reason_distinguishes_the_unavailable_causes(self) -> None:
        no_rows = _evaluate_declarative_rule(self._value_rule(), {}, self._NOW, None)[2]
        missing_field = _evaluate_declarative_rule(
            self._value_rule(),
            {"publication_monthly_cashflow": [{"other": "1"}]},
            self._NOW,
            None,
        )[2]
        non_numeric = _evaluate_declarative_rule(
            self._value_rule(),
            {"publication_monthly_cashflow": [{"net": "abc"}]},
            self._NOW,
            None,
        )[2]
        invalid_doc = _evaluate_declarative_rule(
            {"rule_kind": "exec_python"}, {}, self._NOW, None
        )[2]
        reasons = [no_rows, missing_field, non_numeric, invalid_doc]
        for reason in reasons:
            self.assertTrue(reason)
        # A single "unavailable" verdict is useless if every cause reads the
        # same; each must be separately diagnosable.
        self.assertEqual(len(reasons), len(set(reasons)))
        assert no_rows is not None and missing_field is not None
        assert non_numeric is not None
        self.assertIn("no rows", no_rows)
        self.assertIn("net", missing_field)
        self.assertIn("not numeric", non_numeric)

    def test_helper_state_reason_names_entity_state_and_expectation(self) -> None:
        rule = {
            "rule_kind": "ha_helper_state_comparison",
            "entity_id": "input_boolean.kitchen",
            "operator": "eq",
            "expected_value": "on",
        }
        ctx = {"ha_entities": [{"entity_id": "input_boolean.kitchen", "state": "off"}]}
        verdict, _, reason = _evaluate_declarative_rule(rule, ctx, self._NOW, None)
        self.assertEqual("breach", verdict)
        assert reason is not None
        self.assertIn("input_boolean.kitchen", reason)
        self.assertIn("'off'", reason)
        self.assertIn("not equal", reason)

    def test_missing_entity_reason_names_the_entity(self) -> None:
        rule = {
            "rule_kind": "ha_helper_state_comparison",
            "entity_id": "input_boolean.kitchen",
            "operator": "eq",
            "expected_value": "on",
        }
        _, _, reason = _evaluate_declarative_rule(
            rule, {"ha_entities": []}, self._NOW, None
        )
        assert reason is not None
        self.assertIn("input_boolean.kitchen", reason)
        self.assertIn("not found", reason)

    def test_reason_is_serialized_on_the_api_payload(self) -> None:
        result = PolicyResult(
            id="p",
            name="P",
            description="",
            verdict="breach",
            value="-500.0",
            evaluated_at=self._NOW.isoformat(),
            reason="net is -500 EUR, which is less than the threshold 0 EUR.",
        )
        self.assertEqual(
            "net is -500 EUR, which is less than the threshold 0 EUR.",
            result.to_dict()["reason"],
        )

    def test_reason_defaults_to_none_when_not_supplied(self) -> None:
        result = PolicyResult(
            id="p",
            name="P",
            description="",
            verdict="ok",
            value=None,
            evaluated_at=self._NOW.isoformat(),
        )
        self.assertIsNone(result.to_dict()["reason"])


# ---------------------------------------------------------------------------
# Snapshot authority model (A1)
# ---------------------------------------------------------------------------

_HELPER_RULE = {
    "rule_kind": "ha_helper_state_comparison",
    "entity_id": "input_boolean.hla_test_flag",
    "operator": "eq",
    "expected_value": "on",
}


def _registry_record(policy_id: str = "op_test_flag") -> PolicyDefinitionRecord:
    return PolicyDefinitionRecord(
        policy_id=policy_id,
        display_name="Test Flag",
        policy_kind="declarative_rule",
        rule_schema_version="1.0",
        rule_document=json.dumps(_HELPER_RULE),
        enabled=True,
        source_kind="operator",
        description="Operator test policy.",
        creator="operator",
        created_at=_NOW,
        updated_at=_NOW,
    )


class _StubRegistryStore:
    def __init__(self, records: list | None = None) -> None:
        self.records = records if records is not None else []
        self.fail = False

    def list_policy_definitions(self, enabled_only: bool = False) -> list:
        if self.fail:
            raise RuntimeError("registry down")
        return list(self.records)


class AuthoritySnapshotModelTests(unittest.TestCase):
    _CTX = {
        "ha_entities": [
            {"entity_id": "input_boolean.hla_test_flag", "state": "on"}
        ]
    }

    def _registry_ids(self, results: list[PolicyResult]) -> list[str]:
        builtin_ids = {policy.id for policy in _BUILTIN_POLICIES}
        return [result.id for result in results if result.id not in builtin_ids]

    def test_live_registry_mode(self) -> None:
        store = _StubRegistryStore([_registry_record()])
        evaluator = HaPolicyEvaluator(lambda: self._CTX, policy_registry_store=store)
        results = evaluator.evaluate()
        self.assertEqual(["op_test_flag"], self._registry_ids(results))
        status = evaluator.get_authority_status()
        self.assertEqual("registry", status.mode)
        self.assertTrue(status.registry_configured)
        self.assertEqual(1, status.snapshot_version)
        registry_result = next(r for r in results if r.id == "op_test_flag")
        self.assertEqual("registry", registry_result.metadata["authority_mode"])

    def test_outage_with_prior_success_degrades_to_snapshot(self) -> None:
        store = _StubRegistryStore([_registry_record()])
        evaluator = HaPolicyEvaluator(lambda: self._CTX, policy_registry_store=store)
        evaluator.evaluate()
        store.fail = True
        results = evaluator.evaluate()
        self.assertEqual(["op_test_flag"], self._registry_ids(results))
        status = evaluator.get_authority_status()
        self.assertEqual("snapshot", status.mode)
        self.assertIsNotNone(status.last_error)
        registry_result = next(r for r in results if r.id == "op_test_flag")
        self.assertEqual("snapshot", registry_result.metadata["authority_mode"])

    def test_operator_disabled_policy_not_revived_by_outage(self) -> None:
        store = _StubRegistryStore([_registry_record()])
        evaluator = HaPolicyEvaluator(lambda: self._CTX, policy_registry_store=store)
        evaluator.evaluate()
        # Operator disables the policy: enabled-only listing becomes empty.
        store.records = []
        evaluator.evaluate()
        # Registry outage must evaluate the post-disable snapshot, not revive.
        store.fail = True
        results = evaluator.evaluate()
        self.assertEqual([], self._registry_ids(results))
        self.assertEqual("snapshot", evaluator.get_authority_status().mode)

    def test_outage_without_snapshot_is_unavailable(self) -> None:
        store = _StubRegistryStore([_registry_record()])
        store.fail = True
        evaluator = HaPolicyEvaluator(lambda: self._CTX, policy_registry_store=store)
        results = evaluator.evaluate()
        self.assertEqual([], self._registry_ids(results))
        self.assertEqual("unavailable", evaluator.get_authority_status().mode)

    def test_no_store_reports_unconfigured_unavailable(self) -> None:
        evaluator = HaPolicyEvaluator(lambda: self._CTX)
        evaluator.evaluate()
        status = evaluator.get_authority_status()
        self.assertEqual("unavailable", status.mode)
        self.assertFalse(status.registry_configured)

    def test_snapshot_version_increments_only_on_change(self) -> None:
        store = _StubRegistryStore([_registry_record()])
        evaluator = HaPolicyEvaluator(lambda: self._CTX, policy_registry_store=store)
        evaluator.evaluate()
        evaluator.evaluate()
        self.assertEqual(1, evaluator.get_authority_status().snapshot_version)
        store.records = [_registry_record("op_other")]
        evaluator.evaluate()
        self.assertEqual(2, evaluator.get_authority_status().snapshot_version)

    def test_snapshot_persists_across_restart(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.json"
            store = _StubRegistryStore([_registry_record()])
            first = HaPolicyEvaluator(
                lambda: self._CTX,
                policy_registry_store=store,
                snapshot_path=snapshot_path,
            )
            first.evaluate()
            self.assertTrue(snapshot_path.exists())

            # New process: fresh evaluator, registry down from the start.
            store.fail = True
            second = HaPolicyEvaluator(
                lambda: self._CTX,
                policy_registry_store=store,
                snapshot_path=snapshot_path,
            )
            results = second.evaluate()
            self.assertEqual(["op_test_flag"], self._registry_ids(results))
            self.assertEqual("snapshot", second.get_authority_status().mode)


class ProductionWiringTests(unittest.TestCase):
    """A registry policy evaluates through the production wiring path."""

    def test_registry_policy_evaluates_via_build_ha_startup_runtime(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace

        from apps.api.ha_startup import build_ha_startup_runtime
        from packages.shared.settings import AppSettings
        from packages.storage.control_plane import PolicyDefinitionCreate
        from packages.storage.ingestion_config import IngestionConfigRepository

        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            settings = AppSettings(
                data_dir=temp_root,
                landing_root=temp_root / "landing",
                metadata_database_path=temp_root / "metadata" / "runs.db",
                account_transactions_inbox_dir=temp_root / "inbox",
                processed_files_dir=temp_root / "processed",
                failed_files_dir=temp_root / "failed",
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )
            config_repository = IngestionConfigRepository(temp_root / "config.db")
            config_repository.create_policy_definition(
                PolicyDefinitionCreate(
                    policy_id="op_wired_flag",
                    display_name="Wired Flag",
                    policy_kind="declarative_rule",
                    rule_schema_version="1.0",
                    rule_document=json.dumps(_HELPER_RULE),
                    enabled=True,
                    source_kind="operator",
                    description="Wired through production startup.",
                    creator="operator",
                )
            )
            transformation_service = SimpleNamespace(
                get_budget_progress_current=lambda: [],
                get_ha_entities=lambda: [
                    {"entity_id": "input_boolean.hla_test_flag", "state": "on"}
                ],
                ingest_ha_states=lambda *args, **kwargs: None,
            )
            runtime = build_ha_startup_runtime(
                settings,
                transformation_service=transformation_service,
                reporting_service=SimpleNamespace(),
                capability_packs=(),
                control_plane_store=config_repository,
            )
            results = runtime.policy_evaluator.evaluate()
            self.assertIn(
                "op_wired_flag", [result.id for result in results]
            )
            status = runtime.policy_evaluator.get_authority_status()
            self.assertEqual("registry", status.mode)
            self.assertTrue(
                (temp_root / "ha-policy-effective-snapshot.json").exists()
            )


# ---------------------------------------------------------------------------
# Builtin seed lifecycle (A1)
# ---------------------------------------------------------------------------

class SeedLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from packages.storage.ingestion_config import IngestionConfigRepository

        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.store = IngestionConfigRepository(root / "config.db")
        self.state_path = root / "seed-state.json"

    def _seed(self, policy_id: str = "seed_flag", description: str = "Seeded.", enabled: bool = True):
        from packages.pipelines.ha_policy import PolicySeedDefinition

        return PolicySeedDefinition(
            policy_id=policy_id,
            display_name="Seeded Flag",
            description=description,
            rule_document=dict(_HELPER_RULE),
            enabled=enabled,
        )

    def _ensure(self, seeds):
        from packages.pipelines.ha_policy import ensure_builtin_policies

        return ensure_builtin_policies(
            self.store, seeds=seeds, seed_state_path=self.state_path
        )

    def test_create_installs_builtin_row_and_state(self) -> None:
        summary = self._ensure([self._seed()])
        self.assertEqual(["seed_flag"], summary["created"])
        record = self.store.get_policy_definition("seed_flag")
        self.assertEqual("builtin", record.source_kind)
        self.assertTrue(record.enabled)
        self.assertTrue(self.state_path.exists())

    def test_second_run_is_idempotent(self) -> None:
        self._ensure([self._seed()])
        summary = self._ensure([self._seed()])
        self.assertEqual([], summary["created"])
        self.assertEqual(["seed_flag"], summary["unchanged"])
        self.assertEqual(1, len(self.store.list_policy_definitions()))

    def test_concurrent_start_produces_one_row(self) -> None:
        from pathlib import Path

        # Two "processes": separate seed-state sidecars, same registry.
        other_state = Path(self._tmp.name) / "other-seed-state.json"
        from packages.pipelines.ha_policy import ensure_builtin_policies

        self._ensure([self._seed()])
        summary = ensure_builtin_policies(
            self.store, seeds=[self._seed()], seed_state_path=other_state
        )
        self.assertEqual([], summary["created"])
        self.assertEqual(["seed_flag"], summary["unchanged"])
        self.assertEqual(1, len(self.store.list_policy_definitions()))

    def test_upgrade_applies_without_touching_enabled(self) -> None:
        from packages.storage.control_plane import PolicyDefinitionUpdate

        self._ensure([self._seed(description="v1")])
        # Operator disables the seeded policy (operator-owned state).
        self.store.update_policy_definition(
            "seed_flag", PolicyDefinitionUpdate(enabled=False)
        )
        summary = self._ensure([self._seed(description="v2")])
        self.assertEqual(["seed_flag"], summary["upgraded"])
        record = self.store.get_policy_definition("seed_flag")
        self.assertEqual("v2", record.description)
        self.assertFalse(record.enabled)

    def test_operator_edit_blocks_upgrade(self) -> None:
        from packages.storage.control_plane import PolicyDefinitionUpdate

        self._ensure([self._seed(description="v1")])
        edited_rule = dict(_HELPER_RULE)
        edited_rule["expected_value"] = "off"
        self.store.update_policy_definition(
            "seed_flag",
            PolicyDefinitionUpdate(rule_document=json.dumps(edited_rule)),
        )
        summary = self._ensure([self._seed(description="v2")])
        self.assertEqual(["seed_flag"], summary["skipped_operator_edited"])
        record = self.store.get_policy_definition("seed_flag")
        self.assertIn('"off"', record.rule_document)

    def test_operator_delete_is_tombstoned(self) -> None:
        self._ensure([self._seed()])
        self.store.delete_policy_definition("seed_flag")
        summary = self._ensure([self._seed()])
        self.assertEqual(["seed_flag"], summary["skipped_deleted"])
        with self.assertRaises(KeyError):
            self.store.get_policy_definition("seed_flag")

    def test_removed_seed_is_orphaned_not_deleted(self) -> None:
        self._ensure([self._seed()])
        summary = self._ensure([])
        self.assertEqual(["seed_flag"], summary["orphaned"])
        self.store.get_policy_definition("seed_flag")  # still present

    def test_preexisting_operator_row_is_conflict_and_untouched(self) -> None:
        from packages.storage.control_plane import PolicyDefinitionCreate

        self.store.create_policy_definition(
            PolicyDefinitionCreate(
                policy_id="seed_flag",
                display_name="Operator Owned",
                policy_kind="declarative_rule",
                rule_schema_version="1.0",
                rule_document=json.dumps(_HELPER_RULE),
                enabled=True,
                source_kind="operator",
                description="Operator's own policy.",
                creator="operator",
            )
        )
        summary = self._ensure([self._seed()])
        self.assertEqual(["seed_flag"], summary["conflict"])
        record = self.store.get_policy_definition("seed_flag")
        self.assertEqual("operator", record.source_kind)
        self.assertEqual("Operator Owned", record.display_name)


# ---------------------------------------------------------------------------
# Publication snapshot semantics (A1)
# ---------------------------------------------------------------------------

_CASHFLOW_RULE = {
    "rule_kind": "publication_value_comparison",
    "publication_key": "monthly_cashflow",
    "field_name": "net",
    "operator": "lt",
    "threshold": 0,
    "unit": "currency",
}


def _cashflow_record(policy_id: str = "op_cashflow") -> PolicyDefinitionRecord:
    return PolicyDefinitionRecord(
        policy_id=policy_id,
        display_name="Cashflow Guard",
        policy_kind="declarative_rule",
        rule_schema_version="1.0",
        rule_document=json.dumps(_CASHFLOW_RULE),
        enabled=True,
        source_kind="operator",
        description="Negative monthly cashflow.",
        creator="operator",
        created_at=_NOW,
        updated_at=_NOW,
    )


class _StubConfidenceSnapshot:
    def __init__(self, freshness_state: str) -> None:
        self.confidence_verdict = "TRUSTWORTHY"
        self.freshness_state = freshness_state
        self.completeness_pct = 100
        self.assessed_at = _NOW


class _StubControlPlaneStore:
    def __init__(self, freshness_state: str | None = None) -> None:
        self.freshness_state = freshness_state

    def list_publication_confidence_snapshots(self, **kwargs):
        if self.freshness_state is None:
            return []
        return [_StubConfidenceSnapshot(self.freshness_state)]


class PublicationSnapshotSemanticsTests(unittest.TestCase):
    def test_batched_deduplicated_publication_fetch(self) -> None:
        calls: list[frozenset[str]] = []

        def publication_fetch(keys: frozenset[str]) -> dict:
            calls.append(keys)
            return {
                "publication_monthly_cashflow": [
                    {"booking_month": "2026-08", "net": "-250"}
                ]
            }

        store = _StubRegistryStore(
            [_cashflow_record("op_a"), _cashflow_record("op_b")]
        )
        evaluator = HaPolicyEvaluator(
            lambda: {},
            policy_registry_store=store,
            publication_fetch_fn=publication_fetch,
        )
        results = evaluator.evaluate()
        # Two policies referencing one publication cause one bounded fetch.
        self.assertEqual(1, len(calls))
        self.assertEqual(frozenset({"monthly_cashflow"}), calls[0])
        verdicts = {r.id: r.verdict for r in results if r.id.startswith("op_")}
        self.assertEqual({"op_a": "breach", "op_b": "breach"}, verdicts)

    def test_all_policies_observe_same_snapshot(self) -> None:
        # The fetch returns one batch; both policies must see identical rows
        # even if the underlying source changes between accesses.
        state = {"net": "-250"}

        def publication_fetch(keys: frozenset[str]) -> dict:
            rows = [{"booking_month": "2026-08", "net": state["net"]}]
            state["net"] = "999"  # mutate after the single batch read
            return {"publication_monthly_cashflow": rows}

        store = _StubRegistryStore(
            [_cashflow_record("op_a"), _cashflow_record("op_b")]
        )
        evaluator = HaPolicyEvaluator(
            lambda: {},
            policy_registry_store=store,
            publication_fetch_fn=publication_fetch,
        )
        results = evaluator.evaluate()
        values = {r.id: r.value for r in results if r.id.startswith("op_")}
        self.assertEqual({"op_a": "-250.0", "op_b": "-250.0"}, values)

    def test_missing_publication_data_is_explicit_unavailable(self) -> None:
        store = _StubRegistryStore([_cashflow_record()])
        evaluator = HaPolicyEvaluator(
            lambda: {},
            policy_registry_store=store,
            publication_fetch_fn=lambda keys: {},
        )
        results = evaluator.evaluate()
        result = next(r for r in results if r.id == "op_cashflow")
        self.assertEqual("unavailable", result.verdict)

    def test_stale_publication_data_is_explicit_unavailable(self) -> None:
        store = _StubRegistryStore([_cashflow_record()])
        evaluator = HaPolicyEvaluator(
            lambda: {},
            control_plane_store=_StubControlPlaneStore("OVERDUE"),
            policy_registry_store=store,
            publication_fetch_fn=lambda keys: {
                "publication_monthly_cashflow": [{"net": "-250"}]
            },
        )
        results = evaluator.evaluate()
        result = next(r for r in results if r.id == "op_cashflow")
        self.assertEqual("unavailable", result.verdict)
        # The staleness is the reason; the value stays the measurement that was
        # actually read, so the two carry distinct information.
        self.assertIn("stale input", result.reason or "")
        self.assertIn("OVERDUE", result.reason or "")
        self.assertEqual("-250.0", result.value)
        self.assertEqual("OVERDUE", result.input_freshness.freshness_state)

    def test_fresh_publication_confidence_attached_to_result(self) -> None:
        store = _StubRegistryStore([_cashflow_record()])
        evaluator = HaPolicyEvaluator(
            lambda: {},
            control_plane_store=_StubControlPlaneStore("CURRENT"),
            policy_registry_store=store,
            publication_fetch_fn=lambda keys: {
                "publication_monthly_cashflow": [{"net": "-250"}]
            },
        )
        results = evaluator.evaluate()
        result = next(r for r in results if r.id == "op_cashflow")
        self.assertEqual("breach", result.verdict)
        self.assertEqual("CURRENT", result.input_freshness.freshness_state)
        self.assertEqual(
            "monthly_cashflow", result.metadata["publication_key"]
        )


# ---------------------------------------------------------------------------
# Builtin parity under registry presence (A1 shadow comparison)
# ---------------------------------------------------------------------------

class BuiltinParityTests(unittest.TestCase):
    """The four code built-ins are not demoted (none is expressible
    behavior-identically in the shipped rule kinds), so the shadow
    comparison pins parity instead: registry presence must never change
    builtin output, and a registry row can never shadow a builtin id."""

    _CTX = {
        "bridge_connected": True,
        "bridge_last_sync_at": _NOW.isoformat(),
        "bridge_reconnect_count": 0,
        "budget_rows": [_budget_row(85.0)],
        "ha_entities": [
            {
                "entity_id": "input_boolean.hla_kitchen_light_request",
                "last_state": "on",
            }
        ],
    }

    def _builtin_output(self, evaluator: HaPolicyEvaluator) -> dict:
        builtin_ids = {policy.id for policy in _BUILTIN_POLICIES}
        return {
            r.id: (r.verdict, r.value, r.approval_required)
            for r in evaluator.evaluate()
            if r.id in builtin_ids
        }

    def test_registry_presence_does_not_change_builtin_output(self) -> None:
        without_registry = HaPolicyEvaluator(lambda: dict(self._CTX))
        with_registry = HaPolicyEvaluator(
            lambda: dict(self._CTX),
            policy_registry_store=_StubRegistryStore(
                [_registry_record(), _cashflow_record()]
            ),
        )
        self.assertEqual(
            self._builtin_output(without_registry),
            self._builtin_output(with_registry),
        )

    def test_registry_row_cannot_shadow_builtin_id(self) -> None:
        # An operator/seeded row reusing a builtin id must be skipped, so no
        # policy id ever appears twice in one evaluation.
        shadowing = _registry_record("budget_status")
        evaluator = HaPolicyEvaluator(
            lambda: dict(self._CTX),
            policy_registry_store=_StubRegistryStore([shadowing]),
        )
        results = evaluator.evaluate()
        ids = [r.id for r in results]
        self.assertEqual(len(ids), len(set(ids)))
        budget = next(r for r in results if r.id == "budget_status")
        # The builtin's semantics (85% -> warning), not the helper rule's.
        self.assertEqual("warning", budget.verdict)

    def test_all_four_builtins_present_with_registry(self) -> None:
        evaluator = HaPolicyEvaluator(
            lambda: dict(self._CTX),
            policy_registry_store=_StubRegistryStore([_registry_record()]),
        )
        results = evaluator.evaluate()
        builtin_ids = {policy.id for policy in _BUILTIN_POLICIES}
        self.assertTrue(builtin_ids <= {r.id for r in results})


class PreviewEvaluationTests(unittest.TestCase):
    """Preview runs the real evaluation path without persisting anything."""

    def test_preview_returns_verdict_and_reason_for_unsaved_rule(self) -> None:
        evaluator = HaPolicyEvaluator(
            lambda: {},
            publication_fetch_fn=lambda keys: {
                "publication_monthly_cashflow": [{"net": "-250"}]
            },
        )
        result = evaluator.evaluate_document(dict(_CASHFLOW_RULE))
        self.assertEqual("breach", result.verdict)
        self.assertEqual("-250.0", result.value)
        assert result.reason is not None
        self.assertIn("net", result.reason)
        self.assertTrue(result.metadata["preview"])

    def test_preview_fetches_only_the_referenced_publication(self) -> None:
        calls: list[frozenset[str]] = []

        def publication_fetch(keys: frozenset[str]) -> dict:
            calls.append(keys)
            return {"publication_monthly_cashflow": [{"net": "1200"}]}

        evaluator = HaPolicyEvaluator(
            lambda: {}, publication_fetch_fn=publication_fetch
        )
        result = evaluator.evaluate_document(dict(_CASHFLOW_RULE))
        self.assertEqual([frozenset({"monthly_cashflow"})], calls)
        self.assertEqual("ok", result.verdict)

    def test_preview_honours_the_staleness_rule(self) -> None:
        # A preview must never look healthier than the saved policy would be.
        evaluator = HaPolicyEvaluator(
            lambda: {},
            control_plane_store=_StubControlPlaneStore("OVERDUE"),
            publication_fetch_fn=lambda keys: {
                "publication_monthly_cashflow": [{"net": "-250"}]
            },
        )
        result = evaluator.evaluate_document(dict(_CASHFLOW_RULE))
        self.assertEqual("unavailable", result.verdict)
        self.assertIn("stale input", result.reason or "")
        self.assertEqual("-250.0", result.value)

    def test_preview_does_not_consult_or_mutate_the_registry(self) -> None:
        store = _StubRegistryStore([_cashflow_record("already_saved")])
        evaluator = HaPolicyEvaluator(
            lambda: {},
            policy_registry_store=store,
            publication_fetch_fn=lambda keys: {
                "publication_monthly_cashflow": [{"net": "-250"}]
            },
        )
        result = evaluator.evaluate_document(dict(_CASHFLOW_RULE))
        self.assertEqual("preview", result.id)
        # The saved policy set is untouched by a preview.
        self.assertEqual(
            ["already_saved"],
            [record.policy_id for record in store.list_policy_definitions()],
        )

    def test_preview_of_invalid_document_is_unavailable_with_a_reason(self) -> None:
        evaluator = HaPolicyEvaluator(lambda: {})
        result = evaluator.evaluate_document({"rule_kind": "exec_python"})
        self.assertEqual("unavailable", result.verdict)
        self.assertTrue(result.reason)
