"""Canonical builtin capability pack list for all application entrypoints.

Both the API (apps/api/main.py) and worker (apps/worker/runtime.py) must
register the same set of builtin packs so that publication contracts,
freshness configs, and pipeline catalogs are consistent across runtimes.
Import BUILTIN_CAPABILITY_PACKS from here — do not maintain separate lists.
"""
from __future__ import annotations

from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.platform.capability_types import CapabilityPack

BUILTIN_CAPABILITY_PACKS: tuple[CapabilityPack, ...] = (
    FINANCE_PACK,
    UTILITIES_PACK,
    OVERVIEW_PACK,
    HOMELAB_PACK,
)
