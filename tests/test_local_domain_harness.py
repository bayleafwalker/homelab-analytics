from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.worker.main import main
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import (
    ACCOUNT_ASSET_ID,
    ACCOUNT_DEFINITION_ID,
    create_account_configuration,
)
from tests.account_test_support import (
    FIXTURES as ACCOUNT_FIXTURES,
)
from tests.contract_price_test_support import (
    CONTRACT_PRICE_ASSET_ID,
    CONTRACT_PRICE_DEFINITION_ID,
    create_contract_price_configuration,
)
from tests.contract_price_test_support import (
    FIXTURES as CONTRACT_PRICE_FIXTURES,
)
from tests.subscription_test_support import (
    FIXTURES as SUBSCRIPTION_FIXTURES,
)
from tests.subscription_test_support import (
    SUBSCRIPTION_ASSET_ID,
    SUBSCRIPTION_DEFINITION_ID,
    create_subscription_configuration,
)
from tests.utility_test_support import (
    FIXTURES,
    UTILITY_BILLS_ASSET_ID,
    UTILITY_BILLS_DEFINITION_ID,
    UTILITY_USAGE_ASSET_ID,
    UTILITY_USAGE_DEFINITION_ID,
    create_utility_configuration,
)

pytestmark = [pytest.mark.e2e]


def _make_settings(temp_root: Path) -> AppSettings:
    return AppSettings(
        data_dir=temp_root,
        landing_root=temp_root / "landing",
        metadata_database_path=temp_root / "metadata" / "runs.db",
        account_transactions_inbox_dir=temp_root / "inbox" / "account-transactions",
        processed_files_dir=temp_root / "processed" / "account-transactions",
        failed_files_dir=temp_root / "failed" / "account-transactions",
        analytics_database_path=temp_root / "analytics" / "warehouse.duckdb",
        config_database_path=temp_root / "config.db",
        api_host="127.0.0.1",
        api_port=8090,
        web_host="127.0.0.1",
        web_port=8091,
        worker_poll_interval_seconds=1,
    )


def _run_worker_json(args: list[str], settings: AppSettings) -> dict[str, object]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(args, stdout=stdout, stderr=stderr, settings=settings)
    assert exit_code == 0, stderr.getvalue()
    return json.loads(stdout.getvalue())


def _build_client(
    settings: AppSettings,
    *,
    config_repository: IngestionConfigRepository | None = None,
    subscription_service: SubscriptionService | None = None,
    contract_price_service: ContractPriceService | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            AccountTransactionService(
                landing_root=settings.landing_root,
                metadata_repository=RunMetadataRepository(settings.metadata_database_path),
            ),
            config_repository=config_repository,
            transformation_service=TransformationService(
                DuckDBStore.open(str(settings.resolved_analytics_database_path))
            ),
            subscription_service=subscription_service,
            contract_price_service=contract_price_service,
        )
    )


def test_account_local_domain_harness() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        settings = _make_settings(temp_root)
        inbox_dir = temp_root / "inbox" / "configured-account-transactions"
        processed_dir = temp_root / "processed" / "configured-account-transactions"
        failed_dir = temp_root / "failed" / "configured-account-transactions"
        inbox_dir.mkdir(parents=True)
        shutil.copyfile(
            ACCOUNT_FIXTURES / "configured_account_transactions_source.csv",
            inbox_dir / "configured_account_transactions_source.csv",
        )

        config_repository = IngestionConfigRepository(settings.resolved_config_database_path)
        create_account_configuration(
            config_repository,
            include_ingestion_definitions=True,
            inbox=inbox_dir,
            processed=processed_dir,
            failed=failed_dir,
        )

        global_preflight = _run_worker_json(["verify-config"], settings)
        asset_preflight = _run_worker_json(
            ["verify-config", "--source-asset-id", ACCOUNT_ASSET_ID],
            settings,
        )
        definition_preflight = _run_worker_json(
            ["verify-config", "--ingestion-definition-id", ACCOUNT_DEFINITION_ID],
            settings,
        )

        assert global_preflight["report"]["passed"] is True
        assert global_preflight["report"]["checked"]["source_assets"] == 1
        assert global_preflight["report"]["checked"]["ingestion_definitions"] == 1
        assert asset_preflight["report"]["passed"] is True
        assert asset_preflight["report"]["scope"]["source_asset_id"] == ACCOUNT_ASSET_ID
        assert definition_preflight["report"]["passed"] is True
        assert (
            definition_preflight["report"]["scope"]["ingestion_definition_id"]
            == ACCOUNT_DEFINITION_ID
        )

        ingest_payload = _run_worker_json(
            ["process-ingestion-definition", ACCOUNT_DEFINITION_ID],
            settings,
        )
        assert ingest_payload["result"]["processed_files"] == 1
        assert len(ingest_payload["promotions"]) == 1
        assert ingest_payload["promotions"][0]["facts_loaded"] == 2

        report_payload = _run_worker_json(["report-monthly-cashflow"], settings)
        assert report_payload["rows"][0]["net"] == "2365.8500"

        client = _build_client(settings, config_repository=config_repository)
        response = client.get("/reports/monthly-cashflow")
        assert response.status_code == 200
        assert response.json()["rows"][0]["net"] == "2365.8500"


