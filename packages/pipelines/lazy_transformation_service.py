from __future__ import annotations

from typing import Callable

from packages.pipelines.transformation_service import TransformationService


class LazyTransformationService:
    def __init__(self, factory: Callable[[], TransformationService]) -> None:
        self._factory = factory
        self._service: TransformationService | None = None

    def _get_service(self) -> TransformationService:
        if self._service is None:
            self._service = self._factory()
        return self._service

    def __getattr__(self, name: str):
        return getattr(self._get_service(), name)

    def close(self) -> None:
        if self._service is None:
            return
        self._service.store.close()
