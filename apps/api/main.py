from __future__ import annotations

import uvicorn

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionRegistry, load_extension_registry
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=RunMetadataRepository(settings.metadata_database_path),
    )


def build_subscription_service(settings: AppSettings) -> SubscriptionService:
    return SubscriptionService(
        landing_root=settings.landing_root,
        metadata_repository=RunMetadataRepository(settings.metadata_database_path),
    )


def build_contract_price_service(settings: AppSettings) -> ContractPriceService:
    return ContractPriceService(
        landing_root=settings.landing_root,
        metadata_repository=RunMetadataRepository(settings.metadata_database_path),
    )


def build_transformation_service(settings: AppSettings) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    return TransformationService(DuckDBStore.open(str(analytics_path)))


def build_extension_registry(settings: AppSettings) -> ExtensionRegistry:
    return load_extension_registry(
        extension_paths=settings.extension_paths,
        extension_modules=settings.extension_modules,
    )


def build_app(settings: AppSettings | None = None):
    resolved_settings = settings or AppSettings.from_env()
    return create_app(
        build_service(resolved_settings),
        build_extension_registry(resolved_settings),
        config_repository=IngestionConfigRepository(
            resolved_settings.resolved_config_database_path
        ),
        transformation_service=build_transformation_service(resolved_settings),
        subscription_service=build_subscription_service(resolved_settings),
        contract_price_service=build_contract_price_service(resolved_settings),
    )


def main() -> int:
    settings = AppSettings.from_env()
    uvicorn.run(
        build_app(settings),
        host=settings.api_host,
        port=settings.api_port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
