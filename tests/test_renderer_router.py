"""Tests for RendererRouter."""

import pytest

from packages.adapters.contracts import AdapterPack, TrustLevel
from packages.adapters.export_renderer import EXPORT_RENDERER_MANIFEST, ExportRenderer
from packages.adapters.registry import AdapterRegistry
from packages.adapters.renderer_router import RendererRouter


@pytest.fixture
def registry():
    """Create a fresh AdapterRegistry."""
    return AdapterRegistry()


@pytest.fixture
def export_renderer_json():
    """Create an ExportRenderer instance for JSON."""
    return ExportRenderer(format="json")


@pytest.fixture
def export_renderer_csv():
    """Create an ExportRenderer instance for CSV."""
    return ExportRenderer(format="csv")


@pytest.fixture
def export_pack():
    """Create an AdapterPack with the export renderer manifest."""
    return AdapterPack(
        pack_key="export_pack",
        display_name="Export Pack",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
        renderers=(EXPORT_RENDERER_MANIFEST,),
    )


def test_resolve_returns_matching_renderer_when_pack_active(
    registry, export_renderer_json, export_pack
):
    """resolve() returns matching renderer when pack is active and format matches."""
    registry.register(export_pack)
    registry.activate("export_pack")

    router = RendererRouter(registry, [export_renderer_json])

    # JSON format matches, pack is active
    resolved = router.resolve("any_publication", "json")
    assert len(resolved) == 1
    assert resolved[0] is export_renderer_json


def test_resolve_returns_empty_when_pack_inactive(
    registry, export_renderer_json, export_pack
):
    """resolve() returns empty when pack is inactive."""
    registry.register(export_pack)
    # Don't activate the pack

    router = RendererRouter(registry, [export_renderer_json])

    resolved = router.resolve("any_publication", "json")
    assert len(resolved) == 0


def test_resolve_returns_empty_when_format_not_match(
    registry, export_renderer_json, export_pack
):
    """resolve() returns empty when format doesn't match."""
    registry.register(export_pack)
    registry.activate("export_pack")

    router = RendererRouter(registry, [export_renderer_json])

    # Request an unsupported format
    resolved = router.resolve("any_publication", "xml")
    assert len(resolved) == 0


def test_resolve_filters_by_publication_key_when_restricted(registry, export_pack):
    """resolve() filters by publication_key when supported_publication_keys is non-empty."""
    from packages.adapters.contracts import RendererManifest

    # Create a renderer with restricted publication keys
    restricted_manifest = RendererManifest(
        renderer_key="restricted_renderer",
        display_name="Restricted Renderer",
        version="1.0",
        supported_formats=("json", "csv"),
        supported_publication_keys=("users", "products"),
    )

    # Create a pack with the restricted renderer
    pack = AdapterPack(
        pack_key="restricted_pack",
        display_name="Restricted Pack",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
        renderers=(restricted_manifest,),
    )

    registry.register(pack)
    registry.activate("restricted_pack")

    # Create a mock renderer
    class MockRenderer:
        manifest = restricted_manifest

        def render(self, publication_key: str, rows: list[dict]):
            pass

    renderer = MockRenderer()
    router = RendererRouter(registry, [renderer])

    # Should match "users"
    resolved = router.resolve("users", "json")
    assert len(resolved) == 1

    # Should match "products"
    resolved = router.resolve("products", "json")
    assert len(resolved) == 1

    # Should not match "orders"
    resolved = router.resolve("orders", "json")
    assert len(resolved) == 0


def test_resolve_matches_all_publications_when_empty_supported_keys(
    registry, export_renderer_json, export_pack
):
    """resolve() matches all publications when supported_publication_keys is empty."""
    registry.register(export_pack)
    registry.activate("export_pack")

    router = RendererRouter(registry, [export_renderer_json])

    # EXPORT_RENDERER_MANIFEST has empty supported_publication_keys
    # So any publication_key should match
    resolved1 = router.resolve("users", "json")
    assert len(resolved1) == 1

    resolved2 = router.resolve("products", "json")
    assert len(resolved2) == 1

    resolved3 = router.resolve("any_key", "json")
    assert len(resolved3) == 1


