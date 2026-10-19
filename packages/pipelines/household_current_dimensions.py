"""Built-in current-dimension composition: each domain pack owns its readers.

``dim_household_member`` is platform-owned (``transformation_household``) and
is registered here next to the pack readers.
"""

from __future__ import annotations

from packages.domains.finance.pipelines.current_dimensions import (
    FINANCE_CURRENT_DIMENSION_READERS,
)
from packages.domains.homelab.pipelines.current_dimensions import (
    HOMELAB_CURRENT_DIMENSION_READERS,
)
from packages.domains.utilities.pipelines.current_dimensions import (
    UTILITIES_CURRENT_DIMENSION_READERS,
)
from packages.pipelines.current_dimension_registry import (
    CurrentDimensionReader,
    CurrentDimensionRegistry,
    CurrentViewReader,
)
from packages.pipelines.household_models import CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW

HOUSEHOLD_CURRENT_DIMENSION_READERS: dict[str, CurrentDimensionReader] = {
    "dim_household_member": CurrentViewReader(CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW, "member_id"),
}

BUILTIN_CURRENT_DIMENSION_READERS = (
    FINANCE_CURRENT_DIMENSION_READERS,
    UTILITIES_CURRENT_DIMENSION_READERS,
    HOMELAB_CURRENT_DIMENSION_READERS,
    HOUSEHOLD_CURRENT_DIMENSION_READERS,
)


def register_builtin_current_dimension_readers(registry: CurrentDimensionRegistry) -> None:
    for readers in BUILTIN_CURRENT_DIMENSION_READERS:
        for dimension_name, reader in readers.items():
            registry.register(dimension_name, reader)
