"""Fixtures shared by pack contract tests.

The pack registry fixture enumerates every in-repo pack that is
platform-shipped or lives inside a first-party module, plus one
synthetic external pack fixture. The contract suite treats the two
sets equivalently: any assertion that fails for an in-repo pack must
also fail for a hostile external pack.
"""

from __future__ import annotations

import pytest

from packages.adapters.contracts import (
    AdapterDirection,
    AdapterManifest,
    AdapterPack,
    RendererManifest,
    TrustLevel,
)
from packages.adapters.export_renderer import EXPORT_RENDERER_MANIFEST
from packages.adapters.ha_adapters import HA_ADAPTER_PACK
from packages.adapters.prometheus_adapter import PROMETHEUS_ADAPTER_PACK


@pytest.fixture(scope="session")
def in_repo_packs() -> tuple[AdapterPack, ...]:
    """Every in-repo AdapterPack the contract suite must accept."""
    export_pack = AdapterPack(
        pack_key="export_core",
        display_name="Export Renderer Pack",
        version="1.0",
        trust_level=TrustLevel.VERIFIED,
        renderers=(EXPORT_RENDERER_MANIFEST,),
        description="Platform-shipped CSV/JSON/Parquet export renderer.",
    )
    return (HA_ADAPTER_PACK, PROMETHEUS_ADAPTER_PACK, export_pack)


@pytest.fixture(scope="session")
def synthetic_external_pack() -> AdapterPack:
    """A minimal but well-formed third-party pack fixture.

    Used to assert that the contract suite runs on packs that were not
    written with any of the in-repo helpers — the shape of the manifest
    is the only assumption.
    """
    ingest_manifest = AdapterManifest(
        adapter_key="synthetic_external_ingest",
        display_name="Synthetic External Ingest",
        version="0.1.0",
        supported_directions=(AdapterDirection.INGEST,),
        supported_entity_classes=("sensor",),
        credential_requirements=("EXTERNAL_TOKEN",),
        health_check_contract="Ping the /alive endpoint every 30s.",
    )
    renderer_manifest = RendererManifest(
        renderer_key="synthetic_external_renderer",
        display_name="Synthetic External Renderer",
        version="0.1.0",
        supported_formats=("json",),
    )
    return AdapterPack(
        pack_key="synthetic_external",
        display_name="Synthetic External Pack",
        version="0.1.0",
        trust_level=TrustLevel.COMMUNITY,
        adapters=(ingest_manifest,),
        renderers=(renderer_manifest,),
        description="Contract-test fixture for third-party packs.",
        requires_platform_version=">=0.1.0",
        dependencies=(),
        publication_relations=(),
    )


@pytest.fixture(scope="session")
def all_packs(
    in_repo_packs: tuple[AdapterPack, ...], synthetic_external_pack: AdapterPack
) -> tuple[AdapterPack, ...]:
    return in_repo_packs + (synthetic_external_pack,)
