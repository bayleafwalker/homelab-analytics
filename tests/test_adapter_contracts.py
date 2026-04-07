"""Tests for Stage 6 integration adapter contracts.

Covers:
- AdapterManifest field validation and immutability
- AdapterRuntimeStatus as_dict() serialisation
- IngestAdapter / PublishAdapter / ActionAdapter protocol conformance
- HaIngestAdapter, HaMqttPublishAdapter, HaActionAdapter wrapper behaviour
- get_runtime_status() on the HA workers
"""

from __future__ import annotations

import json
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
from packages.adapters.compatibility import check_compatibility, validate_adapter_pack
from packages.adapters.export_renderer import ExportRenderer
from packages.adapters.registry import AdapterRegistry
from packages.adapters.ha_adapters import (
    HA_ACTION_MANIFEST,
    HA_ADAPTER_PACK,
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


# ---------------------------------------------------------------------------
# AdapterRegistry
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    def _make_pack(self, pack_key: str, display_name: str = "Test Pack") -> AdapterPack:
        """Helper to create a test pack."""
        return AdapterPack(
            pack_key=pack_key,
            display_name=display_name,
            version="1.0",
            trust_level=TrustLevel.LOCAL
        )

    def test_register_and_list(self):
        registry = AdapterRegistry()
        pack1 = self._make_pack("pack1")
        pack2 = self._make_pack("pack2")

        registry.register(pack1)
        registry.register(pack2)

        packs = registry.list_packs()
        assert len(packs) == 2
        assert packs[0].pack_key == "pack1"
        assert packs[1].pack_key == "pack2"

    def test_register_duplicate_raises_value_error(self):
        registry = AdapterRegistry()
        pack = self._make_pack("duplicate")

        registry.register(pack)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(pack)

    def test_activate_deactivate_is_active(self):
        registry = AdapterRegistry()
        pack = self._make_pack("test_pack")
        registry.register(pack)

        # Initially inactive
        assert registry.is_active("test_pack") is False

        # Activate
        registry.activate("test_pack")
        assert registry.is_active("test_pack") is True

        # Deactivate
        registry.deactivate("test_pack")
        assert registry.is_active("test_pack") is False

    def test_list_packs_active_only_filter(self):
        registry = AdapterRegistry()
        pack1 = self._make_pack("pack1")
        pack2 = self._make_pack("pack2")
        pack3 = self._make_pack("pack3")

        registry.register(pack1)
        registry.register(pack2)
        registry.register(pack3)

        # Activate pack1 and pack3
        registry.activate("pack1")
        registry.activate("pack3")

        all_packs = registry.list_packs(active_only=False)
        assert len(all_packs) == 3

        active_packs = registry.list_packs(active_only=True)
        assert len(active_packs) == 2
        assert active_packs[0].pack_key == "pack1"
        assert active_packs[1].pack_key == "pack3"

    def test_get_returns_none_for_unknown(self):
        registry = AdapterRegistry()
        pack = self._make_pack("test_pack")
        registry.register(pack)

        # Existing pack
        retrieved = registry.get("test_pack")
        assert retrieved is not None
        assert retrieved.pack_key == "test_pack"

        # Unknown pack
        assert registry.get("unknown") is None

    def test_unregister_removes_pack(self):
        registry = AdapterRegistry()
        pack = self._make_pack("test_pack")
        registry.register(pack)

        assert registry.get("test_pack") is not None
        registry.unregister("test_pack")
        assert registry.get("test_pack") is None

    def test_unregister_unknown_raises_key_error(self):
        registry = AdapterRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.unregister("unknown")

    def test_activate_unknown_raises_key_error(self):
        registry = AdapterRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.activate("unknown")

    def test_deactivate_unknown_raises_key_error(self):
        registry = AdapterRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.deactivate("unknown")

    def test_list_packs_ordered_by_key(self):
        registry = AdapterRegistry()
        # Register in non-sorted order
        for key in ["zebra", "apple", "monkey"]:
            registry.register(self._make_pack(key))

        packs = registry.list_packs()
        keys = [p.pack_key for p in packs]
        assert keys == ["apple", "monkey", "zebra"]

    def test_is_active_returns_false_for_unknown(self):
        registry = AdapterRegistry()
        assert registry.is_active("unknown") is False


# ---------------------------------------------------------------------------
# Compatibility checking
# ---------------------------------------------------------------------------


class TestCheckCompatibility:
    def test_compatible_pack_verified_trust(self):
        """Compatible pack with VERIFIED trust has no issues or warnings."""
        adapter = AdapterManifest(
            adapter_key="test_adapter",
            display_name="Test",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        pack = AdapterPack(
            pack_key="verified_pack",
            display_name="Verified Pack",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
            adapters=(adapter,),
        )
        check = check_compatibility(pack, platform_version="1.5.2")
        assert check.is_compatible is True
        assert check.issues == ()
        assert check.warnings == ()

    def test_local_trust_adds_warning(self):
        """Pack with LOCAL trust level adds warning."""
        adapter = AdapterManifest(
            adapter_key="local_adapter",
            display_name="Local",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        pack = AdapterPack(
            pack_key="local_pack",
            display_name="Local Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
            adapters=(adapter,),
        )
        check = check_compatibility(pack)
        assert check.is_compatible is True
        assert len(check.warnings) == 1
        assert "LOCAL trust level" in check.warnings[0]
        assert check.issues == ()

    def test_community_trust_adds_warning(self):
        """Pack with COMMUNITY trust level adds warning."""
        adapter = AdapterManifest(
            adapter_key="community_adapter",
            display_name="Community",
            version="1.0",
            supported_directions=(AdapterDirection.PUBLISH,),
        )
        pack = AdapterPack(
            pack_key="community_pack",
            display_name="Community Pack",
            version="1.0",
            trust_level=TrustLevel.COMMUNITY,
            adapters=(adapter,),
        )
        check = check_compatibility(pack)
        assert check.is_compatible is True
        assert len(check.warnings) == 1
        assert "COMMUNITY trust level" in check.warnings[0]
        assert "review before activating in production" in check.warnings[0]
        assert check.issues == ()

    def test_empty_pack_adds_issue(self):
        """Pack with no adapters or renderers is incompatible."""
        pack = AdapterPack(
            pack_key="empty_pack",
            display_name="Empty Pack",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
        )
        check = check_compatibility(pack)
        assert check.is_compatible is False
        assert len(check.issues) == 1
        assert "contains no adapters or renderers" in check.issues[0]
        assert check.warnings == ()

    def test_version_constraint_mismatch_adds_issue(self):
        """Major version mismatch causes incompatibility."""
        adapter = AdapterManifest(
            adapter_key="version_adapter",
            display_name="Version",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        pack = AdapterPack(
            pack_key="version_pack",
            display_name="Version Pack",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
            adapters=(adapter,),
            requires_platform_version="2.0.0",
        )
        check = check_compatibility(pack, platform_version="1.5.2")
        assert check.is_compatible is False
        assert len(check.issues) == 1
        assert "requires platform version '2.0.0'" in check.issues[0]
        assert "got '1.5.2'" in check.issues[0]

    def test_unknown_platform_version_adds_warning(self):
        """Empty platform_version with requires_platform_version adds warning."""
        adapter = AdapterManifest(
            adapter_key="test_adapter",
            display_name="Test",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
            adapters=(adapter,),
            requires_platform_version="1.5.0",
        )
        check = check_compatibility(pack, platform_version="")
        assert check.is_compatible is True
        assert len(check.warnings) == 1
        assert "Platform version unknown" in check.warnings[0]
        assert "cannot verify version constraint '1.5.0'" in check.warnings[0]
        assert check.issues == ()

    def test_version_constraint_matching_major_version(self):
        """Matching major version passes version check."""
        adapter = AdapterManifest(
            adapter_key="test_adapter",
            display_name="Test",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
            adapters=(adapter,),
            requires_platform_version="1.5.0",
        )
        check = check_compatibility(pack, platform_version="1.9.3")
        assert check.is_compatible is True
        assert check.issues == ()
        assert check.warnings == ()

    def test_multiple_warnings_accumulate(self):
        """Multiple warnings are all included."""
        adapter = AdapterManifest(
            adapter_key="test_adapter",
            display_name="Test",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
            adapters=(adapter,),
            requires_platform_version="1.5.0",
        )
        check = check_compatibility(pack, platform_version="")
        assert check.is_compatible is True
        assert len(check.warnings) == 2
        assert any("Platform version unknown" in w for w in check.warnings)
        assert any("LOCAL trust level" in w for w in check.warnings)


# ---------------------------------------------------------------------------
# Adapter pack validation
# ---------------------------------------------------------------------------


class TestValidateAdapterPack:
    def test_valid_pack_returns_empty_list(self):
        """Valid pack passes validation."""
        adapter = AdapterManifest(
            adapter_key="valid_adapter",
            display_name="Valid",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        pack = AdapterPack(
            pack_key="valid_pack",
            display_name="Valid Pack",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
            adapters=(adapter,),
        )
        errors = validate_adapter_pack(pack)
        assert errors == []

    def test_empty_pack_key_returns_error(self):
        """Empty pack_key is rejected."""
        pack = AdapterPack(
            pack_key="",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
        )
        errors = validate_adapter_pack(pack)
        assert "pack_key must be non-empty" in errors

    def test_empty_display_name_returns_error(self):
        """Empty display_name is rejected."""
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
        )
        errors = validate_adapter_pack(pack)
        assert "display_name must be non-empty" in errors

    def test_empty_version_returns_error(self):
        """Empty version is rejected."""
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="",
            trust_level=TrustLevel.LOCAL,
        )
        errors = validate_adapter_pack(pack)
        assert "version must be non-empty" in errors

    def test_empty_adapter_key_returns_error(self):
        """Adapter with empty adapter_key is rejected."""
        adapter = AdapterManifest(
            adapter_key="",
            display_name="Bad Adapter",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
            adapters=(adapter,),
        )
        errors = validate_adapter_pack(pack)
        assert "adapter '' has empty adapter_key" in errors

    def test_duplicate_adapter_key_returns_error(self):
        """Duplicate adapter_key is rejected."""
        adapter1 = AdapterManifest(
            adapter_key="duplicate",
            display_name="Adapter 1",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        adapter2 = AdapterManifest(
            adapter_key="duplicate",
            display_name="Adapter 2",
            version="1.0",
            supported_directions=(AdapterDirection.PUBLISH,),
        )
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
            adapters=(adapter1, adapter2),
        )
        errors = validate_adapter_pack(pack)
        assert "duplicate adapter_key: 'duplicate'" in errors

    def test_empty_renderer_key_returns_error(self):
        """Renderer with empty renderer_key is rejected."""
        renderer = RendererManifest(
            renderer_key="",
            display_name="Bad Renderer",
            version="1.0",
            supported_formats=("csv",),
        )
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
            renderers=(renderer,),
        )
        errors = validate_adapter_pack(pack)
        assert "renderer '' has empty renderer_key" in errors

    def test_duplicate_renderer_key_returns_error(self):
        """Duplicate renderer_key is rejected."""
        renderer1 = RendererManifest(
            renderer_key="duplicate",
            display_name="Renderer 1",
            version="1.0",
            supported_formats=("csv",),
        )
        renderer2 = RendererManifest(
            renderer_key="duplicate",
            display_name="Renderer 2",
            version="1.0",
            supported_formats=("json",),
        )
        pack = AdapterPack(
            pack_key="test_pack",
            display_name="Test Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
            renderers=(renderer1, renderer2),
        )
        errors = validate_adapter_pack(pack)
        assert "duplicate renderer_key: 'duplicate'" in errors

    def test_multiple_errors_accumulate(self):
        """Multiple errors are all included."""
        adapter = AdapterManifest(
            adapter_key="",
            display_name="Bad",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        renderer = RendererManifest(
            renderer_key="",
            display_name="Bad",
            version="1.0",
            supported_formats=("csv",),
        )
        pack = AdapterPack(
            pack_key="",
            display_name="",
            version="",
            trust_level=TrustLevel.LOCAL,
            adapters=(adapter,),
            renderers=(renderer,),
        )
        errors = validate_adapter_pack(pack)
        assert "pack_key must be non-empty" in errors
        assert "display_name must be non-empty" in errors
        assert "version must be non-empty" in errors
        assert any("adapter_key" in e for e in errors)
        assert any("renderer_key" in e for e in errors)


# ---------------------------------------------------------------------------
# ExportRenderer
# ---------------------------------------------------------------------------


class TestExportRenderer:
    def test_default_format_is_json(self):
        """ExportRenderer defaults to JSON format."""
        renderer = ExportRenderer()
        assert renderer._format == "json"

    def test_invalid_format_raises_value_error(self):
        """ExportRenderer raises ValueError for unsupported format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            ExportRenderer(format="xml")

    def test_json_render_non_empty_rows(self):
        """JSON render of non-empty rows returns valid JSON."""
        renderer = ExportRenderer(format="json")
        rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        output = renderer.render("test_publication", rows)
        assert output.format == "json"
        assert output.content_type == "application/json"
        data = json.loads(output.content.decode("utf-8"))
        assert len(data) == 2
        assert data[0]["id"] == 1

    def test_json_render_empty_rows(self):
        """JSON render of empty rows returns empty array."""
        renderer = ExportRenderer(format="json")
        output = renderer.render("test_publication", [])
        assert output.content == b"[]"

    def test_csv_render_non_empty_rows(self):
        """CSV render of non-empty rows includes header and values."""
        renderer = ExportRenderer(format="csv")
        rows = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]
        output = renderer.render("test_publication", rows)
        assert output.format == "csv"
        assert output.content_type == "text/csv"
        csv_content = output.content.decode("utf-8")
        lines = csv_content.strip().split("\n")
        assert "id" in lines[0]
        assert "name" in lines[0]
        assert len(lines) == 3  # header + 2 rows

    def test_csv_render_empty_rows(self):
        """CSV render of empty rows returns empty bytes."""
        renderer = ExportRenderer(format="csv")
        output = renderer.render("test_publication", [])
        assert output.content == b""

    def test_conforms_to_renderer_protocol(self):
        """ExportRenderer instance passes isinstance check for Renderer."""
        renderer = ExportRenderer()
        assert isinstance(renderer, Renderer)

    def test_manifest_supported_formats(self):
        """Manifest contains both csv and json formats."""
        renderer = ExportRenderer()
        assert "csv" in renderer.manifest.supported_formats
        assert "json" in renderer.manifest.supported_formats


# ---------------------------------------------------------------------------
# HA_ADAPTER_PACK
# ---------------------------------------------------------------------------


class TestHaAdapterPack:
    def test_pack_key(self):
        """HA_ADAPTER_PACK has correct pack_key."""
        assert HA_ADAPTER_PACK.pack_key == "ha_core"

    def test_trust_level(self):
        """HA_ADAPTER_PACK has VERIFIED trust level."""
        assert HA_ADAPTER_PACK.trust_level == TrustLevel.VERIFIED

    def test_has_all_three_manifests(self):
        """HA_ADAPTER_PACK contains all three HA manifests in adapters."""
        assert HA_INGEST_MANIFEST in HA_ADAPTER_PACK.adapters
        assert HA_PUBLISH_MANIFEST in HA_ADAPTER_PACK.adapters
        assert HA_ACTION_MANIFEST in HA_ADAPTER_PACK.adapters
        assert len(HA_ADAPTER_PACK.adapters) == 3

    def test_renderers_empty(self):
        """HA_ADAPTER_PACK has no renderers."""
        assert HA_ADAPTER_PACK.renderers == ()


# ---------------------------------------------------------------------------
# Adapter pack lifecycle integration tests
# ---------------------------------------------------------------------------


class TestAdapterPackLifecycleIntegration:
    """Integration-style tests exercising full lifecycle: build, validate, check compatibility,
    register, activate, and verify in registry queries."""

    def test_register_validate_activate_cycle(self):
        """Build custom AdapterPack, validate, check compatibility, register, activate, deactivate."""
        # Build a custom pack
        custom_manifest = AdapterManifest(
            adapter_key="custom_adapter",
            display_name="Custom Test Adapter",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
            supported_entity_classes=("test_entity",),
            credential_requirements=("test_token",),
        )
        custom_pack = AdapterPack(
            pack_key="custom_pack",
            display_name="Custom Test Pack",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
            adapters=(custom_manifest,),
        )

        # Validate the pack
        errors = validate_adapter_pack(custom_pack)
        assert errors == [], f"Pack validation failed: {errors}"

        # Check compatibility
        compat = check_compatibility(custom_pack, platform_version="1.5.2")
        assert compat.is_compatible is True
        assert compat.issues == ()
        assert compat.warnings == ()

        # Create registry and register
        registry = AdapterRegistry()
        registry.register(custom_pack)

        # Initially inactive
        assert registry.is_active("custom_pack") is False

        # Activate
        registry.activate("custom_pack")
        assert registry.is_active("custom_pack") is True

        # Deactivate
        registry.deactivate("custom_pack")
        assert registry.is_active("custom_pack") is False

    def test_ha_pack_compatibility(self):
        """HA_ADAPTER_PACK is VERIFIED with adapters and validates successfully."""
        # Validate the pack
        errors = validate_adapter_pack(HA_ADAPTER_PACK)
        assert errors == [], f"HA_ADAPTER_PACK validation failed: {errors}"

        # Check compatibility
        compat = check_compatibility(HA_ADAPTER_PACK, platform_version="1.5.2")
        assert compat.is_compatible is True
        assert compat.issues == ()
        assert compat.warnings == ()

    def test_export_renderer_in_registry(self):
        """Create pack with ExportRenderer, register, and verify in queries."""
        from packages.adapters.export_renderer import EXPORT_RENDERER_MANIFEST

        # Build a pack wrapping the export renderer
        renderer_pack = AdapterPack(
            pack_key="export_pack",
            display_name="Export Renderer Pack",
            version="1.0",
            trust_level=TrustLevel.VERIFIED,
            renderers=(EXPORT_RENDERER_MANIFEST,),
        )

        # Register in registry
        registry = AdapterRegistry()
        registry.register(renderer_pack)

        # Verify it appears in list_packs()
        packs = registry.list_packs()
        assert len(packs) == 1
        assert packs[0].pack_key == "export_pack"

        # Verify renderers are accessible on the pack
        assert len(renderer_pack.renderers) == 1
        assert renderer_pack.renderers[0].renderer_key == "export_csv_json"

        # Verify ExportRenderer conforms to Renderer protocol
        renderer = ExportRenderer()
        assert isinstance(renderer, Renderer)

    def test_duplicate_pack_key_across_registries_is_isolated(self):
        """Two separate registries should be completely independent."""
        registry1 = AdapterRegistry()
        registry2 = AdapterRegistry()

        # Register HA_ADAPTER_PACK in both
        registry1.register(HA_ADAPTER_PACK)
        registry2.register(HA_ADAPTER_PACK)

        # Activate in registry1
        registry1.activate("ha_core")
        assert registry1.is_active("ha_core") is True
        assert registry2.is_active("ha_core") is False

        # Unregister from registry1
        registry1.unregister("ha_core")
        assert registry1.get("ha_core") is None
        assert registry2.get("ha_core") is not None

    def test_pack_with_mixed_adapters_and_renderers(self):
        """Build pack with both adapters and renderers, validate, check compatibility."""
        adapter_manifest = AdapterManifest(
            adapter_key="mixed_adapter",
            display_name="Mixed Adapter",
            version="1.0",
            supported_directions=(AdapterDirection.PUBLISH,),
        )
        renderer_manifest = RendererManifest(
            renderer_key="mixed_renderer",
            display_name="Mixed Renderer",
            version="1.0",
            supported_formats=("json", "csv"),
        )
        mixed_pack = AdapterPack(
            pack_key="mixed_pack",
            display_name="Mixed Pack",
            version="1.0",
            trust_level=TrustLevel.COMMUNITY,
            adapters=(adapter_manifest,),
            renderers=(renderer_manifest,),
        )

        # Validate
        errors = validate_adapter_pack(mixed_pack)
        assert errors == [], f"Mixed pack validation failed: {errors}"

        # Check compatibility (COMMUNITY trust will add warning)
        compat = check_compatibility(mixed_pack)
        assert compat.is_compatible is True
        assert len(compat.warnings) == 1
        assert "COMMUNITY trust level" in compat.warnings[0]

        # Verify both adapters and renderers are accessible
        assert len(mixed_pack.adapters) == 1
        assert mixed_pack.adapters[0].adapter_key == "mixed_adapter"
        assert len(mixed_pack.renderers) == 1
        assert mixed_pack.renderers[0].renderer_key == "mixed_renderer"

    def test_compatibility_warning_does_not_block_registration(self):
        """Pack with LOCAL trust level produces warning but is still compatible for registration."""
        local_adapter = AdapterManifest(
            adapter_key="local_test_adapter",
            display_name="Local Test",
            version="1.0",
            supported_directions=(AdapterDirection.INGEST,),
        )
        local_pack = AdapterPack(
            pack_key="local_test_pack",
            display_name="Local Test Pack",
            version="1.0",
            trust_level=TrustLevel.LOCAL,
            adapters=(local_adapter,),
        )

        # Check compatibility (LOCAL trust produces warning)
        compat = check_compatibility(local_pack)
        assert compat.is_compatible is True
        assert len(compat.warnings) == 1
        assert "LOCAL trust level" in compat.warnings[0]
        assert compat.issues == ()

        # Despite warning, pack should register and activate successfully
        registry = AdapterRegistry()
        registry.register(local_pack)
        registry.activate("local_test_pack")
        assert registry.is_active("local_test_pack") is True


# ---------------------------------------------------------------------------
# Prometheus adapter tests
# ---------------------------------------------------------------------------


class TestPrometheusAdapter:
    """Tests for the Prometheus metrics adapter."""

    def test_prometheus_renderer_manifest_key(self):
        """Test that the manifest has the correct renderer key."""
        from packages.adapters.prometheus_adapter import PROMETHEUS_RENDERER_MANIFEST
        assert PROMETHEUS_RENDERER_MANIFEST.renderer_key == "prometheus_metrics"

    def test_prometheus_renderer_manifest_version(self):
        """Test that the manifest has the correct version."""
        from packages.adapters.prometheus_adapter import PROMETHEUS_RENDERER_MANIFEST
        assert PROMETHEUS_RENDERER_MANIFEST.version == "1.0"

    def test_prometheus_renderer_manifest_supported_formats(self):
        """Test that the manifest supports prometheus_text format."""
        from packages.adapters.prometheus_adapter import PROMETHEUS_RENDERER_MANIFEST
        assert "prometheus_text" in PROMETHEUS_RENDERER_MANIFEST.supported_formats

    def test_prometheus_renderer_conforms_to_renderer_protocol(self):
        """Test that PrometheusRenderer conforms to the Renderer protocol."""
        from packages.adapters.prometheus_adapter import PrometheusRenderer
        from packages.shared.metrics import MetricsRegistry

        renderer = PrometheusRenderer(MetricsRegistry())
        assert isinstance(renderer, Renderer)

    def test_prometheus_renderer_render_returns_prometheus_text(self):
        """Test that render() returns RenderedOutput with prometheus_text format."""
        from packages.adapters.prometheus_adapter import PrometheusRenderer
        from packages.shared.metrics import MetricsRegistry

        registry = MetricsRegistry()
        renderer = PrometheusRenderer(registry)
        output = renderer.render("unused_key", [])
        assert output.format == "prometheus_text"
        assert "text/plain" in output.content_type
        assert b"0.0.4" in output.content_type.encode()

    def test_prometheus_renderer_render_with_metrics(self):
        """Test that render() includes metric data from the registry."""
        from packages.adapters.prometheus_adapter import PrometheusRenderer
        from packages.shared.metrics import MetricsRegistry

        registry = MetricsRegistry()
        registry.set("test_gauge", 42.0, help_text="Test gauge", metric_type="gauge")
        renderer = PrometheusRenderer(registry)
        output = renderer.render("unused_key", [])
        assert b"test_gauge" in output.content
        assert b"42" in output.content

    def test_prometheus_renderer_manifest_publication_keys_empty(self):
        """Test that the manifest has empty publication keys (platform-wide)."""
        from packages.adapters.prometheus_adapter import PROMETHEUS_RENDERER_MANIFEST
        assert PROMETHEUS_RENDERER_MANIFEST.supported_publication_keys == ()

    def test_prometheus_adapter_pack_key(self):
        """Test that the adapter pack has the correct pack key."""
        from packages.adapters.prometheus_adapter import PROMETHEUS_ADAPTER_PACK
        assert PROMETHEUS_ADAPTER_PACK.pack_key == "prometheus_core"

    def test_prometheus_adapter_pack_trust_level(self):
        """Test that the adapter pack is marked as verified."""
        from packages.adapters.prometheus_adapter import PROMETHEUS_ADAPTER_PACK
        assert PROMETHEUS_ADAPTER_PACK.trust_level == TrustLevel.VERIFIED

    def test_prometheus_adapter_pack_has_renderer(self):
        """Test that the adapter pack includes the renderer manifest."""
        from packages.adapters.prometheus_adapter import PROMETHEUS_ADAPTER_PACK
        assert len(PROMETHEUS_ADAPTER_PACK.renderers) == 1
        assert PROMETHEUS_ADAPTER_PACK.renderers[0].renderer_key == "prometheus_metrics"

    def test_prometheus_adapter_pack_has_no_adapters(self):
        """Test that the adapter pack has no adapters."""
        from packages.adapters.prometheus_adapter import PROMETHEUS_ADAPTER_PACK
        assert PROMETHEUS_ADAPTER_PACK.adapters == ()
