from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar

from packages.pipelines.promotion_types import PromotionResult
from packages.shared.extensions import ExtensionRegistry
from packages.storage.blob import BlobStore
from packages.storage.control_plane import ContractCatalogStore
from packages.storage.run_metadata import RunMetadataStore

if TYPE_CHECKING:
    from packages.pipelines.transformation_service import TransformationService


PromotionRunner = Callable[["PromotionRuntime"], PromotionResult]
ServiceT = TypeVar("ServiceT")
RowT = TypeVar("RowT")


@dataclass(frozen=True)
class PromotionRuntime:
    run_id: str
    landing_root: Path
    metadata_repository: RunMetadataStore
    config_repository: ContractCatalogStore
    transformation_service: TransformationService
    blob_store: BlobStore | None = None
    extension_registry: ExtensionRegistry | None = None


@dataclass(frozen=True)
class PromotionHandler:
    handler_key: str
    default_publications: tuple[str, ...]
    supported_publications: tuple[str, ...]
    runner: PromotionRunner


@dataclass(frozen=True)
class CanonicalPromotionProcessor(Generic[ServiceT, RowT]):
    build_runtime_service: Callable[[PromotionRuntime], ServiceT]
    get_run: Callable[[ServiceT, str], Any]
    get_canonical_rows: Callable[[ServiceT, str], list[RowT]]
    serialize_row: Callable[[RowT], dict[str, Any]]
    count_existing: Callable[["TransformationService", str], int]
    load_rows: Callable[
        ["TransformationService", list[dict[str, Any]], str, str],
        int,
    ]
    required_header: set[str] | None = None
    contract_mismatch_reason: str | None = None


def _skipped_result(
    run_id: str,
    *,
    publication_keys: tuple[str, ...],
    skip_reason: str,
    marts_refreshed: list[str] | None = None,
) -> PromotionResult:
    return PromotionResult(
        run_id=run_id,
        facts_loaded=0,
        marts_refreshed=marts_refreshed or [],
        publication_keys=list(publication_keys),
        skipped=True,
        skip_reason=skip_reason,
    )


def run_canonical_promotion(
    run_id: str,
    *,
    service: ServiceT,
    transformation_service: "TransformationService",
    processor: CanonicalPromotionProcessor[ServiceT, RowT],
    publication_keys: tuple[str, ...],
    refresh_publication_keys: tuple[str, ...] = (),
) -> PromotionResult:
    run = processor.get_run(service, run_id)
    if not run.passed:
        return _skipped_result(
            run_id,
            publication_keys=publication_keys,
            skip_reason=(f"run status is {run.status.value!r}; only passed runs are promoted"),
        )
    if processor.required_header and not processor.required_header.issubset(set(run.header)):
        return _skipped_result(
            run_id,
            publication_keys=publication_keys,
            skip_reason=processor.contract_mismatch_reason
            or "run does not match the canonical contract",
        )
    if processor.count_existing(transformation_service, run_id) > 0:
        marts_refreshed = transformation_service.refresh_publications(refresh_publication_keys)
        return _skipped_result(
            run_id,
            publication_keys=publication_keys,
            marts_refreshed=marts_refreshed,
            skip_reason="run already promoted",
        )

    row_dicts = [
        processor.serialize_row(row) for row in processor.get_canonical_rows(service, run_id)
    ]
    facts_loaded = processor.load_rows(
        transformation_service,
        row_dicts,
        run_id,
        run.source_name,
    )
    marts_refreshed = transformation_service.refresh_publications(refresh_publication_keys)
    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=marts_refreshed,
        publication_keys=list(publication_keys),
    )


def build_canonical_promotion_handler(
    *,
    handler_key: str,
    default_publications: tuple[str, ...],
    refresh_publication_keys: tuple[str, ...] = (),
    processor: CanonicalPromotionProcessor[Any, Any],
    supported_publications: tuple[str, ...] | None = None,
) -> PromotionHandler:
    resolved_supported_publications = supported_publications or default_publications

    def run(runtime: PromotionRuntime) -> PromotionResult:
        return run_canonical_promotion(
            runtime.run_id,
            service=processor.build_runtime_service(runtime),
            transformation_service=runtime.transformation_service,
            processor=processor,
            publication_keys=default_publications,
            refresh_publication_keys=refresh_publication_keys,
        )

    return PromotionHandler(
        handler_key=handler_key,
        default_publications=default_publications,
        supported_publications=resolved_supported_publications,
        runner=run,
    )


class PromotionHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, PromotionHandler] = {}

    def register(self, handler: PromotionHandler) -> None:
        existing = self._handlers.get(handler.handler_key)
        if existing is not None and existing != handler:
            raise ValueError(f"Promotion handler already registered: {handler.handler_key}")
        self._handlers[handler.handler_key] = handler

    def get(self, handler_key: str) -> PromotionHandler:
        try:
            return self._handlers[handler_key]
        except KeyError as exc:
            raise ValueError(f"Unsupported transformation package handler: {handler_key}") from exc

    def list(self) -> list[PromotionHandler]:
        return [self._handlers[handler_key] for handler_key in sorted(self._handlers)]


_DEFAULT_PROMOTION_HANDLER_REGISTRY: PromotionHandlerRegistry | None = None


def get_default_promotion_handler_registry() -> PromotionHandlerRegistry:
    global _DEFAULT_PROMOTION_HANDLER_REGISTRY
    if _DEFAULT_PROMOTION_HANDLER_REGISTRY is None:
        from packages.pipelines.builtin_promotion_handlers import (
            register_builtin_promotion_handlers,
        )

        registry = PromotionHandlerRegistry()
        register_builtin_promotion_handlers(registry)
        _DEFAULT_PROMOTION_HANDLER_REGISTRY = registry
    return _DEFAULT_PROMOTION_HANDLER_REGISTRY
