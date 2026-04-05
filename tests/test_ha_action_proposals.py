"""Tests for approval-gated HA action proposals."""
from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
