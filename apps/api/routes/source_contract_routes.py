"""Source contract routes: dataset contracts CRUD, diff, and archive."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI

from apps.api.models import ArchivedStateRequest, DatasetContractRequest
from packages.storage.control_plane import ControlPlaneAdminStore
from packages.storage.ingestion_config import (
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
)


def register_source_contract_routes(
    app: FastAPI,
    *,
    resolved_config_repository: ControlPlaneAdminStore,
    require_unsafe_admin: Callable[[], None],
    to_jsonable: Callable[[Any], Any],
    build_dataset_contract_diff: Callable[
        [DatasetContractConfigRecord, DatasetContractConfigRecord], dict[str, Any]
    ],
) -> None:
    @app.get("/config/dataset-contracts")
    async def list_dataset_contracts(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "dataset_contracts": to_jsonable(
                resolved_config_repository.list_dataset_contracts(
                    include_archived=include_archived
                )
            )
        }

    @app.get("/config/dataset-contracts/{dataset_contract_id}")
    async def get_dataset_contract(dataset_contract_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "dataset_contract": to_jsonable(
                resolved_config_repository.get_dataset_contract(dataset_contract_id)
            )
        }

    @app.get("/config/dataset-contracts/{dataset_contract_id}/diff")
    async def get_dataset_contract_diff(
        dataset_contract_id: str,
        other_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        left = resolved_config_repository.get_dataset_contract(dataset_contract_id)
        right = resolved_config_repository.get_dataset_contract(other_id)
        return {"diff": build_dataset_contract_diff(left, right)}

    @app.post("/config/dataset-contracts", status_code=201)
    async def create_dataset_contract(
        payload: DatasetContractRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        dataset_contract = resolved_config_repository.create_dataset_contract(
            DatasetContractConfigCreate(
                dataset_contract_id=payload.dataset_contract_id,
                dataset_name=payload.dataset_name,
                version=payload.version,
                allow_extra_columns=payload.allow_extra_columns,
                columns=tuple(
                    DatasetColumnConfig(
                        name=column.name,
                        type=column.type,
                        required=column.required,
                    )
                    for column in payload.columns
                ),
            )
        )
        return {"dataset_contract": to_jsonable(dataset_contract)}

    @app.patch("/config/dataset-contracts/{dataset_contract_id}/archive")
    async def set_dataset_contract_archived_state(
        dataset_contract_id: str,
        payload: ArchivedStateRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        dataset_contract = resolved_config_repository.set_dataset_contract_archived_state(
            dataset_contract_id,
            archived=payload.archived,
        )
        return {"dataset_contract": to_jsonable(dataset_contract)}