def test_subscriptions_local_domain_harness() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        settings = _make_settings(temp_root)
        inbox_dir = temp_root / "inbox" / "configured-subscriptions"
        processed_dir = temp_root / "processed" / "configured-subscriptions"
        failed_dir = temp_root / "failed" / "configured-subscriptions"
        inbox_dir.mkdir(parents=True)
        shutil.copyfile(
            SUBSCRIPTION_FIXTURES / "subscriptions_valid.csv",
            inbox_dir / "subscriptions_valid.csv",
        )

        config_repository = IngestionConfigRepository(settings.resolved_config_database_path)
        create_subscription_configuration(
            config_repository,
            include_ingestion_definitions=True,
            inbox=inbox_dir,
            processed=processed_dir,
            failed=failed_dir,
        )

        global_preflight = _run_worker_json(["verify-config"], settings)
        asset_preflight = _run_worker_json(
            ["verify-config", "--source-asset-id", SUBSCRIPTION_ASSET_ID],
            settings,
        )
        definition_preflight = _run_worker_json(
            ["verify-config", "--ingestion-definition-id", SUBSCRIPTION_DEFINITION_ID],
            settings,
        )

        assert global_preflight["report"]["passed"] is True
        assert global_preflight["report"]["checked"]["source_assets"] == 1
        assert global_preflight["report"]["checked"]["ingestion_definitions"] == 1
        assert asset_preflight["report"]["passed"] is True
        assert asset_preflight["report"]["scope"]["source_asset_id"] == SUBSCRIPTION_ASSET_ID
        assert definition_preflight["report"]["passed"] is True
        assert (
            definition_preflight["report"]["scope"]["ingestion_definition_id"]
            == SUBSCRIPTION_DEFINITION_ID
        )

        ingest_payload = _run_worker_json(
            ["process-ingestion-definition", SUBSCRIPTION_DEFINITION_ID],
            settings,
        )
        assert ingest_payload["result"]["processed_files"] == 1
        assert len(ingest_payload["promotions"]) == 1
        assert ingest_payload["promotions"][0]["facts_loaded"] == 5

        report_payload = _run_worker_json(["report-subscription-summary"], settings)
        assert len(report_payload["rows"]) == 5

        client = _build_client(
            settings,
            config_repository=config_repository,
            subscription_service=SubscriptionService(
                landing_root=settings.landing_root,
                metadata_repository=RunMetadataRepository(settings.metadata_database_path),
            ),
        )
        response = client.get("/reports/subscription-summary")
        assert response.status_code == 200
        assert len(response.json()["rows"]) == 5


def test_contract_prices_local_domain_harness() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        settings = _make_settings(temp_root)
        inbox_dir = temp_root / "inbox" / "configured-contract-prices"
        processed_dir = temp_root / "processed" / "configured-contract-prices"
        failed_dir = temp_root / "failed" / "configured-contract-prices"
        inbox_dir.mkdir(parents=True)
        shutil.copyfile(
            CONTRACT_PRICE_FIXTURES / "contract_prices_valid.csv",
            inbox_dir / "contract_prices_valid.csv",
        )

        config_repository = IngestionConfigRepository(settings.resolved_config_database_path)
        create_contract_price_configuration(
            config_repository,
            include_ingestion_definitions=True,
            inbox=inbox_dir,
            processed=processed_dir,
            failed=failed_dir,
        )

        global_preflight = _run_worker_json(["verify-config"], settings)
        asset_preflight = _run_worker_json(
            ["verify-config", "--source-asset-id", CONTRACT_PRICE_ASSET_ID],
            settings,
        )
        definition_preflight = _run_worker_json(
            ["verify-config", "--ingestion-definition-id", CONTRACT_PRICE_DEFINITION_ID],
            settings,
        )

        assert global_preflight["report"]["passed"] is True
        assert global_preflight["report"]["checked"]["source_assets"] == 1
        assert global_preflight["report"]["checked"]["ingestion_definitions"] == 1
        assert asset_preflight["report"]["passed"] is True
        assert asset_preflight["report"]["scope"]["source_asset_id"] == CONTRACT_PRICE_ASSET_ID
        assert definition_preflight["report"]["passed"] is True
        assert (
            definition_preflight["report"]["scope"]["ingestion_definition_id"]
            == CONTRACT_PRICE_DEFINITION_ID
        )

        ingest_payload = _run_worker_json(
            ["process-ingestion-definition", CONTRACT_PRICE_DEFINITION_ID],
            settings,
        )
        assert ingest_payload["result"]["processed_files"] == 1
        assert len(ingest_payload["promotions"]) == 1
        assert ingest_payload["promotions"][0]["facts_loaded"] == 4

        report_payload = _run_worker_json(["report-contract-prices"], settings)
        assert len(report_payload["rows"]) == 3

        client = _build_client(
            settings,
            config_repository=config_repository,
            contract_price_service=ContractPriceService(
                landing_root=settings.landing_root,
                metadata_repository=RunMetadataRepository(settings.metadata_database_path),
            ),
        )
        response = client.get("/reports/contract-prices")
        assert response.status_code == 200
        assert len(response.json()["rows"]) == 3


