"""Built-in current-dimension composition: each domain pack owns its readers."""

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
from packages.pipelines.current_dimension_registry import CurrentDimensionRegistry

BUILTIN_CURRENT_DIMENSION_READERS = (
    FINANCE_CURRENT_DIMENSION_READERS,
    UTILITIES_CURRENT_DIMENSION_READERS,
    HOMELAB_CURRENT_DIMENSION_READERS,
)


def register_builtin_current_dimension_readers(registry: CurrentDimensionRegistry) -> None:
    for readers in BUILTIN_CURRENT_DIMENSION_READERS:
        for dimension_name, reader in readers.items():
            registry.register(dimension_name, reader)
