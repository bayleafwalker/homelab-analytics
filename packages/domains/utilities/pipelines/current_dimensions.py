"""Utilities-pack current-dimension readers."""

from __future__ import annotations

from packages.domains.utilities.pipelines.utility_models import CURRENT_DIM_METER_VIEW
from packages.pipelines.current_dimension_registry import (
    CurrentDimensionReader,
    CurrentViewReader,
)

UTILITIES_CURRENT_DIMENSION_READERS: dict[str, CurrentDimensionReader] = {
    "dim_meter": CurrentViewReader(CURRENT_DIM_METER_VIEW, "meter_id"),
}
