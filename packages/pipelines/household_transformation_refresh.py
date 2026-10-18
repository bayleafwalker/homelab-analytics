"""Built-in publication refresh composition: each domain pack owns its handlers."""

from __future__ import annotations

from packages.domains.finance.pipelines.publication_refresh import (
    FINANCE_PUBLICATION_REFRESH_HANDLERS,
)
from packages.domains.homelab.pipelines.publication_refresh import (
    HOMELAB_PUBLICATION_REFRESH_HANDLERS,
)
from packages.domains.overview.pipelines.publication_refresh import (
    OVERVIEW_PUBLICATION_REFRESH_HANDLERS,
)
from packages.domains.utilities.pipelines.publication_refresh import (
    UTILITIES_PUBLICATION_REFRESH_HANDLERS,
)
from packages.pipelines.household_packages import BUILTIN_TRANSFORMATION_PACKAGE_SPECS
from packages.pipelines.household_reporting import PUBLICATION_RELATIONS
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshHandler,
    PublicationRefreshRegistry,
)


def _compose_domain_refresh_handlers(
    *tables: dict[str, PublicationRefreshHandler],
) -> dict[str, PublicationRefreshHandler]:
    composed: dict[str, PublicationRefreshHandler] = {}
    for table in tables:
        overlap = sorted(set(composed) & set(table))
        if overlap:
            raise ValueError(f"Publication refresh handlers declared by two packs: {overlap}")
        composed.update(table)
    return composed


BUILTIN_PUBLICATION_REFRESH_HANDLERS: dict[str, PublicationRefreshHandler] = (
    _compose_domain_refresh_handlers(
        FINANCE_PUBLICATION_REFRESH_HANDLERS,
        UTILITIES_PUBLICATION_REFRESH_HANDLERS,
        OVERVIEW_PUBLICATION_REFRESH_HANDLERS,
        HOMELAB_PUBLICATION_REFRESH_HANDLERS,
    )
)


def register_builtin_publication_refresh_handlers(
    registry: PublicationRefreshRegistry,
) -> None:
    for publication_key, handler in BUILTIN_PUBLICATION_REFRESH_HANDLERS.items():
        registry.register(publication_key, handler)


def validate_builtin_publication_refresh_handlers() -> None:
    declared_publications = set(PUBLICATION_RELATIONS)
    handled_publications = set(BUILTIN_PUBLICATION_REFRESH_HANDLERS)
    for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS:
        refresh_keys = set(spec.refresh_publication_keys)
        if not refresh_keys <= declared_publications:
            unknown = sorted(refresh_keys - declared_publications)
            raise ValueError(
                "Built-in transformation package refresh publications are not declared in the reporting registry: "
                f"{spec.transformation_package_id}: {unknown}"
            )
        if not refresh_keys <= handled_publications:
            missing = sorted(refresh_keys - handled_publications)
            raise ValueError(
                "Built-in transformation package refresh publications are not handled by the transformation refresh registry: "
                f"{spec.transformation_package_id}: {missing}"
            )


validate_builtin_publication_refresh_handlers()
