"""Tests for approval-gated HA action proposals."""
from __future__ import annotations

import unittest

from packages.domains.homelab.pipelines.ha_action_proposals import ProposalProvenance
from packages.pipelines.ha_action_proposals import ApprovalActionRegistry


class ApprovalActionRegistryTests(unittest.TestCase):
    def test_register_creates_pending_proposal(self) -> None:
        registry = ApprovalActionRegistry()
        proposal = registry.register(
            policy_id="device_control",
            policy_name="Device Control",
            verdict="warning",
            value="needs approval",
            notification_id="homelab_analytics_approval_device_control",
            action_id="homelab_analytics_approval_device_control",
        )

        self.assertEqual(proposal.status, "pending")
        self.assertEqual(proposal.action_id, "homelab_analytics_approval_device_control")
        self.assertEqual(proposal.source_kind, "policy")
        self.assertIsNone(proposal.source_key)
        self.assertIsNone(proposal.created_by)
        self.assertEqual(len(registry.list_pending()), 1)
        self.assertEqual(registry.get_status()["pending"], 1)

    def test_approve_updates_status(self) -> None:
        registry = ApprovalActionRegistry()
        proposal = registry.register(
            policy_id="device_control",
            policy_name="Device Control",
            verdict="warning",
            value=None,
            notification_id="homelab_analytics_approval_device_control",
            action_id="homelab_analytics_approval_device_control",
        )

        approved = registry.approve(proposal.action_id)
        self.assertEqual(approved.status, "approved")
        self.assertIsNotNone(approved.approved_at)
        self.assertEqual(registry.get_status()["approved"], 1)
        self.assertEqual(registry.list_pending(), [])

    def test_dismiss_updates_status(self) -> None:
        registry = ApprovalActionRegistry()
        proposal = registry.register(
            policy_id="device_control",
            policy_name="Device Control",
            verdict="warning",
            value=None,
            notification_id="homelab_analytics_approval_device_control",
            action_id="homelab_analytics_approval_device_control",
        )

        dismissed = registry.dismiss(proposal.action_id)
        self.assertEqual(dismissed.status, "dismissed")
        self.assertIsNotNone(dismissed.dismissed_at)
        self.assertEqual(registry.get_status()["dismissed"], 1)
        self.assertEqual(registry.list_pending(), [])

    def test_to_dict_includes_metadata(self) -> None:
        registry = ApprovalActionRegistry()
        proposal = registry.register(
            policy_id="device_control",
            policy_name="Device Control",
            verdict="warning",
            value=None,
            notification_id=None,
            action_id="homelab_analytics_approval_device_control",
            metadata={"source": "test"},
            source_kind="assistant",
            source_key="publication.monthly-cashflow",
            source_summary="Draft approval to review monthly cash flow.",
            created_by="assistant",
        )

        payload = proposal.to_dict()
        self.assertEqual(payload["metadata"]["source"], "test")
        self.assertEqual(payload["notification_id"], "homelab_analytics_approval_device_control")
        self.assertEqual(payload["source_kind"], "assistant")
        self.assertEqual(payload["source_key"], "publication.monthly-cashflow")
        self.assertEqual(payload["source_summary"], "Draft approval to review monthly cash flow.")
        self.assertEqual(payload["created_by"], "assistant")


class ProposalProvenanceTests(unittest.TestCase):
    def test_provenance_defaults(self) -> None:
        prov = ProposalProvenance()
        self.assertEqual(prov.publication_keys, [])
        self.assertIsNone(prov.confidence_verdict_at_draft)
        self.assertIsNone(prov.freshness_state_at_draft)
        self.assertIsNone(prov.assessed_at)

    def test_provenance_to_dict(self) -> None:
        prov = ProposalProvenance(
            publication_keys=["mart_monthly_cashflow", "mart_spend_by_category_monthly"],
            confidence_verdict_at_draft="trustworthy",
            freshness_state_at_draft="current",
            assessed_at="2026-04-06T12:00:00+00:00",
        )
        d = prov.to_dict()
        self.assertEqual(d["publication_keys"], ["mart_monthly_cashflow", "mart_spend_by_category_monthly"])
        self.assertEqual(d["confidence_verdict_at_draft"], "trustworthy")
        self.assertEqual(d["freshness_state_at_draft"], "current")
        self.assertEqual(d["assessed_at"], "2026-04-06T12:00:00+00:00")

    def test_proposal_to_dict_with_provenance(self) -> None:
        registry = ApprovalActionRegistry()
        prov = ProposalProvenance(
            publication_keys=["mart_monthly_cashflow"],
            confidence_verdict_at_draft="degraded",
            freshness_state_at_draft="stale",
            assessed_at="2026-04-06T12:00:00+00:00",
        )
        proposal = registry.register(
            policy_id="budget_alert",
            policy_name="Budget Alert",
            verdict="warning",
            value=None,
            notification_id=None,
            source_kind="assistant",
            provenance=prov,
        )
        d = proposal.to_dict()
        self.assertIsNotNone(d["provenance"])
        assert d["provenance"] is not None
        self.assertEqual(d["provenance"]["confidence_verdict_at_draft"], "degraded")
        self.assertEqual(d["provenance"]["publication_keys"], ["mart_monthly_cashflow"])

    def test_proposal_to_dict_without_provenance(self) -> None:
        registry = ApprovalActionRegistry()
        proposal = registry.register(
            policy_id="device_control",
            policy_name="Device Control",
            verdict="ok",
            value=None,
            notification_id=None,
        )
        d = proposal.to_dict()
        self.assertIsNone(d["provenance"])


if __name__ == "__main__":
    unittest.main()
