"""Tests for Stage 6 integration adapter contracts.

Covers:
- AdapterManifest field validation and immutability
- AdapterRuntimeStatus as_dict() serialisation
- IngestAdapter / PublishAdapter / ActionAdapter protocol conformance
- HaIngestAdapter, HaMqttPublishAdapter, HaActionAdapter wrapper behaviour
- get_runtime_status() on the HA workers
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from packages.adapters.contracts import (
    ActionAdapter,
    AdapterDirection,
    AdapterManifest,
    AdapterRuntimeStatus,
    IngestAdapter,
    PublishAdapter,
)
from packages.adapters.ha_adapters import (
    HA_ACTION_MANIFEST,
    HA_INGEST_MANIFEST,
    HA_PUBLISH_MANIFEST,
    HaActionAdapter,
    HaIngestAdapter,
    HaMqttPublishAdapter,
)

# ---------------------------------------------------------------------------
# AdapterManifest
# ---------------------------------------------------------------------------


class TestAdapterManifest:
    def test_frozen_manifest_rejects_mutation(self):
        manifest = AdapterManifest(
            adapter_key="test",
            display_name="Test",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        with pytest.raises((AttributeError, TypeError)):
            manifest.adapter_key = "changed"  # type: ignore[misc]

    def test_default_empty_tuples(self):
        manifest = AdapterManifest(
            adapter_key="x",
            display_name="X",
            version="0.1",
            supported_directions=(AdapterDirection.PUBLISH,),
        )
        assert manifest.supported_entity_classes == ()
        assert manifest.credential_requirements == ()
        assert manifest.target_capabilities == ()

    def test_multiple_directions(self):
        manifest = AdapterManifest(
            adapter_key="multi",
            display_name="Multi",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST, AdapterDirection.ACTION),
        )
        assert AdapterDirection.INGEST in manifest.supported_directions
        assert AdapterDirection.ACTION in manifest.supported_directions
        assert AdapterDirection.PUBLISH not in manifest.supported_directions


# ---------------------------------------------------------------------------
# AdapterRuntimeStatus
# ---------------------------------------------------------------------------


class TestAdapterRuntimeStatus:
    def test_as_dict_includes_shared_fields(self):
        status = AdapterRuntimeStatus(
            enabled=True,
            connected=False,
            last_activity_at="2026-03-29T10:00:00Z",
            error_count=2,
        )
        d = status.as_dict()
        assert d["enabled"] is True
        assert d["connected"] is False
        assert d["last_activity_at"] == "2026-03-29T10:00:00Z"
        assert d["error_count"] == 2

    def test_as_dict_merges_extra(self):
        status = AdapterRuntimeStatus(
            enabled=True,
            connected=True,
            last_activity_at=None,
            error_count=0,
            extra={"publish_count": 42, "entity_count": 7},
        )
        d = status.as_dict()
        assert d["publish_count"] == 42
        assert d["entity_count"] == 7

    def test_none_last_activity_at(self):
        status = AdapterRuntimeStatus(
            enabled=False,
            connected=False,
            last_activity_at=None,
            error_count=0,
        )
        assert status.as_dict()["last_activity_at"] is None


# ---------------------------------------------------------------------------
# Protocol conformance via isinstance
# ---------------------------------------------------------------------------


class _MinimalIngest:
    manifest = HA_INGEST_MANIFEST

    def get_status(self) -> AdapterRuntimeStatus:
        return AdapterRuntimeStatus(enabled=True, connected=True, last_activity_at=None, error_count=0)


class _MinimalPublish:
    manifest = HA_PUBLISH_MANIFEST

    def get_status(self) -> AdapterRuntimeStatus:
        return AdapterRuntimeStatus(enabled=True, connected=True, last_activity_at=None, error_count=0)


class _MinimalAction:
    manifest = HA_ACTION_MANIFEST

    def get_status(self) -> AdapterRuntimeStatus:
        return AdapterRuntimeStatus(enabled=True, connected=True, last_activity_at=None, error_count=0)


class TestProtocolConformance:
    def test_ingest_isinstance(self):
        assert isinstance(_MinimalIngest(), IngestAdapter)

    def test_publish_isinstance(self):
        assert isinstance(_MinimalPublish(), PublishAdapter)

    def test_action_isinstance(self):
        assert isinstance(_MinimalAction(), ActionAdapter)

    def test_missing_manifest_fails_ingest(self):
        class Bad:
            def get_status(self) -> AdapterRuntimeStatus:
                return AdapterRuntimeStatus(enabled=True, connected=True, last_activity_at=None, error_count=0)

        assert not isinstance(Bad(), IngestAdapter)

    def test_missing_get_status_fails_publish(self):
        class Bad:
            manifest = HA_PUBLISH_MANIFEST

        assert not isinstance(Bad(), PublishAdapter)


# ---------------------------------------------------------------------------
# HA manifest values
# ---------------------------------------------------------------------------


class TestHaManifests:
    def test_ingest_manifest_key(self):
        assert HA_INGEST_MANIFEST.adapter_key == "ha_ingest"
        assert AdapterDirection.INGEST in HA_INGEST_MANIFEST.supported_directions

    def test_publish_manifest_key(self):
        assert HA_PUBLISH_MANIFEST.adapter_key == "ha_mqtt_publish"
        assert AdapterDirection.PUBLISH in HA_PUBLISH_MANIFEST.supported_directions

    def test_action_manifest_key(self):
        assert HA_ACTION_MANIFEST.adapter_key == "ha_action"
        assert AdapterDirection.ACTION in HA_ACTION_MANIFEST.supported_directions

    def test_credentials_declared(self):
        assert "ha_url" in HA_INGEST_MANIFEST.credential_requirements
        assert "ha_token" in HA_INGEST_MANIFEST.credential_requirements
        assert "ha_mqtt_broker_url" in HA_PUBLISH_MANIFEST.credential_requirements


# ---------------------------------------------------------------------------
# HaIngestAdapter
# ---------------------------------------------------------------------------


class TestHaIngestAdapter:
    def _mock_worker(self, *, connected=True, last_sync_at="2026-03-29T12:00:00Z", reconnect_count=3):
        worker = MagicMock()
        worker.get_status.return_value = {
            "connected": connected,
            "last_sync_at": last_sync_at,
            "reconnect_count": reconnect_count,
        }
        return worker

    def test_manifest_is_ha_ingest(self):
        adapter = HaIngestAdapter(self._mock_worker())
        assert adapter.manifest is HA_INGEST_MANIFEST

    def test_conforms_to_ingest_protocol(self):
        adapter = HaIngestAdapter(self._mock_worker())
        assert isinstance(adapter, IngestAdapter)

    def test_get_status_connected(self):
        adapter = HaIngestAdapter(self._mock_worker(connected=True, last_sync_at="2026-03-29T12:00:00Z", reconnect_count=2))
        status = adapter.get_status()
        assert status.enabled is True
        assert status.connected is True
        assert status.last_activity_at == "2026-03-29T12:00:00Z"
        assert status.error_count == 0
        assert status.extra["reconnect_count"] == 2

    def test_get_status_disconnected(self):
        adapter = HaIngestAdapter(self._mock_worker(connected=False, last_sync_at=None, reconnect_count=0))
        status = adapter.get_status()
        assert status.connected is False
        assert status.last_activity_at is None


# ---------------------------------------------------------------------------
# HaMqttPublishAdapter
# ---------------------------------------------------------------------------


class TestHaMqttPublishAdapter:
    def _mock_worker(self, *, connected=True, last_publish_at="2026-03-29T13:00:00Z",
                     publish_count=10, entity_count=5, publication_keys=None):
        worker = MagicMock()
        worker.get_status.return_value = {
            "connected": connected,
            "last_publish_at": last_publish_at,
            "publish_count": publish_count,
            "entity_count": entity_count,
            "static_entity_count": 3,
            "contract_entity_count": 2,
            "publication_keys": publication_keys or ["finance", "utilities"],
        }
        return worker

    def test_manifest_is_ha_publish(self):
        adapter = HaMqttPublishAdapter(self._mock_worker())
        assert adapter.manifest is HA_PUBLISH_MANIFEST

    def test_conforms_to_publish_protocol(self):
        adapter = HaMqttPublishAdapter(self._mock_worker())
        assert isinstance(adapter, PublishAdapter)

    def test_get_status_fields(self):
        adapter = HaMqttPublishAdapter(self._mock_worker(
            connected=True, last_publish_at="2026-03-29T13:00:00Z",
            publish_count=10, entity_count=5,
        ))
        status = adapter.get_status()
        assert status.enabled is True
        assert status.connected is True
        assert status.last_activity_at == "2026-03-29T13:00:00Z"
        assert status.extra["publish_count"] == 10
        assert status.extra["entity_count"] == 5


# ---------------------------------------------------------------------------
# HaActionAdapter
# ---------------------------------------------------------------------------


class TestHaActionAdapter:
    def _mock_worker(self, *, enabled=True, connected=True, last_dispatch_at="2026-03-29T14:00:00Z",
                     dispatch_count=5, error_count=1, action_log_size=5, tracked_policies=3,
                     approval_pending_count=2, approval_approved_count=1, approval_dismissed_count=0):
        worker = MagicMock()
        worker.get_status.return_value = {
            "enabled": enabled,
            "connected": connected,
            "last_dispatch_at": last_dispatch_at,
            "dispatch_count": dispatch_count,
            "error_count": error_count,
            "action_log_size": action_log_size,
            "tracked_policies": tracked_policies,
            "approval_tracked_count": approval_pending_count + approval_approved_count + approval_dismissed_count,
            "approval_pending_count": approval_pending_count,
            "approval_approved_count": approval_approved_count,
            "approval_dismissed_count": approval_dismissed_count,
        }
        return worker

    def test_manifest_is_ha_action(self):
        adapter = HaActionAdapter(self._mock_worker())
        assert adapter.manifest is HA_ACTION_MANIFEST

    def test_conforms_to_action_protocol(self):
        adapter = HaActionAdapter(self._mock_worker())
        assert isinstance(adapter, ActionAdapter)

    def test_get_status_fields(self):
        adapter = HaActionAdapter(self._mock_worker(
            error_count=1, dispatch_count=5, approval_pending_count=2,
        ))
        status = adapter.get_status()
        assert status.enabled is True
        assert status.connected is True
        assert status.error_count == 1
        assert status.extra["dispatch_count"] == 5
        assert status.extra["approval_pending_count"] == 2

    def test_get_status_disabled(self):
        adapter = HaActionAdapter(self._mock_worker(enabled=False, connected=False))
        status = adapter.get_status()
        assert status.enabled is False
        assert status.connected is False


# ---------------------------------------------------------------------------
# get_runtime_status() on HA workers
# ---------------------------------------------------------------------------


class TestWorkerGetRuntimeStatus:
    """Integration-style tests for the get_runtime_status() methods added to HA workers."""

    def test_ha_bridge_worker_get_runtime_status(self):
        from packages.pipelines.ha_bridge import HaBridgeWorker

        worker = HaBridgeWorker.__new__(HaBridgeWorker)
        worker.connected = True
        worker.last_sync_at = "2026-03-29T11:00:00Z"
        worker.reconnect_count = 4

        status = worker.get_runtime_status()
        assert isinstance(status, AdapterRuntimeStatus)
        assert status.enabled is True
        assert status.connected is True
        assert status.last_activity_at == "2026-03-29T11:00:00Z"
        assert status.extra["reconnect_count"] == 4

    def test_ha_mqtt_publisher_get_runtime_status(self):
        from packages.pipelines.ha_mqtt_publisher import HaMqttPublisher

        worker = MagicMock(spec=HaMqttPublisher)
        worker.get_status.return_value = {
            "connected": False,
            "last_publish_at": None,
            "publish_count": 0,
            "entity_count": 4,
            "static_entity_count": 4,
            "contract_entity_count": 0,
            "publication_keys": [],
        }
        worker.get_runtime_status = HaMqttPublisher.get_runtime_status.__get__(worker)

        status = worker.get_runtime_status()
        assert isinstance(status, AdapterRuntimeStatus)
        assert status.connected is False
        assert status.last_activity_at is None
        assert status.extra["entity_count"] == 4

    def test_ha_action_dispatcher_get_runtime_status(self):
        from packages.pipelines.ha_action_dispatcher import HaActionDispatcher

        worker = MagicMock(spec=HaActionDispatcher)
        worker.get_status.return_value = {
            "enabled": True,
            "connected": True,
            "last_dispatch_at": "2026-03-29T15:00:00Z",
            "dispatch_count": 3,
            "error_count": 0,
            "action_log_size": 3,
            "tracked_policies": 4,
            "approval_tracked_count": 1,
            "approval_pending_count": 1,
            "approval_approved_count": 0,
            "approval_dismissed_count": 0,
        }
        worker.get_runtime_status = HaActionDispatcher.get_runtime_status.__get__(worker)

        status = worker.get_runtime_status()
        assert isinstance(status, AdapterRuntimeStatus)
        assert status.error_count == 0
        assert status.extra["approval_pending_count"] == 1
