from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from packages.pipelines.transformation_service import TransformationService


TransformationLoadHandler = Callable[
    ["TransformationService", list[dict[str, Any]], str | None, date | None, str | None],
    int,
]
TransformationCountHandler = Callable[["TransformationService", str | None], int]


@dataclass(frozen=True)
class TransformationDomainHandler:
    domain_key: str
    load_rows: TransformationLoadHandler
    count_rows: TransformationCountHandler


class TransformationDomainRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, TransformationDomainHandler] = {}

    def register(self, handler: TransformationDomainHandler) -> None:
        existing = self._handlers.get(handler.domain_key)
        if existing is not None and existing != handler:
            raise ValueError(f"Transformation domain already registered: {handler.domain_key}")
        self._handlers[handler.domain_key] = handler

    def load(
        self,
        transformation_service: "TransformationService",
        domain_key: str,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return self._get(domain_key).load_rows(
            transformation_service,
            rows,
            run_id,
            effective_date,
            source_system,
        )

    def count(
        self,
        transformation_service: "TransformationService",
        domain_key: str,
        *,
        run_id: str | None = None,
    ) -> int:
        return self._get(domain_key).count_rows(transformation_service, run_id)

    def domain_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def _get(self, domain_key: str) -> TransformationDomainHandler:
        try:
            return self._handlers[domain_key]
        except KeyError as exc:
            raise ValueError(f"Unsupported transformation domain: {domain_key}") from exc


def build_builtin_transformation_domain_registry() -> TransformationDomainRegistry:
    registry = TransformationDomainRegistry()
    registry.register(
        TransformationDomainHandler(
            domain_key="account_transactions",
            load_rows=lambda service, rows, run_id, effective_date, source_system: (
                service.load_transactions(
                    rows,
                    run_id=run_id,
                    effective_date=effective_date,
                    source_system=source_system,
                )
            ),
            count_rows=lambda service, run_id: service.count_transactions(run_id=run_id),
        )
    )
    registry.register(
        TransformationDomainHandler(
            domain_key="subscriptions",
            load_rows=lambda service, rows, run_id, effective_date, source_system: (
                service.load_subscriptions(
                    rows,
                    run_id=run_id,
                    effective_date=effective_date,
                    source_system=source_system,
                )
            ),
            count_rows=lambda service, run_id: service.count_subscriptions(run_id=run_id),
        )
    )
    registry.register(
        TransformationDomainHandler(
            domain_key="contract_prices",
            load_rows=lambda service, rows, run_id, effective_date, source_system: (
                service.load_contract_prices(
                    rows,
                    run_id=run_id,
                    effective_date=effective_date,
                    source_system=source_system,
                )
            ),
            count_rows=lambda service, run_id: service.count_contract_prices(run_id=run_id),
        )
    )
    registry.register(
        TransformationDomainHandler(
            domain_key="utility_usage",
            load_rows=lambda service, rows, run_id, effective_date, source_system: (
                service.load_utility_usage(
                    rows,
                    run_id=run_id,
                    effective_date=effective_date,
                    source_system=source_system,
                )
            ),
            count_rows=lambda service, run_id: service.count_utility_usage(run_id=run_id),
        )
    )
    registry.register(
        TransformationDomainHandler(
            domain_key="utility_bills",
            load_rows=lambda service, rows, run_id, effective_date, source_system: (
                service.load_bills(
                    rows,
                    run_id=run_id,
                    effective_date=effective_date,
                    source_system=source_system,
                )
            ),
            count_rows=lambda service, run_id: service.count_bills(run_id=run_id),
        )
    )
    return registry


_DEFAULT_TRANSFORMATION_DOMAIN_REGISTRY: TransformationDomainRegistry | None = None


def get_default_transformation_domain_registry() -> TransformationDomainRegistry:
    global _DEFAULT_TRANSFORMATION_DOMAIN_REGISTRY
    if _DEFAULT_TRANSFORMATION_DOMAIN_REGISTRY is None:
        _DEFAULT_TRANSFORMATION_DOMAIN_REGISTRY = build_builtin_transformation_domain_registry()
    return _DEFAULT_TRANSFORMATION_DOMAIN_REGISTRY
