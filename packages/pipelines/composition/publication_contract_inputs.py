from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from packages.pipelines.composition.current_dimension_contracts import (
    CURRENT_DIMENSION_CONTRACTS,
)
from packages.pipelines.household_reporting import (
    CURRENT_DIMENSION_RELATIONS,
    PUBLICATION_RELATIONS,
)
from packages.platform.current_dimension_contracts import CurrentDimensionContractDefinition
from packages.platform.publication_contracts import (
    PublicationRelation,
    build_publication_relation_map,
)
from packages.shared.extensions import ExtensionRegistry


@dataclass(frozen=True)
class PublicationContractRegistrations:
    publication_relations: Mapping[str, Any]
    current_dimension_relations: Mapping[str, str]
    current_dimension_contracts: Mapping[
        str,
        CurrentDimensionContractDefinition,
    ]


HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS = PublicationContractRegistrations(
    publication_relations=PUBLICATION_RELATIONS,
    current_dimension_relations=CURRENT_DIMENSION_RELATIONS,
    current_dimension_contracts=CURRENT_DIMENSION_CONTRACTS,
)


def build_household_publication_relation_map(
    *,
    extension_registry: ExtensionRegistry | None = None,
) -> dict[str, PublicationRelation]:
    return build_publication_relation_map(
        base_relations=HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.publication_relations,
        extension_registry=extension_registry,
    )
