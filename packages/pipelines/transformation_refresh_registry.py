from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from packages.pipelines.transformation_service import TransformationService


PublicationRefreshHandler = Callable[["TransformationService"], int]


class PublicationRefreshRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, PublicationRefreshHandler] = {}

    def register(
        self,
        publication_key: str,
        handler: PublicationRefreshHandler,
    ) -> None:
        existing = self._handlers.get(publication_key)
        if existing is not None and existing is not handler:
            raise ValueError(
                f"Transformation publication refresh handler already registered: {publication_key}"
            )
        self._handlers[publication_key] = handler

    def refresh(
        self,
        transformation_service: "TransformationService",
        publication_keys: list[str] | tuple[str, ...],
    ) -> list[str]:
        refreshed: list[str] = []
        seen: set[str] = set()
        for publication_key in publication_keys:
            if publication_key in seen:
                continue
            try:
                handler = self._handlers[publication_key]
            except KeyError as exc:
                raise ValueError(
                    f"Unsupported transformation publication refresh: {publication_key}"
                ) from exc
            handler(transformation_service)
            refreshed.append(publication_key)
            seen.add(publication_key)
        return refreshed

    def publication_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))


_DEFAULT_PUBLICATION_REFRESH_REGISTRY: PublicationRefreshRegistry | None = None


def get_default_publication_refresh_registry() -> PublicationRefreshRegistry:
    global _DEFAULT_PUBLICATION_REFRESH_REGISTRY
    if _DEFAULT_PUBLICATION_REFRESH_REGISTRY is None:
        from packages.pipelines.builtin_transformation_refresh import (
            register_builtin_publication_refresh_handlers,
        )

        registry = PublicationRefreshRegistry()
        register_builtin_publication_refresh_handlers(registry)
        _DEFAULT_PUBLICATION_REFRESH_REGISTRY = registry
    return _DEFAULT_PUBLICATION_REFRESH_REGISTRY