def test_render_all_returns_rendered_outputs_from_all_eligible(
    registry, export_renderer_json, export_renderer_csv, export_pack
):
    """render_all() returns rendered outputs from all eligible renderers."""
    registry.register(export_pack)
    registry.activate("export_pack")

    # Both renderers are in the list
    router = RendererRouter(registry, [export_renderer_json, export_renderer_csv])

    rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    # When requesting json format, both renderers support it so both render
    # export_renderer_json outputs json, export_renderer_csv outputs csv
    outputs = router.render_all("users", "json", rows)
    assert len(outputs) == 2
    formats = {output.format for output in outputs}
    assert formats == {"json", "csv"}

    # When requesting csv format, both renderers support it so both render
    outputs = router.render_all("users", "csv", rows)
    assert len(outputs) == 2
    formats = {output.format for output in outputs}
    assert formats == {"json", "csv"}


def test_render_first_returns_first_output_when_available(
    registry, export_renderer_json, export_pack
):
    """render_first() returns first output or None."""
    registry.register(export_pack)
    registry.activate("export_pack")

    router = RendererRouter(registry, [export_renderer_json])

    rows = [{"id": 1, "name": "Alice"}]

    output = router.render_first("users", "json", rows)
    assert output is not None
    assert output.format == "json"


def test_render_first_returns_none_when_no_eligible_renderers(
    registry, export_renderer_json, export_pack
):
    """render_first() returns None if no eligible renderers."""
    registry.register(export_pack)
    # Don't activate the pack

    router = RendererRouter(registry, [export_renderer_json])

    rows = [{"id": 1, "name": "Alice"}]

    output = router.render_first("users", "json", rows)
    assert output is None


def test_multiple_renderers_only_eligible_ones_returned(registry, export_pack):
    """Multiple renderers: only eligible ones returned."""
    from packages.adapters.contracts import RendererManifest

    # Create two renderers with different capabilities
    json_only_manifest = RendererManifest(
        renderer_key="json_renderer",
        display_name="JSON Only",
        version="1.0",
        supported_formats=("json",),
    )

    csv_only_manifest = RendererManifest(
        renderer_key="csv_renderer",
        display_name="CSV Only",
        version="1.0",
        supported_formats=("csv",),
    )

    # Create packs for each
    pack1 = AdapterPack(
        pack_key="pack_json",
        display_name="JSON Pack",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
        renderers=(json_only_manifest,),
    )

    pack2 = AdapterPack(
        pack_key="pack_csv",
        display_name="CSV Pack",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
        renderers=(csv_only_manifest,),
    )

    registry.register(pack1)
    registry.register(pack2)
    registry.activate("pack_json")
    # pack_csv is NOT activated

    # Create mock renderers
    class MockJSONRenderer:
        manifest = json_only_manifest

        def render(self, publication_key: str, rows: list[dict]):
            from packages.adapters.contracts import RenderedOutput

            return RenderedOutput(
                format="json",
                content=b"[]",
                content_type="application/json",
            )

    class MockCSVRenderer:
        manifest = csv_only_manifest

        def render(self, publication_key: str, rows: list[dict]):
            from packages.adapters.contracts import RenderedOutput

            return RenderedOutput(format="csv", content=b"", content_type="text/csv")

    json_renderer = MockJSONRenderer()
    csv_renderer = MockCSVRenderer()

    router = RendererRouter(registry, [json_renderer, csv_renderer])

    # When requesting JSON, only the JSON renderer should be resolved
    resolved = router.resolve("publication", "json")
    assert len(resolved) == 1
    assert resolved[0] is json_renderer

    # When requesting CSV, no renderer should be resolved (pack_csv is inactive)
    resolved = router.resolve("publication", "csv")
    assert len(resolved) == 0

    # Now activate pack_csv
    registry.activate("pack_csv")

    # When requesting CSV, the CSV renderer should now be resolved
    resolved = router.resolve("publication", "csv")
    assert len(resolved) == 1
    assert resolved[0] is csv_renderer
