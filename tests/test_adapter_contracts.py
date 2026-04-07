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
    AdapterPack,
    AdapterRuntimeStatus,
    CompatibilityCheck,
    IngestAdapter,
    PublishAdapter,
    RenderedOutput,
    Renderer,
    RendererManifest,
    TrustLevel,
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
# AdapterDirection with OBSERVE
# ---------------------------------------------------------------------------


class TestAdapterDirection:
    def test_observe_direction_exists(self):
        assert AdapterDirection.OBSERVE == "observe"
        assert hasattr(AdapterDirection, "OBSERVE")

    def test_all_directions(self):
        directions = [d.value for d in AdapterDirection]
        assert "ingest" in directions
        assert "publish" in directions
        assert "action" in directions
        assert "observe" in directions


# ---------------------------------------------------------------------------
# Renderer contracts
# ---------------------------------------------------------------------------


class TestRenderedOutput:
    def test_rendered_output_creation(self):
        output = RenderedOutput(
            format="csv",
            content=b"a,b,c\n1,2,3",
            content_type="text/csv"
        )
        assert output.format == "csv"
        assert output.content == b"a,b,c\n1,2,3"
        assert output.content_type == "text/csv"
        assert output.encoding == "utf-8"

    def test_rendered_output_custom_encoding(self):
        output = RenderedOutput(
            format="json",
            content=b'{"key": "value"}',
            content_type="application/json",
            encoding="utf-16"
        )
        assert output.encoding == "utf-16"

    def test_rendered_output_frozen(self):
        output = RenderedOutput(
            format="csv",
            content=b"data",
            content_type="text/csv"
        )
        with pytest.raises((AttributeError, TypeError)):
            output.format = "json"  # type: ignore[misc]


class TestRendererManifest:
    def test_renderer_manifest_creation(self):
        manifest = RendererManifest(
            renderer_key="csv_renderer",
            display_name="CSV Renderer",
            version="1.0",
            supported_formats=("csv", "tsv")
        )
        assert manifest.renderer_key == "csv_renderer"
        assert manifest.display_name == "CSV Renderer"
        assert "csv" in manifest.supported_formats
        assert manifest.supported_publication_keys == ()

    def test_renderer_manifest_with_publication_keys(self):
        manifest = RendererManifest(
            renderer_key="json_renderer",
            display_name="JSON Renderer",
            version="2.0",
            supported_formats=("json",),
            supported_publication_keys=("finance", "utilities")
        )
        assert manifest.supported_publication_keys == ("finance", "utilities")

    def test_renderer_manifest_frozen(self):
        manifest = RendererManifest(
            renderer_key="test",
            display_name="Test",
            version="1.0",
            supported_formats=("csv",)
        )
        with pytest.raises((AttributeError, TypeError)):
            manifest.renderer_key = "changed"  # type: ignore[misc]


class TestRenderer:
    def _minimal_renderer(self):
        class MinimalRenderer:
            manifest = RendererManifest(
                renderer_key="test_renderer",
                display_name="Test",
                version="1.0",
                supported_formats=("csv",)
            )

            def render(self, publication_key: str, rows: list[dict]) -> RenderedOutput:
                return RenderedOutput(
                    format="csv",
                    content=b"test",
                    content_type="text/csv"
                )

        return MinimalRenderer()

    def test_renderer_isinstance(self):
        renderer = self._minimal_renderer()
        assert isinstance(renderer, Renderer)

    def test_missing_manifest_fails_renderer(self):
        class Bad:
            def render(self, publication_key: str, rows: list[dict]) -> RenderedOutput:
                return RenderedOutput(
                    format="csv",
                    content=b"test",
                    content_type="text/csv"
                )

        assert not isinstance(Bad(), Renderer)

    def test_missing_render_fails_renderer(self):
        class Bad:
            manifest = RendererManifest(
                renderer_key="test",
                display_name="Test",
                version="1.0",
                supported_formats=("csv",)
            )

        assert not isinstance(Bad(), Renderer)


# ---------------------------------------------------------------------------
# Adapter pack management
# ---------------------------------------------------------------------------


