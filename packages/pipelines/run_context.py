from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Mapping, cast

if TYPE_CHECKING:
    from packages.storage.blob import BlobStore


@dataclass(frozen=True)
class RunControlContext:
    source_asset_id: str | None = None
    source_system_id: str | None = None
    dataset_contract_id: str | None = None
    column_mapping_id: str | None = None
    ingestion_definition_id: str | None = None
    retry_of_run_id: str | None = None

    def as_manifest_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in asdict(self).items()
            if isinstance(value, str) and value
        }

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, object] | None,
    ) -> RunControlContext | None:
        if payload is None:
            return None
        context = cls(
            source_asset_id=_optional_string(payload.get("source_asset_id")),
            source_system_id=_optional_string(payload.get("source_system_id")),
            dataset_contract_id=_optional_string(payload.get("dataset_contract_id")),
            column_mapping_id=_optional_string(payload.get("column_mapping_id")),
            ingestion_definition_id=_optional_string(
                payload.get("ingestion_definition_id")
            ),
            retry_of_run_id=_optional_string(payload.get("retry_of_run_id")),
        )
        if all(value is None for value in asdict(context).values()):
            return None
        return context


def read_run_manifest(
    blob_store: BlobStore,
    manifest_path: str,
) -> dict[str, Any]:
    payload = json.loads(blob_store.read_bytes(manifest_path).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Run manifest at {manifest_path} is not a JSON object.")
    return cast(dict[str, Any], payload)


def read_run_context(
    blob_store: BlobStore,
    manifest_path: str,
) -> RunControlContext | None:
    return run_context_from_manifest(read_run_manifest(blob_store, manifest_path))


def run_context_from_manifest(
    manifest: Mapping[str, Any],
) -> RunControlContext | None:
    context = manifest.get("context")
    if not isinstance(context, Mapping):
        return None
    return RunControlContext.from_mapping(context)


def merge_run_context(
    base: RunControlContext | None = None,
    *,
    source_asset_id: str | None = None,
    source_system_id: str | None = None,
    dataset_contract_id: str | None = None,
    column_mapping_id: str | None = None,
    ingestion_definition_id: str | None = None,
    retry_of_run_id: str | None = None,
) -> RunControlContext | None:
    context = RunControlContext(
        source_asset_id=source_asset_id or (base.source_asset_id if base else None),
        source_system_id=source_system_id or (base.source_system_id if base else None),
        dataset_contract_id=dataset_contract_id
        or (base.dataset_contract_id if base else None),
        column_mapping_id=column_mapping_id or (base.column_mapping_id if base else None),
        ingestion_definition_id=ingestion_definition_id
        or (base.ingestion_definition_id if base else None),
        retry_of_run_id=retry_of_run_id or (base.retry_of_run_id if base else None),
    )
    if all(value is None for value in asdict(context).values()):
        return None
    return context


def _optional_string(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None
