from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from packages.pipelines.composition.current_dimension_contracts import (
    CURRENT_DIMENSION_CONTRACTS,
)
from packages.pipelines.household_reporting import (
    CURRENT_DIMENSION_RELATIONS,
    PUBLICATION_RELATIONS,
)
from packages.platform.capability_types import CapabilityPack
from packages.platform.current_dimension_contracts import CurrentDimensionContractDefinition
from packages.platform.publication_contracts import (
    PublicationContract,
    PublicationRelation,
    build_publication_contracts,
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


def build_policy_referenceable_contracts(
    capability_packs: Sequence[CapabilityPack],
    *,
    extension_registry: ExtensionRegistry | None = None,
) -> list[PublicationContract]:
    """Publications a policy may reference, and that evaluation can read.

    Deliberately narrower than the full contract listing: the current
    dimension registrations are excluded, because the policy evaluator
    resolves a publication key to a relation from exactly this set. A key
    outside it is dropped at fetch time, so a policy referencing one would be
    accepted at create and then evaluate ``unavailable`` forever.

    Both the create-time allowlist and the evaluator's relation map are built
    from this function so the two cannot drift apart.
    """
    return build_publication_contracts(
        capability_packs,
        publication_relations=build_household_publication_relation_map(
            extension_registry=extension_registry,
        ),
    )
