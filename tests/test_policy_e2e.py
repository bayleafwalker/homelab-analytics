"""End-to-end test: operator creates a policy → evaluator runs it → PolicyResult
produced → result is visible via the HA policy evaluation surface.

This covers the full Stage 5 acceptance criterion:
  create policy definition → evaluate policy → PolicyResult produced →
  synthetic HA state published (exposed via /api/ha/policies/evaluate).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.homelab.pipelines.ha_policy import HaPolicyEvaluator
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


_VALUE_RULE = {
    "rule_kind": "publication_value_comparison",
    "publication_key": "monthly_cashflow",
    "field_name": "net",
    "operator": "lt",
    "threshold": 0,
    "unit": "currency",
}


def _build_cashflow_context(net: float) -> dict:
    return {
        "bridge_connected": False,
        "bridge_last_sync_at": None,
        "bridge_reconnect_count": 0,
        "budget_rows": [],
        "ha_entities": [],
        "publication_monthly_cashflow": [
            {"booking_month": "2026-04", "net": str(net), "income": "1000", "expense": "1500", "transaction_count": 5}
        ],
    }


class PolicyRegistryE2ETests(unittest.TestCase):
    def test_create_policy_evaluate_produce_result_visible_via_ha_surface(self) -> None:
        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            service = AccountTransactionService(
                landing_root=temp_root / "landing",
                metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
            )
            config_repository = IngestionConfigRepository(temp_root / "config.db")

            # Build evaluator wired to the same config_repository that CRUD uses
            context_holder: list[dict] = [_build_cashflow_context(-500)]
            evaluator = HaPolicyEvaluator(
                lambda: context_holder[0],
                policy_registry_store=config_repository,
            )

            app = create_app(
                service,
                config_repository=config_repository,
                ha_policy_evaluator=evaluator,
                enable_unsafe_admin=True,
            )

            with TestClient(app) as client:
                # Step 1: create an operator-authored policy
                create_resp = client.post(
                    "/control/policies",
                    json={
                        "display_name": "Negative cashflow alert",
                        "policy_kind": "publication_value_comparison",
                        "rule_document": _VALUE_RULE,
                        "creator": "e2e-test",
                    },
                )
                self.assertEqual(201, create_resp.status_code)
                policy_id = create_resp.json()["policy_id"]

                # Step 2: evaluate policies via HA surface (triggers PolicyResult production)
                eval_resp = client.post("/api/ha/policies/evaluate")
                self.assertEqual(200, eval_resp.status_code)

                # Step 3: registry policy appears in results (PolicyResult produced)
                policies = eval_resp.json()["policies"]
                ids = {p["id"] for p in policies}
                self.assertIn(policy_id, ids)

                # Step 4: verdict reflects the negative cashflow rule
                # net=-500, rule is "lt 0" (breach condition) → breach
                registry_result = next(p for p in policies if p["id"] == policy_id)
                self.assertEqual("breach", registry_result["verdict"])
                self.assertEqual("Negative cashflow alert", registry_result["name"])
                self.assertIn("evaluated_at", registry_result)

                # Step 5: synthetic state is published — verify via GET /api/ha/policies
                list_resp = client.get("/api/ha/policies")
                self.assertEqual(200, list_resp.status_code)
                list_ids = {p["id"] for p in list_resp.json()["policies"]}
                self.assertIn(policy_id, list_ids)

    def test_disabled_policy_not_in_evaluation_results(self) -> None:
        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            service = AccountTransactionService(
                landing_root=temp_root / "landing",
                metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
            )
            config_repository = IngestionConfigRepository(temp_root / "config.db")
            evaluator = HaPolicyEvaluator(
                lambda: _build_cashflow_context(-500),
                policy_registry_store=config_repository,
            )
            app = create_app(
                service,
                config_repository=config_repository,
                ha_policy_evaluator=evaluator,
                enable_unsafe_admin=True,
            )

            with TestClient(app) as client:
                create_resp = client.post(
                    "/control/policies",
                    json={
                        "display_name": "Disabled policy",
                        "policy_kind": "publication_value_comparison",
                        "rule_document": _VALUE_RULE,
                    },
                )
                policy_id = create_resp.json()["policy_id"]
                client.patch(f"/control/policies/{policy_id}", json={"enabled": False})

                eval_resp = client.post("/api/ha/policies/evaluate")
                ids = {p["id"] for p in eval_resp.json()["policies"]}
                self.assertNotIn(policy_id, ids)

    def test_ok_verdict_when_net_is_positive(self) -> None:
        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            service = AccountTransactionService(
                landing_root=temp_root / "landing",
                metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
            )
            config_repository = IngestionConfigRepository(temp_root / "config.db")
            evaluator = HaPolicyEvaluator(
                lambda: _build_cashflow_context(1200),
                policy_registry_store=config_repository,
            )
            app = create_app(
                service,
                config_repository=config_repository,
                ha_policy_evaluator=evaluator,
                enable_unsafe_admin=True,
            )

            with TestClient(app) as client:
                create_resp = client.post(
                    "/control/policies",
                    json={
                        "display_name": "Negative cashflow alert",
                        "policy_kind": "publication_value_comparison",
                        "rule_document": _VALUE_RULE,
                    },
                )
                policy_id = create_resp.json()["policy_id"]

                eval_resp = client.post("/api/ha/policies/evaluate")
                policies = eval_resp.json()["policies"]
                result = next(p for p in policies if p["id"] == policy_id)
                self.assertEqual("ok", result["verdict"])