class TestTrustLevel:
    def test_trust_level_values(self):
        assert TrustLevel.VERIFIED == "verified"
        assert TrustLevel.COMMUNITY == "community"
        assert TrustLevel.LOCAL == "local"

    def test_all_trust_levels(self):
        levels = [t.value for t in TrustLevel]
        assert "verified" in levels
        assert "community" in levels
        assert "local" in levels


class TestCompatibilityCheck:
    def test_compatibility_check_compatible(self):
        check = CompatibilityCheck(
            is_compatible=True,
            issues=(),
            warnings=()
        )
        assert check.is_compatible is True
        assert check.issues == ()
        assert check.warnings == ()

    def test_compatibility_check_with_issues(self):
        check = CompatibilityCheck(
            is_compatible=False,
            issues=("Missing dependency X", "Incompatible API version"),
            warnings=("Using deprecated feature",)
        )
        assert check.is_compatible is False
        assert len(check.issues) == 2
        assert "Missing dependency X" in check.issues
        assert "Incompatible API version" in check.issues
        assert "Using deprecated feature" in check.warnings

    def test_compatibility_check_frozen(self):
        check = CompatibilityCheck(
            is_compatible=True,
            issues=(),
            warnings=()
        )
        with pytest.raises((AttributeError, TypeError)):
            check.is_compatible = False  # type: ignore[misc]


class TestAdapterPack:
    def test_adapter_pack_creation_minimal(self):
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL
        )
        assert pack.pack_key == "test_pack"
        assert pack.display_name == "Test Pack"
        assert pack.version == "1.0"
        assert pack.trust_level == TrustLevel.LOCAL
        assert pack.adapters == ()
        assert pack.renderers == ()
        assert pack.description == ""
        assert pack.requires_platform_version == ""

    def test_adapter_pack_with_adapters(self):
        adapter_manifest = AdapterManifest(
            adapter_key="test_adapter",
            display_name="Test Adapter",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,)
        )
        pack = AdapterPack(
            pack_key="pack_with_adapters",
            display_name="Pack With Adapters",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
            adapters=(adapter_manifest,)
        )
        assert len(pack.adapters) == 1
        assert pack.adapters[0].adapter_key == "test_adapter"

    def test_adapter_pack_with_renderers(self):
        renderer_manifest = RendererManifest(
            renderer_key="test_renderer",
            display_name="Test Renderer",
            version="1.0",
            supported_formats=("csv",)
        )
        pack = AdapterPack(
            pack_key="pack_with_renderers",
            display_name="Pack With Renderers",
            version="1.0",
            trust_level=TrustLevel.COMMUNITY,
            renderers=(renderer_manifest,)
        )
        assert len(pack.renderers) == 1
        assert pack.renderers[0].renderer_key == "test_renderer"

    def test_adapter_pack_with_all_fields(self):
        adapter_manifest = AdapterManifest(
            adapter_key="test_adapter",
            display_name="Test Adapter",
            version="1.0",
            supported_directions=(AdapterDirection.PUBLISH,)
        )
        renderer_manifest = RendererManifest(
            renderer_key="test_renderer",
            display_name="Test Renderer",
            version="1.0",
            supported_formats=("json",)
        )
        pack = AdapterPack(
            pack_key="full_pack",
            display_name="Full Pack",
            version="2.0",
            trust_level=TrustLevel.COMMUNITY,
            adapters=(adapter_manifest,),
            renderers=(renderer_manifest,),
            description="A test pack with everything",
            requires_platform_version=">=1.5.0"
        )
        assert pack.pack_key == "full_pack"
        assert pack.description == "A test pack with everything"
        assert pack.requires_platform_version == ">=1.5.0"
        assert len(pack.adapters) == 1
        assert len(pack.renderers) == 1

    def test_adapter_pack_frozen(self):
        pack = AdapterPack(
            pack_key="test",
            display_name="Test",
            version="1.0",
            trust_level=TrustLevel.LOCAL
        )
        with pytest.raises((AttributeError, TypeError)):
            pack.pack_key = "changed"  # type: ignore[misc]


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
