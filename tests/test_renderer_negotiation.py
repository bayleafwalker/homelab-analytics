"""Tests for RendererRouter content negotiation."""

import pytest

from packages.adapters.contracts import (
    AdapterPack,
    RendererManifest,
    TrustLevel,
)
from packages.adapters.export_renderer import EXPORT_RENDERER_MANIFEST, ExportRenderer
from packages.adapters.registry import AdapterRegistry
from packages.adapters.renderer_negotiation import (
    NEGOTIATION_ERROR_NO_ACCEPTABLE_FORMAT,
    NEGOTIATION_ERROR_NO_ELIGIBLE_RENDERER,
    NEGOTIATION_ERROR_UNSUPPORTED_PUBLICATION_VERSION,
    parse_accept_header,
    resolve_format_from_accept,
)
from packages.adapters.renderer_router import RendererRouter


@pytest.fixture
def export_pack():
    return AdapterPack(
        pack_key="export_pack",
        display_name="Export Pack",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
        renderers=(EXPORT_RENDERER_MANIFEST,),
    )


@pytest.fixture
def registry(export_pack):
    registry = AdapterRegistry()
    registry.register(export_pack)
    registry.activate("export_pack")
    return registry


@pytest.fixture
def json_renderer():
    return ExportRenderer(format="json")


@pytest.fixture
def csv_renderer():
    return ExportRenderer(format="csv")


def test_parse_accept_header_orders_by_quality():
    entries = parse_accept_header("text/csv;q=0.5, application/json;q=0.9, */*;q=0.1")
    assert [e.media_type for e in entries] == [
        "application/json",
        "text/csv",
        "*/*",
    ]


def test_parse_accept_header_drops_q_zero():
    entries = parse_accept_header("application/json;q=0, text/csv")
    assert [e.media_type for e in entries] == ["text/csv"]


def test_parse_accept_header_empty_returns_empty_list():
    assert parse_accept_header("") == []
    assert parse_accept_header("   ") == []


def test_resolve_format_from_accept_defaults_to_json_when_empty():
    assert resolve_format_from_accept("") == ("json", "application/json")


def test_resolve_format_from_accept_maps_known_media_types():
    assert resolve_format_from_accept("text/csv")[0] == "csv"
    assert resolve_format_from_accept("application/json")[0] == "json"
    assert resolve_format_from_accept("application/x-parquet")[0] == "parquet"


def test_resolve_format_from_accept_wildcard_prefers_json():
    assert resolve_format_from_accept("*/*")[0] == "json"


def test_resolve_format_from_accept_text_wildcard_prefers_csv():
    assert resolve_format_from_accept("text/*")[0] == "csv"


def test_resolve_format_from_accept_returns_none_for_unknown():
    assert resolve_format_from_accept("application/xml") == (None, None)


def test_negotiate_returns_eligible_renderer_for_matching_accept(registry, json_renderer):
    router = RendererRouter(registry, [json_renderer])

    result = router.negotiate("any_publication", "application/json")

    assert result.is_ok
    assert result.chosen_format == "json"
    assert result.chosen_media_type == "application/json"
    assert result.renderers == (json_renderer,)
    assert result.error_reason is None


def test_negotiate_returns_406_reason_for_unknown_media_type(registry, json_renderer):
    router = RendererRouter(registry, [json_renderer])

    result = router.negotiate("any_publication", "application/xml")

    assert not result.is_ok
    assert result.error_reason == NEGOTIATION_ERROR_NO_ACCEPTABLE_FORMAT
    assert result.renderers == ()


def test_negotiate_returns_no_eligible_renderer_when_pack_inactive(registry, csv_renderer):
    registry.deactivate("export_pack")
    router = RendererRouter(registry, [csv_renderer])

    result = router.negotiate("any_publication", "text/csv")

    assert not result.is_ok
    assert result.error_reason == NEGOTIATION_ERROR_NO_ELIGIBLE_RENDERER


def test_negotiate_respects_q_ordering(registry, json_renderer, csv_renderer):
    router = RendererRouter(registry, [json_renderer, csv_renderer])

    result = router.negotiate("any_publication", "text/csv;q=0.9, application/json;q=1.0")

    assert result.chosen_format == "json"
    assert json_renderer in result.renderers


def test_negotiate_falls_through_to_next_acceptable_format(registry, csv_renderer):
    router = RendererRouter(registry, [csv_renderer])

    result = router.negotiate("any_publication", "application/xml, text/csv")

    assert result.is_ok
    assert result.chosen_format == "csv"


def test_negotiate_accepts_matching_publication_version():
    versioned_manifest = RendererManifest(
        renderer_key="export_csv_json",
        display_name="Versioned Export",
        version="1.0",
        supported_formats=("json",),
        supported_publication_versions=("1.0.0", "1.1.0"),
    )
    pack = AdapterPack(
        pack_key="versioned_pack",
        display_name="Versioned Pack",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
        renderers=(versioned_manifest,),
    )
    registry = AdapterRegistry()
    registry.register(pack)
    registry.activate("versioned_pack")

    class _R:
        manifest = versioned_manifest

        def render(self, publication_key, rows):
            raise NotImplementedError

    renderer = _R()
    router = RendererRouter(registry, [renderer])

    ok = router.negotiate("any_publication", "application/json", publication_version="1.0.0")
    assert ok.is_ok

    miss = router.negotiate("any_publication", "application/json", publication_version="2.0.0")
    assert not miss.is_ok
    assert miss.error_reason == NEGOTIATION_ERROR_UNSUPPORTED_PUBLICATION_VERSION


def test_negotiate_accepts_any_version_when_manifest_declares_no_versions(registry, json_renderer):
    router = RendererRouter(registry, [json_renderer])

    result = router.negotiate("any_publication", "application/json", publication_version="99.99.99")

    assert result.is_ok
