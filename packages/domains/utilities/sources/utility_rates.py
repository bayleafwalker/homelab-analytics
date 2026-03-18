"""Utility rates source definition for the utilities capability pack."""
from __future__ import annotations

from packages.platform.capability_types import SourceDefinition

UTILITY_RATES_SOURCE = SourceDefinition(
    dataset_name="utility_rates",
    display_name="Utility Rates",
    description="Electricity and gas tariff rates for utility cost tracking.",
    retry_kind="utility_rates",
)
