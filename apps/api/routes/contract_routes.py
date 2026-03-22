from __future__ import annotations

from fastapi import FastAPI, HTTPException

from apps.api.response_models import (
    PublicationContractModel,
    PublicationContractsResponse,
    UiDescriptorsResponse,
    publication_contract_model_from_dataclass,
    ui_descriptor_model_from_dataclass,
)
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.builtin_reporting import PUBLICATION_RELATIONS
from packages.platform.capability_types import CapabilityPack
from packages.platform.publication_contracts import (
    build_publication_contracts,
    build_ui_descriptor_contracts,
)

PUBLIC_CONTRACT_PACK_NAMES = {
    FINANCE_PACK.name,
    UTILITIES_PACK.name,
    OVERVIEW_PACK.name,
    HOMELAB_PACK.name,
}


def register_contract_routes(
    app: FastAPI,
    *,
    capability_packs: tuple[CapabilityPack, ...],
) -> None:
    public_capability_packs = tuple(
        pack for pack in capability_packs if pack.name in PUBLIC_CONTRACT_PACK_NAMES
    )
    if not public_capability_packs:
        public_capability_packs = (
            FINANCE_PACK,
            UTILITIES_PACK,
            OVERVIEW_PACK,
            HOMELAB_PACK,
        )
    publication_contracts = build_publication_contracts(
        public_capability_packs,
        publication_relations=PUBLICATION_RELATIONS,
    )
    publication_contracts_by_key = {
        contract.publication_key: contract for contract in publication_contracts
    }
    ui_descriptors = build_ui_descriptor_contracts(public_capability_packs)

    @app.get("/contracts/publications", response_model=PublicationContractsResponse)
    async def list_publication_contracts() -> PublicationContractsResponse:
        return PublicationContractsResponse(
            publication_contracts=[
                publication_contract_model_from_dataclass(contract)
                for contract in publication_contracts
            ]
        )

    @app.get(
        "/contracts/publications/{publication_key}",
        response_model=PublicationContractModel,
    )
    async def get_publication_contract(publication_key: str) -> PublicationContractModel:
        contract = publication_contracts_by_key.get(publication_key)
        if contract is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown publication contract: {publication_key}",
            )
        return publication_contract_model_from_dataclass(contract)

    @app.get("/contracts/ui-descriptors", response_model=UiDescriptorsResponse)
    async def list_ui_descriptors() -> UiDescriptorsResponse:
        return UiDescriptorsResponse(
            ui_descriptors=[
                ui_descriptor_model_from_dataclass(descriptor)
                for descriptor in ui_descriptors
            ]
        )
