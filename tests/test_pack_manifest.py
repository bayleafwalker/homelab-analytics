"""Tests for the unified PackManifest and its AdapterPack specialization."""

from __future__ import annotations

from packages.adapters.contracts import (
    PACK_KIND_ADAPTER,
    PACK_KIND_DOMAIN,
    VALID_PACK_KINDS,
    AdapterDirection,
    AdapterManifest,
    AdapterPack,
    PackManifest,
    TrustLevel,
)
from packages.adapters.ha_adapters import HA_ADAPTER_PACK


def test_pack_manifest_defaults_to_adapter_kind():
    manifest = PackManifest(
        pack_key="example",
        display_name="Example",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
    )
    assert manifest.pack_kind == PACK_KIND_ADAPTER


def test_pack_manifest_accepts_domain_kind():
    manifest = PackManifest(
        pack_key="finance",
        display_name="Finance",
        version="1.0",
        trust_level=TrustLevel.VERIFIED,
        pack_kind=PACK_KIND_DOMAIN,
    )
    assert manifest.pack_kind in VALID_PACK_KINDS
    assert manifest.pack_kind == "domain"


def test_ha_adapter_pack_loads_unchanged():
    assert HA_ADAPTER_PACK.pack_key == "ha_core"
    assert HA_ADAPTER_PACK.trust_level == TrustLevel.VERIFIED
    assert len(HA_ADAPTER_PACK.adapters) == 3


def test_adapter_pack_exposes_pack_manifest_view():
    ingest = AdapterManifest(
        adapter_key="unit_test_ingest",
        display_name="Unit Test Ingest",
        version="1.0",
        supported_directions=(AdapterDirection.INGEST,),
    )
    pack = AdapterPack(
        pack_key="unit_test_pack",
        display_name="Unit Test Pack",
        version="0.1.0",
        trust_level=TrustLevel.LOCAL,
        adapters=(ingest,),
        requires_platform_version=">=0.1.0",
        dependencies=("ha_core",),
        publication_relations=("rpt_current_dim_entity",),
    )

    manifest = pack.to_pack_manifest()

    assert manifest.pack_key == "unit_test_pack"
    assert manifest.pack_kind == PACK_KIND_ADAPTER
    assert manifest.trust_level == TrustLevel.LOCAL
    assert manifest.requires_platform_version == ">=0.1.0"
    assert manifest.dependencies == ("ha_core",)
    assert manifest.publication_relations == ("rpt_current_dim_entity",)


def test_ha_adapter_pack_to_pack_manifest_is_adapter_kind_verified():
    manifest = HA_ADAPTER_PACK.to_pack_manifest()
    assert manifest.pack_kind == PACK_KIND_ADAPTER
    assert manifest.trust_level == TrustLevel.VERIFIED


def test_adapter_pack_defaults_do_not_change_existing_call_sites():
    pack = AdapterPack(
        pack_key="minimal",
        display_name="Minimal",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
    )
    assert pack.dependencies == ()
    assert pack.publication_relations == ()
    assert pack.requires_platform_version == ""
