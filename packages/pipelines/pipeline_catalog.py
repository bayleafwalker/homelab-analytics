from __future__ import annotations

from dataclasses import dataclass

from packages.pipelines.builtin_packages import BUILTIN_TRANSFORMATION_PACKAGE_SPECS
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.shared.extensions import ExtensionRegistry
from packages.storage.control_plane import ConfigCatalogStore
from packages.storage.ingestion_catalog import (
    PublicationDefinitionCreate,
    TransformationPackageCreate,
)


@dataclass(frozen=True)
class PipelinePublicationSpec:
    publication_definition_id: str
    publication_key: str
    name: str
    description: str | None = None


@dataclass(frozen=True)
class PipelinePackageSpec:
    transformation_package_id: str
    handler_key: str
    name: str
    version: int
    description: str | None = None
    publications: tuple[PipelinePublicationSpec, ...] = ()


class PipelineCatalogRegistry:
    def __init__(self) -> None:
        self._packages: dict[str, PipelinePackageSpec] = {}
        self._publication_package_ids: dict[str, str] = {}

    def register(self, package_spec: PipelinePackageSpec) -> None:
        existing = self._packages.get(package_spec.transformation_package_id)
        if existing is not None and existing != package_spec:
            raise ValueError(
                "Pipeline package already registered: "
                f"{package_spec.transformation_package_id}"
            )
        for publication in package_spec.publications:
            existing_package_id = self._publication_package_ids.get(
                publication.publication_definition_id
            )
            if (
                existing_package_id is not None
                and existing_package_id != package_spec.transformation_package_id
            ):
                raise ValueError(
                    "Pipeline publication already registered: "
                    f"{publication.publication_definition_id}"
                )
        self._packages[package_spec.transformation_package_id] = package_spec
        for publication in package_spec.publications:
            self._publication_package_ids[publication.publication_definition_id] = (
                package_spec.transformation_package_id
            )

    def list_packages(self) -> list[PipelinePackageSpec]:
        return [
            self._packages[package_id]
            for package_id in sorted(self._packages)
        ]

    def iter_publications(
        self,
    ) -> list[tuple[PipelinePackageSpec, PipelinePublicationSpec]]:
        publications: list[tuple[PipelinePackageSpec, PipelinePublicationSpec]] = []
        for package_spec in self.list_packages():
            publications.extend(
                (package_spec, publication) for publication in package_spec.publications
            )
        return publications


def build_builtin_pipeline_catalog_registry() -> PipelineCatalogRegistry:
    registry = PipelineCatalogRegistry()
    for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS:
        registry.register(
            PipelinePackageSpec(
                transformation_package_id=spec.transformation_package_id,
                handler_key=spec.handler_key,
                name=spec.name,
                version=spec.version,
                description=spec.description,
                publications=tuple(
                    PipelinePublicationSpec(
                        publication_definition_id=publication.publication_definition_id,
                        publication_key=publication.publication_key,
                        name=publication.name,
                    )
                    for publication in spec.publications
                ),
            )
        )
    return registry


def sync_pipeline_catalog(
    config_repository: ConfigCatalogStore,
    pipeline_catalog_registry: PipelineCatalogRegistry,
    *,
    extension_registry: ExtensionRegistry | None = None,
    promotion_handler_registry: PromotionHandlerRegistry,
) -> None:
    for package_spec in pipeline_catalog_registry.list_packages():
        _sync_transformation_package(
            config_repository,
            package_spec,
            promotion_handler_registry=promotion_handler_registry,
        )
    for package_spec, publication in pipeline_catalog_registry.iter_publications():
        _sync_publication_definition(
            config_repository,
            package_spec,
            publication,
            extension_registry=extension_registry,
            promotion_handler_registry=promotion_handler_registry,
        )


def _sync_transformation_package(
    config_repository: ConfigCatalogStore,
    package_spec: PipelinePackageSpec,
    *,
    promotion_handler_registry: PromotionHandlerRegistry,
) -> None:
    try:
        existing = config_repository.get_transformation_package(
            package_spec.transformation_package_id
        )
    except KeyError:
        try:
            config_repository.create_transformation_package(
                TransformationPackageCreate(
                    transformation_package_id=package_spec.transformation_package_id,
                    name=package_spec.name,
                    handler_key=package_spec.handler_key,
                    version=package_spec.version,
                    description=package_spec.description,
                ),
                promotion_handler_registry=promotion_handler_registry,
            )
        except Exception:
            try:
                existing = config_repository.get_transformation_package(
                    package_spec.transformation_package_id
                )
            except KeyError:
                raise
            _validate_transformation_package(existing, package_spec)
            return
        return

    _validate_transformation_package(existing, package_spec)


def _sync_publication_definition(
    config_repository: ConfigCatalogStore,
    package_spec: PipelinePackageSpec,
    publication_spec: PipelinePublicationSpec,
    *,
    extension_registry: ExtensionRegistry | None,
    promotion_handler_registry: PromotionHandlerRegistry,
) -> None:
    try:
        existing = config_repository.get_publication_definition(
            publication_spec.publication_definition_id
        )
    except KeyError:
        try:
            config_repository.create_publication_definition(
                PublicationDefinitionCreate(
                    publication_definition_id=publication_spec.publication_definition_id,
                    transformation_package_id=package_spec.transformation_package_id,
                    publication_key=publication_spec.publication_key,
                    name=publication_spec.name,
                    description=publication_spec.description,
                ),
                extension_registry=extension_registry,
                promotion_handler_registry=promotion_handler_registry,
            )
        except Exception:
            try:
                existing = config_repository.get_publication_definition(
                    publication_spec.publication_definition_id
                )
            except KeyError:
                raise
            _validate_publication_definition(existing, package_spec, publication_spec)
            return
        return

    _validate_publication_definition(existing, package_spec, publication_spec)


def _validate_transformation_package(existing, package_spec: PipelinePackageSpec) -> None:
    if (
        existing.name != package_spec.name
        or existing.handler_key != package_spec.handler_key
        or existing.version != package_spec.version
        or existing.description != package_spec.description
    ):
        raise ValueError(
            "Registered pipeline package conflicts with persisted control-plane state: "
            f"{package_spec.transformation_package_id}"
        )


def _validate_publication_definition(
    existing,
    package_spec: PipelinePackageSpec,
    publication_spec: PipelinePublicationSpec,
) -> None:
    if (
        existing.transformation_package_id != package_spec.transformation_package_id
        or existing.publication_key != publication_spec.publication_key
        or existing.name != publication_spec.name
        or existing.description != publication_spec.description
    ):
        raise ValueError(
            "Registered pipeline publication conflicts with persisted control-plane state: "
            f"{publication_spec.publication_definition_id}"
        )
