"""Contract prices source definition for the utilities capability pack."""
from __future__ import annotations

from packages.platform.capability_types import SourceDefinition

CONTRACT_PRICES_SOURCE = SourceDefinition(
    dataset_name="contract_prices",
    display_name="Contract Prices",
    description="Contracted unit prices for utilities and services (electricity tariffs, etc.).",
    retry_kind="contract_prices",
)