def test_utility_local_domain_harness() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        settings = _make_settings(temp_root)
        usage_inbox = temp_root / "inbox" / "utility-usage"
        usage_processed = temp_root / "processed" / "utility-usage"
        usage_failed = temp_root / "failed" / "utility-usage"
        bills_inbox = temp_root / "inbox" / "utility-bills"
        bills_processed = temp_root / "processed" / "utility-bills"
        bills_failed = temp_root / "failed" / "utility-bills"
        usage_inbox.mkdir(parents=True)
        bills_inbox.mkdir(parents=True)

        shutil.copyfile(
            FIXTURES / "utility_usage_source.csv",
            usage_inbox / "utility_usage_source.csv",
        )
        shutil.copyfile(
            FIXTURES / "utility_bills_source.csv",
            bills_inbox / "utility_bills_source.csv",
        )

        config_repository = IngestionConfigRepository(settings.resolved_config_database_path)
        create_utility_configuration(
            config_repository,
            include_ingestion_definitions=True,
            usage_inbox=usage_inbox,
            usage_processed=usage_processed,
            usage_failed=usage_failed,
            bills_inbox=bills_inbox,
            bills_processed=bills_processed,
            bills_failed=bills_failed,
        )

        global_preflight = _run_worker_json(["verify-config"], settings)
        usage_asset_preflight = _run_worker_json(
            ["verify-config", "--source-asset-id", UTILITY_USAGE_ASSET_ID],
            settings,
        )
        usage_definition_preflight = _run_worker_json(
            ["verify-config", "--ingestion-definition-id", UTILITY_USAGE_DEFINITION_ID],
            settings,
        )
        bills_asset_preflight = _run_worker_json(
            ["verify-config", "--source-asset-id", UTILITY_BILLS_ASSET_ID],
            settings,
        )
        bills_definition_preflight = _run_worker_json(
            ["verify-config", "--ingestion-definition-id", UTILITY_BILLS_DEFINITION_ID],
            settings,
        )

        assert global_preflight["report"]["passed"] is True
        assert global_preflight["report"]["checked"]["source_assets"] == 2
        assert global_preflight["report"]["checked"]["ingestion_definitions"] == 2
        assert usage_asset_preflight["report"]["passed"] is True
        assert usage_asset_preflight["report"]["scope"]["source_asset_id"] == UTILITY_USAGE_ASSET_ID
        assert usage_asset_preflight["report"]["checked"]["source_assets"] == 1
        assert usage_definition_preflight["report"]["passed"] is True
        assert (
            usage_definition_preflight["report"]["scope"]["ingestion_definition_id"]
            == UTILITY_USAGE_DEFINITION_ID
        )
        assert usage_definition_preflight["report"]["checked"]["ingestion_definitions"] == 1
        assert bills_asset_preflight["report"]["passed"] is True
        assert bills_asset_preflight["report"]["scope"]["source_asset_id"] == UTILITY_BILLS_ASSET_ID
        assert bills_asset_preflight["report"]["checked"]["source_assets"] == 1
        assert bills_definition_preflight["report"]["passed"] is True
        assert (
            bills_definition_preflight["report"]["scope"]["ingestion_definition_id"]
            == UTILITY_BILLS_DEFINITION_ID
        )
        assert bills_definition_preflight["report"]["checked"]["ingestion_definitions"] == 1

        usage_payload = _run_worker_json(
            ["process-ingestion-definition", UTILITY_USAGE_DEFINITION_ID],
            settings,
        )
        bills_payload = _run_worker_json(
            ["process-ingestion-definition", UTILITY_BILLS_DEFINITION_ID],
            settings,
        )

        assert usage_payload["result"]["processed_files"] == 1
        assert bills_payload["result"]["processed_files"] == 1

        report_payload = _run_worker_json(
            ["report-utility-cost-summary", "--granularity", "month"],
            settings,
        )
        assert len(report_payload["rows"]) == 4
        assert {row["coverage_status"] for row in report_payload["rows"]} == {
            "matched",
            "usage_only",
            "bill_only",
        }

        client = _build_client(settings, config_repository=config_repository)
        response = client.get("/reports/utility-cost-summary")
        assert response.status_code == 200
        assert len(response.json()["rows"]) == 4
