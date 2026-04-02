from __future__ import annotations

from fastapi import FastAPI, HTTPException

from apps.api.response_models import (
    PublicationContractModel,
    PublicationContractsResponse,
    PublicationSemanticIndexEntryModel,
    PublicationSemanticIndexResponse,
    UiDescriptorsResponse,
    publication_contract_model_from_dataclass,
    publication_semantic_index_entry_model_from_dataclass,
    ui_descriptor_model_from_dataclass,
)
from packages.pipelines.composition.current_dimension_contracts import (
    CURRENT_DIMENSION_CONTRACTS,
)
from packages.pipelines.household_reporting import (
    CURRENT_DIMENSION_RELATIONS,
    PUBLICATION_RELATIONS,
)
from packages.platform.capability_types import CapabilityPack
from packages.platform.publication_contracts import (
    build_publication_contracts,
    build_publication_relation_map,
    build_ui_descriptor_contracts,
)
from packages.platform.publication_index import (
    build_publication_semantic_index,
    filter_publication_semantic_index,
)
from packages.shared.extensions import ExtensionRegistry


def register_contract_routes(
    app: FastAPI,
    *,
    capability_packs: tuple[CapabilityPack, ...],
    extension_registry: ExtensionRegistry,
) -> None:
    publication_contracts = build_publication_contracts(
        capability_packs,
        publication_relations=build_publication_relation_map(
            base_relations=PUBLICATION_RELATIONS,
            extension_registry=extension_registry,
        ),
        current_dimension_relations=CURRENT_DIMENSION_RELATIONS,
        current_dimension_contracts=CURRENT_DIMENSION_CONTRACTS,
    )
    publication_contracts_by_key = {
        contract.publication_key: contract for contract in publication_contracts
    }
    ui_descriptors = build_ui_descriptor_contracts(capability_packs)
    publication_semantic_index = build_publication_semantic_index(
        publication_contracts,
        ui_descriptors,
    )
    publication_semantic_index_by_key = {
        entry.publication.publication_key: entry for entry in publication_semantic_index
    }

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

    @app.get(
        "/contracts/publication-index",
        response_model=PublicationSemanticIndexResponse,
    )
    async def list_publication_semantic_index(
        query: str | None = None,
        renderer: str | None = None,
        ui_descriptor_key: str | None = None,
    ) -> PublicationSemanticIndexResponse:
        return PublicationSemanticIndexResponse(
            publication_index=[
                publication_semantic_index_entry_model_from_dataclass(entry)
                for entry in filter_publication_semantic_index(
                    publication_semantic_index,
                    query=query,
                    renderer=renderer,
                    ui_descriptor_key=ui_descriptor_key,
                )
            ],
            query=query,
            renderer=renderer,
            ui_descriptor_key=ui_descriptor_key,
        )

    @app.get(
        "/contracts/publication-index/{publication_key}",
        response_model=PublicationSemanticIndexEntryModel,
    )
    async def get_publication_semantic_index_entry(
        publication_key: str,
    ) -> PublicationSemanticIndexEntryModel:
        entry = publication_semantic_index_by_key.get(publication_key)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown publication semantic index entry: {publication_key}",
            )
        return publication_semantic_index_entry_model_from_dataclass(entry)

    @app.get("/contracts/ui-descriptors", response_model=UiDescriptorsResponse)
    async def list_ui_descriptors() -> UiDescriptorsResponse:
        return UiDescriptorsResponse(
            ui_descriptors=[
                ui_descriptor_model_from_dataclass(descriptor)
                for descriptor in ui_descriptors
            ]
        )
