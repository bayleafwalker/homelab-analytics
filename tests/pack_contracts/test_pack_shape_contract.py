"""Contract assertions that must hold for every pack.

These are the invariants that make a pack safe to register and to hand
to the ``PackCompatibilityChecker``. Anything that fails here would
either crash at registration time or produce inconsistent diagnostics.
"""

from __future__ import annotations

import re

import pytest

from packages.adapters.contracts import (
    PACK_KIND_ADAPTER,
    AdapterDirection,
    AdapterPack,
    TrustLevel,
)

PACK_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@pytest.mark.parametrize("attribute", ["pack_key", "display_name", "version"])
def test_pack_identity_fields_are_non_empty(all_packs, attribute):
    for pack in all_packs:
        value = getattr(pack, attribute)
        assert value, f"{pack.pack_key}: {attribute} must be non-empty"


def test_pack_key_is_stable_identifier(all_packs):
    for pack in all_packs:
        assert PACK_KEY_PATTERN.match(pack.pack_key), (
            f"{pack.pack_key}: pack_key must be snake_case starting with a letter"
        )


def test_pack_trust_level_is_valid(all_packs):
    for pack in all_packs:
        assert isinstance(pack.trust_level, TrustLevel)


def test_pack_to_pack_manifest_returns_adapter_kind(all_packs):
    for pack in all_packs:
        manifest = pack.to_pack_manifest()
        assert manifest.pack_kind == PACK_KIND_ADAPTER
        assert manifest.pack_key == pack.pack_key
        assert manifest.version == pack.version


def test_pack_adapters_declare_at_least_one_direction(all_packs):
    for pack in all_packs:
        for adapter in pack.adapters:
            assert adapter.supported_directions, (
                f"{pack.pack_key}: adapter {adapter.adapter_key} declares no directions"
            )
            for direction in adapter.supported_directions:
                assert isinstance(direction, AdapterDirection)


def test_pack_renderers_declare_at_least_one_format(all_packs):
    for pack in all_packs:
        for renderer in pack.renderers:
            assert renderer.supported_formats, (
                f"{pack.pack_key}: renderer {renderer.renderer_key} declares no formats"
            )


def test_pack_declares_at_least_one_manifest(all_packs):
    """A pack that ships no adapters and no renderers is a bug."""
    for pack in all_packs:
        assert pack.adapters or pack.renderers, (
            f"{pack.pack_key}: pack declares no adapters and no renderers"
        )


def test_pack_dependency_keys_are_stable_identifiers(all_packs):
    for pack in all_packs:
        for dep in pack.dependencies:
            key = dep
            for op in (">=", "<=", "==", ">", "<"):
                if op in key:
                    key = key.split(op, 1)[0]
                    break
            key = key.strip()
            if not key:
                continue
            assert PACK_KEY_PATTERN.match(key), (
                f"{pack.pack_key}: dependency key {key!r} is not a stable identifier"
            )


def test_pack_publication_relations_are_snake_case(all_packs):
    for pack in all_packs:
        for publication in pack.publication_relations:
            assert publication, f"{pack.pack_key}: empty publication_relations entry"
            assert publication == publication.lower(), (
                f"{pack.pack_key}: publication key {publication!r} is not lowercase"
            )


def test_adapter_and_renderer_keys_are_unique_within_pack(all_packs):
    for pack in all_packs:
        adapter_keys = [adapter.adapter_key for adapter in pack.adapters]
        assert len(adapter_keys) == len(set(adapter_keys)), (
            f"{pack.pack_key}: adapter_key collision within pack"
        )
        renderer_keys = [renderer.renderer_key for renderer in pack.renderers]
        assert len(renderer_keys) == len(set(renderer_keys)), (
            f"{pack.pack_key}: renderer_key collision within pack"
        )


def test_synthetic_external_pack_is_recognised(synthetic_external_pack):
    """Sanity check that the fixture participates in the contract suite."""
    assert isinstance(synthetic_external_pack, AdapterPack)
    assert synthetic_external_pack.pack_key == "synthetic_external"
    assert synthetic_external_pack.trust_level == TrustLevel.COMMUNITY
