from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.finance.pipelines.contract_price_service import ContractPriceService
from packages.domains.finance.pipelines.subscription_service import SubscriptionService
from packages.domains.finance.pipelines.transaction_models import DIM_ACCOUNT
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.promotion_registry import (
    PromotionHandler,
    PromotionHandlerRegistry,
    get_default_promotion_handler_registry,
)
from packages.pipelines.promotion_types import PromotionResult
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import (
    ExtensionPublication,
    LayerExtension,
    build_builtin_extension_registry,
)
from packages.shared.function_registry import FunctionRegistry, RegisteredFunction
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    SourceAssetCreate,
    SourceSystemCreate,
)
from packages.storage.run_metadata import RunMetadataRepository
from tests.external_registry_test_support import create_git_extension_repository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class _AssistantStubReportingService:
    def get_monthly_cashflow(self, from_month=None, to_month=None):
        return [
            {
                "booking_month": "2026-01",
                "income": "2500.00",
                "expense": "900.00",
                "net": "1600.00",
            }
        ]

    def get_spend_by_category_monthly(self):
        return [
            {
                "booking_month": "2026-01",
                "category": "groceries",
                "counterparty_name": "Supermarket",
                "total_expense": "84.15",
            }
        ]

    def get_upcoming_fixed_costs_30d(self):
        return [
            {
                "contract_name": "Rent",
                "expected_date": "2026-04-01",
            }
        ]


class ApiAppTests(unittest.TestCase):
    def test_create_app_rejects_legacy_auth_mode_only_bootstrap(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                ValueError,
                "identity_mode explicitly",
            ):
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    auth_mode="local",
                )

    def test_create_app_requires_configured_proxy_provider_for_proxy_mode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                ValueError,
                "configured proxy provider",
            ):
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    identity_mode="proxy",
                )

    def test_create_app_treats_local_single_user_as_cookie_auth(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                ValueError,
                "session manager",
            ):
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    identity_mode="local_single_user",
                )

    def test_health_endpoint_returns_ok(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    )
                    ,
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/health")

            self.assertEqual(200, response.status_code)
            self.assertEqual({"status": "ok"}, response.json())

    def test_openapi_docs_are_available(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/docs")

            self.assertEqual(200, response.status_code)
            self.assertIn("text/html", response.headers["content-type"])

    def test_openapi_schema_uses_typed_request_models_for_config_routes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/openapi.json")

            self.assertEqual(200, response.status_code)
            schema = response.json()
            request_body_schema = schema["paths"]["/config/source-systems"]["post"][
                "requestBody"
            ]["content"]["application/json"]["schema"]
            self.assertEqual(
                "#/components/schemas/SourceSystemRequest",
                request_body_schema["$ref"],
            )

    def test_openapi_schema_exposes_contract_routes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/openapi.json")

            self.assertEqual(200, response.status_code)
            schema = response.json()
            self.assertEqual(
                "#/components/schemas/PublicationContractsResponse",
                schema["paths"]["/contracts/publications"]["get"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/PublicationContractModel",
                schema["paths"]["/contracts/publications/{publication_key}"]["get"][
                    "responses"
                ]["200"]["content"]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/UiDescriptorsResponse",
                schema["paths"]["/contracts/ui-descriptors"]["get"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/PublicationSemanticIndexResponse",
                schema["paths"]["/contracts/publication-index"]["get"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/PublicationSemanticIndexEntryModel",
                schema["paths"]["/contracts/publication-index/{publication_key}"]["get"][
                    "responses"
                ]["200"]["content"]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/AssistantAnswerResponseModel",
                schema["paths"]["/api/assistant/answer"]["get"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )

    def test_publication_semantic_index_supports_query_and_retrieval(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            list_response = client.get("/contracts/publication-index", params={"query": "cashflow"})

            self.assertEqual(200, list_response.status_code)
            publication_index = list_response.json()["publication_index"]
            self.assertTrue(
                any(
                    entry["publication"]["publication_key"] == "monthly_cashflow"
                    for entry in publication_index
                )
            )

            detail_response = client.get("/contracts/publication-index/monthly_cashflow")

            self.assertEqual(200, detail_response.status_code)
            self.assertEqual(
                "monthly_cashflow",
                detail_response.json()["publication"]["publication_key"],
            )

    def test_assistant_answer_surface_returns_publication_backed_response(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    reporting_service=_AssistantStubReportingService(),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get(
                "/api/assistant/answer",
                params={"question": "what is our current monthly burn?"},
            )

            self.assertEqual(200, response.status_code)
            payload = response.json()
            self.assertEqual("finance", payload["resolved_domain"])
            self.assertEqual("mart_monthly_cashflow", payload["sources"][0]["publication_key"])
            self.assertIn("Latest monthly cashflow", payload["answer"])
            self.assertEqual("2026-01", payload["evidence"]["monthly_cashflow"][0]["booking_month"])

    def test_openapi_schema_exposes_typed_mutation_response_models(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/openapi.json")

            self.assertEqual(200, response.status_code)
            schema = response.json()
            self.assertEqual(
                "#/components/schemas/ServiceTokenCreateResponseModel",
                schema["paths"]["/auth/service-tokens"]["post"]["responses"]["201"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/RunMutationResponseModel",
                schema["paths"]["/runs/{run_id}/retry"]["post"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/ConfiguredIngestionProcessResponseModel",
                schema["paths"]["/ingest/ingestion-definitions/{ingestion_definition_id}/process"][
                    "post"
                ]["responses"]["201"]["content"]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/HaApprovalProposalModel",
                schema["paths"]["/api/ha/actions/proposals"]["post"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/HaApprovalProposalCreateModel",
                schema["paths"]["/api/ha/actions/proposals"]["post"]["requestBody"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )

    def test_openapi_schema_exposes_homelab_cost_benefit_scenario_route(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/openapi.json")

            self.assertEqual(200, response.status_code)
            schema = response.json()
            self.assertEqual(
                "#/components/schemas/HomelabCostBenefitRequest",
                schema["paths"]["/api/scenarios/homelab-cost-benefit"]["post"][
                    "requestBody"
                ]["content"]["application/json"]["schema"]["$ref"],
            )

    def test_openapi_schema_exposes_homelab_roi_report_route(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/openapi.json")

            self.assertEqual(200, response.status_code)
            schema = response.json()
            self.assertIn("/reports/homelab-roi", schema["paths"])

    def test_openapi_schema_exposes_scenario_compare_set_routes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/openapi.json")

            self.assertEqual(200, response.status_code)
            schema = response.json()
            self.assertEqual(
                "#/components/schemas/ScenarioCompareSetRequest",
                schema["paths"]["/api/scenarios/compare-sets"]["post"]["requestBody"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/ScenarioCompareSetUpdateRequest",
                schema["paths"]["/api/scenarios/compare-sets/{compare_set_id}"]["patch"][
                    "requestBody"
                ]["content"]["application/json"]["schema"]["$ref"],
            )
            self.assertIn(
                "/api/scenarios/compare-sets/{compare_set_id}/restore",
                schema["paths"],
            )

    def test_openapi_schema_exposes_control_terminal_models(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/openapi.json")

            self.assertEqual(200, response.status_code)
            schema = response.json()
            self.assertEqual(
                "#/components/schemas/TerminalCommandsResponseModel",
                schema["paths"]["/control/terminal/commands"]["get"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/TerminalExecutionRequest",
                schema["paths"]["/control/terminal/execute"]["post"]["requestBody"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/TerminalExecutionResponseModel",
                schema["paths"]["/control/terminal/execute"]["post"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/TerminalExecutionResponseModel",
                schema["paths"]["/control/terminal/execute"]["post"]["responses"]["400"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )

    def test_openapi_schema_exposes_typed_ha_mqtt_status_model(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/openapi.json")

            self.assertEqual(200, response.status_code)
            schema = response.json()
            self.assertEqual(
                "#/components/schemas/HaMqttStatusModel",
                schema["paths"]["/api/ha/mqtt/status"]["get"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/HaBridgeStatusModel",
                schema["paths"]["/api/ha/bridge/status"]["get"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )
            self.assertEqual(
                "#/components/schemas/HaActionsStatusModel",
                schema["paths"]["/api/ha/actions/status"]["get"]["responses"]["200"][
                    "content"
                ]["application/json"]["schema"]["$ref"],
            )

    def test_typed_config_payload_validation_rejects_invalid_dataset_contracts(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.post(
                "/config/dataset-contracts",
                json={
                    "dataset_contract_id": "bad_contract",
                    "dataset_name": "household_account_transactions",
                    "version": 1,
                    "allow_extra_columns": False,
                    "columns": [
                        {"name": "booked_at", "type": "not-a-real-type", "required": True}
                    ],
                },
            )

            self.assertEqual(422, response.status_code)

    def test_ingest_runs_and_reports_are_exposed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            transformation_service = TransformationService(
                DuckDBStore.open(str(Path(temp_dir) / "warehouse.duckdb"))
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    transformation_service=transformation_service,
                )
            )

            ingest_response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, ingest_response.status_code)

            run_id = ingest_response.json()["run"]["run_id"]

            runs_response = client.get("/runs")
            self.assertEqual(200, runs_response.status_code)
            self.assertEqual(1, len(runs_response.json()["runs"]))
            self.assertEqual(run_id, runs_response.json()["runs"][0]["run_id"])

            report_response = client.get(
                "/reports/monthly-cashflow",
            )
            self.assertEqual(200, report_response.status_code)
            self.assertEqual(
                "2365.8500",
                report_response.json()["rows"][0]["net"],
            )

    def test_contract_routes_return_publication_catalog(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            publication_response = client.get("/contracts/publications")
            self.assertEqual(200, publication_response.status_code)
            publication_payload = publication_response.json()
            publication_keys = {
                contract["publication_key"]
                for contract in publication_payload["publication_contracts"]
            }
            self.assertIn("monthly_cashflow", publication_keys)
            self.assertIn("dim_category", publication_keys)

            single_contract_response = client.get(
                "/contracts/publications/monthly_cashflow"
            )
            self.assertEqual(200, single_contract_response.status_code)
            single_contract_payload = single_contract_response.json()
            self.assertEqual("monthly_cashflow", single_contract_payload["publication_key"])
            self.assertEqual("1.0.0", single_contract_payload["schema_version"])
            self.assertEqual(
                "time",
                single_contract_payload["columns"][0]["semantic_role"],
            )
            self.assertEqual(
                "month",
                single_contract_payload["columns"][0]["grain"],
            )
            self.assertEqual(
                "sum",
                single_contract_payload["columns"][1]["aggregation"],
            )

            descriptor_response = client.get("/contracts/ui-descriptors")
            self.assertEqual(200, descriptor_response.status_code)
            self.assertGreater(len(descriptor_response.json()["ui_descriptors"]), 0)

    def test_multipart_upload_ingests_account_transactions(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            upload_response = client.post(
                "/ingest",
                data={"source_name": "manual-upload"},
                files={
                    "file": (
                        "account_transactions_valid.csv",
                        (FIXTURES / "account_transactions_valid.csv").read_bytes(),
                        "text/csv",
                    )
                },
            )

            self.assertEqual(201, upload_response.status_code)
            self.assertEqual("landed", upload_response.json()["run"]["status"])

            runs_response = client.get("/runs")
            self.assertEqual(200, runs_response.status_code)
            self.assertEqual(1, len(runs_response.json()["runs"]))

    def test_duplicate_ingest_returns_409_with_run_payload(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    )
                )
            )

            first_response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, first_response.status_code)

            duplicate_response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )

            self.assertEqual(409, duplicate_response.status_code)
            self.assertFalse(duplicate_response.json()["run"]["passed"])
            self.assertEqual("rejected", duplicate_response.json()["run"]["status"])
            self.assertIn(
                "duplicate_file",
                [issue["code"] for issue in duplicate_response.json()["run"]["issues"]],
            )

    def test_validation_failure_returns_400_with_run_payload(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    )
                )
            )

            response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_missing_column.csv"),
                    "source_name": "manual-upload",
                },
            )

            self.assertEqual(400, response.status_code)
            self.assertFalse(response.json()["run"]["passed"])
            self.assertEqual("rejected", response.json()["run"]["status"])

    def test_extensions_endpoint_returns_loaded_registry(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/extensions")

            self.assertEqual(200, response.status_code)
            self.assertIn("reporting", response.json()["extensions"])
            self.assertTrue(
                any(
                    extension["key"] == "monthly_cashflow_summary"
                    and extension["data_access"] == "published"
                    and extension["publication_relations"] == []
                    for extension in response.json()["extensions"]["reporting"]
                )
            )

    def test_functions_endpoint_returns_loaded_registry(self) -> None:
        with TemporaryDirectory() as temp_dir:
            function_registry = FunctionRegistry()
            function_registry.register(
                RegisteredFunction(
                    function_key="normalize_counterparty",
                    kind="column_mapping_value",
                    description="Normalize mapped counterparty values.",
                    module="tests.test_api_app",
                    source="test",
                    handler=lambda *, value, **_: value.upper(),
                )
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    function_registry=function_registry,
                    enable_unsafe_admin=True,
                )
            )

            response = client.get("/functions")

            self.assertEqual(200, response.status_code)
            self.assertEqual(
                "normalize_counterparty",
                response.json()["functions"]["column_mapping_value"][0]["function_key"],
            )

    def test_transformation_handler_and_publication_key_endpoints_return_loaded_options(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry = build_builtin_extension_registry()
            registry.register(
                LayerExtension(
                    layer="reporting",
                    key="budget_current_publication",
                    kind="mart",
                    description="Published current budget relation for config tests.",
                    module="tests.budget_current_publication",
                    source="tests",
                    data_access="published",
                    publication_relations=(
                        ExtensionPublication(
                            relation_name="mart_budget_current",
                            columns=(("budget_month", "VARCHAR NOT NULL"),),
                            source_query=(
                                "SELECT booking_month AS budget_month FROM mart_monthly_cashflow"
                            ),
                            order_by="budget_month",
                        ),
                    ),
                )
            )
            promotion_handler_registry = PromotionHandlerRegistry()
            for handler in get_default_promotion_handler_registry().list():
                promotion_handler_registry.register(handler)
            promotion_handler_registry.register(
                PromotionHandler(
                    handler_key="custom_budget_transform",
                    default_publications=("mart_budget_current",),
                    supported_publications=("mart_budget_current",),
                    runner=lambda runtime: PromotionResult(
                        run_id=runtime.run_id,
                        facts_loaded=0,
                        marts_refreshed=["mart_budget_current"],
                        publication_keys=["mart_budget_current"],
                    ),
                )
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    extension_registry=registry,
                    promotion_handler_registry=promotion_handler_registry,
                    enable_unsafe_admin=True,
                )
            )

            handler_response = client.get("/config/transformation-handlers")
            self.assertEqual(200, handler_response.status_code)
            self.assertTrue(
                any(
                    handler["handler_key"] == "custom_budget_transform"
                    and handler["default_publications"] == ["mart_budget_current"]
                    and handler["supported_publications"] == ["mart_budget_current"]
                    for handler in handler_response.json()["transformation_handlers"]
                )
            )

            publication_response = client.get("/config/publication-keys")
            self.assertEqual(200, publication_response.status_code)
            self.assertTrue(
                any(
                    publication["publication_key"] == "mart_budget_current"
                    and publication["supported_handlers"] == ["custom_budget_transform"]
                    and publication["reporting_extensions"]
                    == ["budget_current_publication"]
                    for publication in publication_response.json()["publication_keys"]
                )
            )

    def test_column_mapping_route_rejects_unknown_function_keys(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repository = IngestionConfigRepository(temp_root / "config.db")
            repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_partner_export",
                    name="Bank Partner Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=[
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                    ],
                )
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=repository,
                    enable_unsafe_admin=True,
                )
            )

            response = client.post(
                "/config/column-mappings",
                json={
                    "column_mapping_id": "bank_partner_export_v1",
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "version": 1,
                    "rules": [
                        {"target_column": "booked_at", "source_column": "booking_date"},
                        {
                            "target_column": "account_id",
                            "source_column": "account_number",
                            "function_key": "missing_normalizer",
                        },
                    ],
                },
            )

            self.assertEqual(400, response.status_code)
            self.assertIn("Unknown function key", response.json()["error"])

    def test_generic_transformation_and_reporting_extension_endpoints_execute(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    transformation_service=TransformationService(DuckDBStore.memory()),
                    enable_unsafe_admin=True,
                )
            )

            ingest_response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, ingest_response.status_code)
            run_id = ingest_response.json()["run"]["run_id"]

            transform_response = client.get(
                "/transformations/account_transactions_canonical",
                params={"run_id": run_id},
            )
            self.assertEqual(200, transform_response.status_code)
            self.assertEqual(
                "CHK-001",
                transform_response.json()["result"][0]["account_id"],
            )

            report_response = client.get(
                "/reports/monthly_cashflow_summary",
                params={"run_id": run_id},
            )
            self.assertEqual(200, report_response.status_code)
            self.assertEqual("2365.8500", report_response.json()["result"][0]["net"])

    def test_reporting_extension_endpoint_requires_configured_reporting_runtime(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    )
                )
            )

            response = client.get(
                "/reports/monthly_cashflow_summary",
                params={"run_id": "run-001"},
            )

            self.assertEqual(404, response.status_code)
            self.assertEqual(
                "Reporting extension requires a reporting service.",
                response.json()["detail"],
            )

    def test_custom_published_reporting_extension_endpoint_executes_from_registry(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            registry = build_builtin_extension_registry()
            registry.register(
                LayerExtension(
                    layer="reporting",
                    key="external_budget_projection",
                    kind="mart",
                    description="External published budget projection.",
                    module="tests.external_budget_projection",
                    source="tests",
                    data_access="published",
                    publication_relations=(
                        ExtensionPublication(
                            relation_name="mart_budget_projection",
                            columns=(
                                ("booking_month", "VARCHAR NOT NULL"),
                                ("net", "DECIMAL(18,4) NOT NULL"),
                            ),
                            source_query=(
                                "SELECT booking_month, net FROM mart_monthly_cashflow"
                            ),
                            order_by="booking_month",
                        ),
                    ),
                    handler=lambda *, reporting_service: reporting_service.get_relation_rows(
                        "mart_budget_projection"
                    ),
                )
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    extension_registry=registry,
                    transformation_service=TransformationService(DuckDBStore.memory()),
                )
            )

            ingest_response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, ingest_response.status_code)
            run_id = ingest_response.json()["run"]["run_id"]

            response = client.get(
                "/reports/external_budget_projection",
                params={"run_id": run_id},
            )

            self.assertEqual(200, response.status_code)
            self.assertEqual(
                [
                    {
                        "booking_month": "2026-01",
                        "net": "2365.8500",
                    }
                ],
                response.json()["result"],
            )

    def test_config_entities_and_configured_csv_ingestion_are_exposed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry = build_builtin_extension_registry()
            registry.register(
                LayerExtension(
                    layer="reporting",
                    key="budget_current_publication",
                    kind="mart",
                    description="Published current budget relation for config tests.",
                    module="tests.budget_current_publication",
                    source="tests",
                    data_access="published",
                    publication_relations=(
                        ExtensionPublication(
                            relation_name="mart_budget_current",
                            columns=(("budget_month", "VARCHAR NOT NULL"),),
                            source_query=(
                                "SELECT booking_month AS budget_month FROM mart_monthly_cashflow"
                            ),
                            order_by="budget_month",
                        ),
                    ),
                )
            )
            promotion_handler_registry = PromotionHandlerRegistry()
            for handler in get_default_promotion_handler_registry().list():
                promotion_handler_registry.register(handler)
            promotion_handler_registry.register(
                PromotionHandler(
                    handler_key="custom_budget_transform",
                    default_publications=("mart_budget_current",),
                    supported_publications=("mart_budget_current",),
                    runner=lambda runtime: PromotionResult(
                        run_id=runtime.run_id,
                        facts_loaded=0,
                        marts_refreshed=["mart_budget_current"],
                        publication_keys=["mart_budget_current"],
                    ),
                )
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    extension_registry=registry,
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    promotion_handler_registry=promotion_handler_registry,
                    enable_unsafe_admin=True,
                )
            )

            source_system_response = client.post(
                "/config/source-systems",
                json={
                    "source_system_id": "bank_partner_export",
                    "name": "Bank Partner Export",
                    "source_type": "file-drop",
                    "transport": "filesystem",
                    "schedule_mode": "manual",
                    "description": "Manual bank export",
                },
            )
            self.assertEqual(201, source_system_response.status_code)
            self.assertEqual(
                "bank_partner_export",
                source_system_response.json()["source_system"]["source_system_id"],
            )

            dataset_contract_response = client.post(
                "/config/dataset-contracts",
                json={
                    "dataset_contract_id": "household_account_transactions_v1",
                    "dataset_name": "household_account_transactions",
                    "version": 1,
                    "allow_extra_columns": False,
                    "columns": [
                        {"name": "booked_at", "type": "date", "required": True},
                        {"name": "account_id", "type": "string", "required": True},
                        {
                            "name": "counterparty_name",
                            "type": "string",
                            "required": True,
                        },
                        {"name": "amount", "type": "decimal", "required": True},
                        {"name": "currency", "type": "string", "required": True},
                        {
                            "name": "description",
                            "type": "string",
                            "required": False,
                        },
                    ],
                },
            )
            self.assertEqual(201, dataset_contract_response.status_code)
            self.assertEqual(
                "household_account_transactions_v1",
                dataset_contract_response.json()["dataset_contract"][
                    "dataset_contract_id"
                ],
            )

            column_mapping_response = client.post(
                "/config/column-mappings",
                json={
                    "column_mapping_id": "bank_partner_export_v1",
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "version": 1,
                    "rules": [
                        {
                            "target_column": "booked_at",
                            "source_column": "booking_date",
                        },
                        {
                            "target_column": "account_id",
                            "source_column": "account_number",
                        },
                        {
                            "target_column": "counterparty_name",
                            "source_column": "payee",
                        },
                        {"target_column": "amount", "source_column": "amount_eur"},
                        {"target_column": "currency", "default_value": "EUR"},
                        {"target_column": "description", "source_column": "memo"},
                    ],
                },
            )
            self.assertEqual(201, column_mapping_response.status_code)
            self.assertEqual(
                "bank_partner_export_v1",
                column_mapping_response.json()["column_mapping"]["column_mapping_id"],
            )

            source_systems_response = client.get("/config/source-systems")
            self.assertEqual(200, source_systems_response.status_code)
            self.assertEqual(1, len(source_systems_response.json()["source_systems"]))

            transformation_packages_response = client.get(
                "/config/transformation-packages"
            )
            self.assertEqual(200, transformation_packages_response.status_code)
            self.assertTrue(
                any(
                    package["transformation_package_id"]
                    == "builtin_account_transactions"
                    for package in transformation_packages_response.json()[
                        "transformation_packages"
                    ]
                )
            )

            custom_package_response = client.post(
                "/config/transformation-packages",
                json={
                    "transformation_package_id": "custom_budget_v1",
                    "name": "Custom Budget Transform",
                    "handler_key": "custom_budget_transform",
                    "version": 1,
                    "description": "Custom test transform",
                },
            )
            self.assertEqual(201, custom_package_response.status_code)
            self.assertEqual(
                "custom_budget_v1",
                custom_package_response.json()["transformation_package"][
                    "transformation_package_id"
                ],
            )

            custom_publication_response = client.post(
                "/config/publication-definitions",
                json={
                    "publication_definition_id": "custom_budget_current",
                    "transformation_package_id": "custom_budget_v1",
                    "publication_key": "mart_budget_current",
                    "name": "Current Budget Mart",
                    "description": "Custom test publication",
                },
            )
            self.assertEqual(201, custom_publication_response.status_code)
            self.assertEqual(
                "custom_budget_current",
                custom_publication_response.json()["publication_definition"][
                    "publication_definition_id"
                ],
            )

            publication_definitions_response = client.get(
                "/config/publication-definitions"
            )
            self.assertEqual(200, publication_definitions_response.status_code)
            self.assertTrue(
                any(
                    definition["publication_definition_id"] == "custom_budget_current"
                    for definition in publication_definitions_response.json()[
                        "publication_definitions"
                    ]
                )
            )

            ingest_response = client.post(
                "/ingest/configured-csv",
                json={
                    "source_path": str(
                        FIXTURES / "configured_account_transactions_source.csv"
                    ),
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "column_mapping_id": "bank_partner_export_v1",
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, ingest_response.status_code)
            self.assertEqual("landed", ingest_response.json()["run"]["status"])
            self.assertEqual(
                "household_account_transactions",
                ingest_response.json()["run"]["dataset_name"],
            )

    def test_extension_registry_source_routes_create_sync_and_activate_path_sources(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            extension_root = temp_root / "custom-extension"
            extension_root.mkdir(parents=True, exist_ok=True)
            (extension_root / "custom_extension.py").write_text(
                "\n".join(
                    [
                        "from packages.shared.extensions import LayerExtension",
                        "",
                        "def register_extensions(registry):",
                        "    registry.register(",
                        "        LayerExtension(",
                        '            layer=\"reporting\",',
                        '            key=\"custom_household_projection\",',
                        '            kind=\"mart\",',
                        '            description=\"Custom household projection.\",',
                        '            module=\"custom_extension\",',
                        '            source=\"custom-extension\",',
                        "        )",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (extension_root / "custom_functions.py").write_text(
                "def register_functions(registry):\n    return None\n",
                encoding="utf-8",
            )
            (extension_root / "homelab-analytics.registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "import_paths": ["."],
                        "extension_modules": ["custom_extension"],
                        "function_modules": ["custom_functions"],
                        "minimum_platform_version": "0.1.0",
                    }
                ),
                encoding="utf-8",
            )

            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    enable_unsafe_admin=True,
                )
            )

            create_response = client.post(
                "/config/extension-registry-sources",
                json={
                    "extension_registry_source_id": "household_custom_extension",
                    "name": "Household Custom Extension",
                    "source_kind": "path",
                    "location": str(extension_root),
                    "enabled": True,
                },
            )
            self.assertEqual(201, create_response.status_code)
            self.assertEqual(
                "household_custom_extension",
                create_response.json()["extension_registry_source"][
                    "extension_registry_source_id"
                ],
            )

            sync_response = client.post(
                "/config/extension-registry-sources/household_custom_extension/sync",
                json={"activate": True},
            )
            self.assertEqual(200, sync_response.status_code)
            self.assertEqual(
                "validated",
                sync_response.json()["extension_registry_revision"]["sync_status"],
            )
            self.assertEqual(
                "household_custom_extension",
                sync_response.json()["extension_registry_activation"][
                    "extension_registry_source_id"
                ],
            )

            revisions_response = client.get("/config/extension-registry-revisions")
            self.assertEqual(200, revisions_response.status_code)
            self.assertEqual(
                ["custom_extension"],
                revisions_response.json()["extension_registry_revisions"][0][
                    "extension_modules"
                ],
            )

            activations_response = client.get("/config/extension-registry-activations")
            self.assertEqual(200, activations_response.status_code)
            self.assertEqual(
                "household_custom_extension",
                activations_response.json()["extension_registry_activations"][0][
                    "extension_registry_source_id"
                ],
            )

    def test_extension_registry_source_routes_sync_git_sources(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            git_repository = create_git_extension_repository(
                temp_root,
                module_name="custom_git_extension",
                extension_key="git_household_projection",
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    external_registry_cache_root=temp_root / "external-registry-cache",
                    enable_unsafe_admin=True,
                )
            )

            create_response = client.post(
                "/config/extension-registry-sources",
                json={
                    "extension_registry_source_id": "household_git_extension",
                    "name": "Household Git Extension",
                    "source_kind": "git",
                    "location": str(git_repository.repo_root),
                    "desired_ref": "main",
                    "enabled": True,
                },
            )
            self.assertEqual(201, create_response.status_code)

            sync_response = client.post(
                "/config/extension-registry-sources/household_git_extension/sync",
                json={"activate": True},
            )
            self.assertEqual(200, sync_response.status_code)
            self.assertEqual(
                git_repository.commit_sha,
                sync_response.json()["extension_registry_revision"]["resolved_ref"],
            )
            self.assertEqual(
                "validated",
                sync_response.json()["extension_registry_revision"]["sync_status"],
            )

    def test_publication_definition_creation_rejects_unknown_publication_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    enable_unsafe_admin=True,
                )
            )

            response = client.post(
                "/config/publication-definitions",
                json={
                    "publication_definition_id": "invalid_budget_current",
                    "transformation_package_id": "builtin_account_transactions",
                    "publication_key": "mart_unknown_current",
                    "name": "Unknown Budget Mart",
                    "description": "Should fail validation",
                },
            )

            self.assertEqual(400, response.status_code)
            self.assertIn("Unknown publication key", response.json()["error"])
            self.assertIn("mart_unknown_current", response.json()["error"])

    def test_publication_definition_creation_rejects_unsupported_builtin_mapping(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    enable_unsafe_admin=True,
                )
            )

            response = client.post(
                "/config/publication-definitions",
                json={
                    "publication_definition_id": "invalid_builtin_mapping",
                    "transformation_package_id": "builtin_account_transactions",
                    "publication_key": "mart_contract_price_current",
                    "name": "Invalid built-in mapping",
                    "description": "Should fail validation",
                },
            )

            self.assertEqual(400, response.status_code)
            self.assertIn(
                "Publication key is not supported by the selected transformation package handler",
                response.json()["error"],
            )
            self.assertIn("builtin_account_transactions", response.json()["error"])
            self.assertIn("mart_contract_price_current", response.json()["error"])

    def test_transformation_package_creation_rejects_unknown_handler_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    enable_unsafe_admin=True,
                )
            )

            response = client.post(
                "/config/transformation-packages",
                json={
                    "transformation_package_id": "invalid_budget_v1",
                    "name": "Invalid Budget Transform",
                    "handler_key": "custom_budget_transform",
                    "version": 1,
                    "description": "Should fail validation",
                },
            )

            self.assertEqual(400, response.status_code)
            self.assertIn("Unknown transformation handler key", response.json()["error"])
            self.assertIn("custom_budget_transform", response.json()["error"])

    def test_transformation_package_and_publication_definition_routes_update_and_archive(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    enable_unsafe_admin=True,
                )
            )

            create_package_response = client.post(
                "/config/transformation-packages",
                json={
                    "transformation_package_id": "custom_budget_v1",
                    "name": "Custom Budget Transform",
                    "handler_key": "account_transactions",
                    "version": 1,
                    "description": "Custom test transform",
                },
            )
            self.assertEqual(201, create_package_response.status_code)

            create_publication_response = client.post(
                "/config/publication-definitions",
                json={
                    "publication_definition_id": "custom_budget_current",
                    "transformation_package_id": "custom_budget_v1",
                    "publication_key": "mart_monthly_cashflow",
                    "name": "Current Budget Mart",
                    "description": "Custom test publication",
                },
            )
            self.assertEqual(201, create_publication_response.status_code)

            update_package_response = client.patch(
                "/config/transformation-packages/custom_budget_v1",
                json={
                    "transformation_package_id": "custom_budget_v1",
                    "name": "Custom Budget Transform v2",
                    "handler_key": "account_transactions",
                    "version": 2,
                    "description": "Updated custom test transform",
                },
            )
            self.assertEqual(200, update_package_response.status_code)
            self.assertEqual(
                2,
                update_package_response.json()["transformation_package"]["version"],
            )
            self.assertFalse(
                update_package_response.json()["transformation_package"]["archived"]
            )

            update_publication_response = client.patch(
                "/config/publication-definitions/custom_budget_current",
                json={
                    "publication_definition_id": "custom_budget_current",
                    "transformation_package_id": "custom_budget_v1",
                    "publication_key": "mart_monthly_cashflow",
                    "name": "Current Budget Mart v2",
                    "description": "Updated custom test publication",
                },
            )
            self.assertEqual(200, update_publication_response.status_code)
            self.assertEqual(
                "Current Budget Mart v2",
                update_publication_response.json()["publication_definition"]["name"],
            )

            blocked_archive_response = client.patch(
                "/config/transformation-packages/custom_budget_v1/archive",
                json={"archived": True},
            )
            self.assertEqual(400, blocked_archive_response.status_code)
            self.assertIn("publication definitions", blocked_archive_response.json()["error"])

            archive_publication_response = client.patch(
                "/config/publication-definitions/custom_budget_current/archive",
                json={"archived": True},
            )
            self.assertEqual(200, archive_publication_response.status_code)
            self.assertTrue(
                archive_publication_response.json()["publication_definition"]["archived"]
            )

            active_publications_response = client.get("/config/publication-definitions")
            self.assertEqual(200, active_publications_response.status_code)
            self.assertFalse(
                any(
                    definition["publication_definition_id"] == "custom_budget_current"
                    for definition in active_publications_response.json()[
                        "publication_definitions"
                    ]
                )
            )
            archived_publications_response = client.get(
                "/config/publication-definitions?include_archived=true"
            )
            self.assertEqual(200, archived_publications_response.status_code)
            archived_publication = next(
                definition
                for definition in archived_publications_response.json()[
                    "publication_definitions"
                ]
                if definition["publication_definition_id"] == "custom_budget_current"
            )
            self.assertTrue(archived_publication["archived"])

            archive_package_response = client.patch(
                "/config/transformation-packages/custom_budget_v1/archive",
                json={"archived": True},
            )
            self.assertEqual(200, archive_package_response.status_code)
            self.assertTrue(
                archive_package_response.json()["transformation_package"]["archived"]
            )

            active_packages_response = client.get("/config/transformation-packages")
            self.assertEqual(200, active_packages_response.status_code)
            self.assertFalse(
                any(
                    package["transformation_package_id"] == "custom_budget_v1"
                    for package in active_packages_response.json()[
                        "transformation_packages"
                    ]
                )
            )
            archived_packages_response = client.get(
                "/config/transformation-packages?include_archived=true"
            )
            self.assertEqual(200, archived_packages_response.status_code)
            archived_package = next(
                package
                for package in archived_packages_response.json()["transformation_packages"]
                if package["transformation_package_id"] == "custom_budget_v1"
            )
            self.assertTrue(archived_package["archived"])

            blocked_publication_restore_response = client.patch(
                "/config/publication-definitions/custom_budget_current/archive",
                json={"archived": False},
            )
            self.assertEqual(400, blocked_publication_restore_response.status_code)
            self.assertIn(
                "Transformation package is archived",
                blocked_publication_restore_response.json()["error"],
            )

            restore_package_response = client.patch(
                "/config/transformation-packages/custom_budget_v1/archive",
                json={"archived": False},
            )
            self.assertEqual(200, restore_package_response.status_code)
            self.assertFalse(
                restore_package_response.json()["transformation_package"]["archived"]
            )

            restore_publication_response = client.patch(
                "/config/publication-definitions/custom_budget_current/archive",
                json={"archived": False},
            )
            self.assertEqual(200, restore_publication_response.status_code)
            self.assertFalse(
                restore_publication_response.json()["publication_definition"]["archived"]
            )

    def test_source_assets_and_ingestion_definitions_are_exposed_and_executable(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            inbox_dir = temp_root / "configured-inbox"
            processed_dir = temp_root / "configured-processed"
            failed_dir = temp_root / "configured-failed"
            inbox_dir.mkdir()
            (inbox_dir / "valid.csv").write_text(
                (FIXTURES / "configured_account_transactions_source.csv").read_text()
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    enable_unsafe_admin=True,
                )
            )

            client.post(
                "/config/source-systems",
                json={
                    "source_system_id": "bank_partner_export",
                    "name": "Bank Partner Export",
                    "source_type": "file-drop",
                    "transport": "filesystem",
                    "schedule_mode": "manual",
                },
            )
            client.post(
                "/config/dataset-contracts",
                json={
                    "dataset_contract_id": "household_account_transactions_v1",
                    "dataset_name": "household_account_transactions",
                    "version": 1,
                    "allow_extra_columns": False,
                    "columns": [
                        {"name": "booked_at", "type": "date", "required": True},
                        {"name": "account_id", "type": "string", "required": True},
                        {
                            "name": "counterparty_name",
                            "type": "string",
                            "required": True,
                        },
                        {"name": "amount", "type": "decimal", "required": True},
                        {"name": "currency", "type": "string", "required": True},
                        {
                            "name": "description",
                            "type": "string",
                            "required": False,
                        },
                    ],
                },
            )
            client.post(
                "/config/column-mappings",
                json={
                    "column_mapping_id": "bank_partner_export_v1",
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "version": 1,
                    "rules": [
                        {
                            "target_column": "booked_at",
                            "source_column": "booking_date",
                        },
                        {
                            "target_column": "account_id",
                            "source_column": "account_number",
                        },
                        {
                            "target_column": "counterparty_name",
                            "source_column": "payee",
                        },
                        {"target_column": "amount", "source_column": "amount_eur"},
                        {"target_column": "currency", "default_value": "EUR"},
                        {"target_column": "description", "source_column": "memo"},
                    ],
                },
            )

            source_asset_response = client.post(
                "/config/source-assets",
                json={
                    "source_asset_id": "bank_partner_transactions",
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "column_mapping_id": "bank_partner_export_v1",
                    "name": "Bank Partner Transactions",
                    "asset_type": "dataset",
                    "transformation_package_id": "builtin_account_transactions",
                },
            )
            self.assertEqual(201, source_asset_response.status_code)
            self.assertEqual(
                "bank_partner_transactions",
                source_asset_response.json()["source_asset"]["source_asset_id"],
            )

            definition_response = client.post(
                "/config/ingestion-definitions",
                json={
                    "ingestion_definition_id": "bank_partner_watch_folder",
                    "source_asset_id": "bank_partner_transactions",
                    "transport": "filesystem",
                    "schedule_mode": "watch-folder",
                    "source_path": str(inbox_dir),
                    "file_pattern": "*.csv",
                    "processed_path": str(processed_dir),
                    "failed_path": str(failed_dir),
                    "poll_interval_seconds": 30,
                    "enabled": True,
                    "source_name": "folder-watch",
                },
            )
            self.assertEqual(201, definition_response.status_code)
            self.assertEqual(
                "bank_partner_watch_folder",
                definition_response.json()["ingestion_definition"][
                    "ingestion_definition_id"
                ],
            )

            source_assets_response = client.get("/config/source-assets")
            self.assertEqual(200, source_assets_response.status_code)
            self.assertEqual(1, len(source_assets_response.json()["source_assets"]))

            sources_response = client.get("/sources")
            self.assertEqual(200, sources_response.status_code)
            self.assertEqual(1, len(sources_response.json()["source_systems"]))
            self.assertEqual(1, len(sources_response.json()["source_assets"]))

            process_response = client.post(
                "/ingest/ingestion-definitions/bank_partner_watch_folder/process"
            )
            self.assertEqual(201, process_response.status_code)
            self.assertEqual(1, process_response.json()["result"]["processed_files"])
            self.assertEqual(0, process_response.json()["result"]["rejected_files"])

    def test_http_ingestion_definition_can_be_created_and_processed(self) -> None:
        from tests.test_configured_ingestion_definition import run_csv_server

        with TemporaryDirectory() as temp_dir, run_csv_server(
            response_body=(
                FIXTURES / "configured_account_transactions_source.csv"
            ).read_bytes()
        ) as server:
            temp_root = Path(temp_dir)
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    enable_unsafe_admin=True,
                )
            )

            client.post(
                "/config/source-systems",
                json={
                    "source_system_id": "utility_api",
                    "name": "Utility API",
                    "source_type": "api",
                    "transport": "http",
                    "schedule_mode": "scheduled",
                },
            )
            client.post(
                "/config/dataset-contracts",
                json={
                    "dataset_contract_id": "household_account_transactions_v1",
                    "dataset_name": "household_account_transactions",
                    "version": 1,
                    "allow_extra_columns": False,
                    "columns": [
                        {"name": "booked_at", "type": "date", "required": True},
                        {"name": "account_id", "type": "string", "required": True},
                        {
                            "name": "counterparty_name",
                            "type": "string",
                            "required": True,
                        },
                        {"name": "amount", "type": "decimal", "required": True},
                        {"name": "currency", "type": "string", "required": True},
                        {
                            "name": "description",
                            "type": "string",
                            "required": False,
                        },
                    ],
                },
            )
            client.post(
                "/config/column-mappings",
                json={
                    "column_mapping_id": "utility_api_v1",
                    "source_system_id": "utility_api",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "version": 1,
                    "rules": [
                        {
                            "target_column": "booked_at",
                            "source_column": "booking_date",
                        },
                        {
                            "target_column": "account_id",
                            "source_column": "account_number",
                        },
                        {
                            "target_column": "counterparty_name",
                            "source_column": "payee",
                        },
                        {"target_column": "amount", "source_column": "amount_eur"},
                        {"target_column": "currency", "default_value": "EUR"},
                        {"target_column": "description", "source_column": "memo"},
                    ],
                },
            )
            client.post(
                "/config/source-assets",
                json={
                    "source_asset_id": "utility_api_asset",
                    "source_system_id": "utility_api",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "column_mapping_id": "utility_api_v1",
                    "name": "Utility API Asset",
                    "asset_type": "dataset",
                    "transformation_package_id": "builtin_account_transactions",
                },
            )

            definition_response = client.post(
                "/config/ingestion-definitions",
                json={
                    "ingestion_definition_id": "utility_api_pull",
                    "source_asset_id": "utility_api_asset",
                    "transport": "http",
                    "schedule_mode": "direct-api",
                    "source_path": "",
                    "request_url": (
                        f"http://127.0.0.1:{server.server_address[1]}/api.csv"
                    ),
                    "request_method": "GET",
                    "response_format": "csv",
                    "output_file_name": "api.csv",
                    "enabled": True,
                    "source_name": "scheduled-api-pull",
                },
            )
            self.assertEqual(201, definition_response.status_code)
            self.assertEqual(
                "utility_api_pull",
                definition_response.json()["ingestion_definition"][
                    "ingestion_definition_id"
                ],
            )

            process_response = client.post(
                "/ingest/ingestion-definitions/utility_api_pull/process"
            )
            self.assertEqual(201, process_response.status_code)
            self.assertEqual(1, process_response.json()["result"]["processed_files"])
            self.assertEqual(0, process_response.json()["result"]["rejected_files"])

    def test_current_dimension_reports_are_exposed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            account_service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            transformation_service = TransformationService(DuckDBStore.memory())
            transformation_service.store.upsert_dimension_rows(
                DIM_ACCOUNT,
                [{"account_id": "CHK-001", "currency": "EUR"}],
                effective_date=date(2025, 1, 1),
            )
            transformation_service.store.upsert_dimension_rows(
                DIM_ACCOUNT,
                [{"account_id": "CHK-001", "currency": "USD"}],
                effective_date=date(2025, 2, 1),
            )
            transformation_service.load_home_automation_state(
                [
                    {
                        "entity_id": "sensor.living_room_temperature",
                        "state": "21.3",
                        "attributes": {
                            "friendly_name": "Living Room Temperature",
                            "unit_of_measurement": "°C",
                            "area_id": "living-room",
                            "integration": "home_assistant",
                        },
                        "last_changed": "2026-03-28T10:00:00+00:00",
                    }
                ],
                run_id="run-002",
                source_system="home_assistant",
            )

            client = TestClient(
                create_app(
                    account_service,
                    transformation_service=transformation_service,
                )
            )

            response = client.get("/reports/current-dimensions/dim_account")

            self.assertEqual(200, response.status_code)
            body = response.json()
            self.assertEqual("dim_account", body["dimension"])
            self.assertEqual(1, len(body["rows"]))
            self.assertEqual("CHK-001", body["rows"][0]["account_id"])
            self.assertEqual("USD", body["rows"][0]["currency"])

            entity_response = client.get("/reports/current-dimensions/dim_entity")
            self.assertEqual(200, entity_response.status_code)
            entity_body = entity_response.json()
            self.assertEqual("dim_entity", entity_body["dimension"])
            self.assertEqual(1, len(entity_body["rows"]))
            self.assertEqual(
                "sensor.living_room_temperature",
                entity_body["rows"][0]["entity_id"],
            )
            self.assertEqual(
                "Living Room Temperature",
                entity_body["rows"][0]["entity_name"],
            )

            transformation_service.load_domain_rows(
                "asset_register",
                [
                    {
                        "asset_name": "UPS Rack A",
                        "asset_type": "ups",
                        "purchase_date": "2024-01-15",
                        "purchase_price": "1200.00",
                        "currency": "EUR",
                        "location": "rack-a",
                    }
                ],
                run_id="run-003",
                source_system="manual-upload",
            )

            asset_response = client.get("/reports/current-dimensions/dim_asset")
            self.assertEqual(200, asset_response.status_code)
            asset_body = asset_response.json()
            self.assertEqual("dim_asset", asset_body["dimension"])
            self.assertEqual(1, len(asset_body["rows"]))
            self.assertEqual("UPS Rack A", asset_body["rows"][0]["asset_name"])
            self.assertEqual("rack-a", asset_body["rows"][0]["location"])


    def test_runs_endpoint_exposes_pagination_envelope_and_supports_filtering(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            metadata_repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=metadata_repository,
                    )
                )
            )

            # Ingest a valid file to create one LANDED run.
            ingest_response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, ingest_response.status_code)

            # GET /runs should include pagination metadata.
            runs_response = client.get("/runs")
            self.assertEqual(200, runs_response.status_code)
            body = runs_response.json()
            self.assertIn("pagination", body)
            self.assertEqual(1, body["pagination"]["total"])
            self.assertEqual(50, body["pagination"]["limit"])
            self.assertEqual(0, body["pagination"]["offset"])
            self.assertEqual(1, len(body["runs"]))

            # Filtering by status=landed should return the run.
            landed_response = client.get("/runs", params={"status": "landed"})
            self.assertEqual(200, landed_response.status_code)
            self.assertEqual(1, landed_response.json()["pagination"]["total"])

            # Filtering by status=rejected should return nothing.
            rejected_response = client.get("/runs", params={"status": "rejected"})
            self.assertEqual(200, rejected_response.status_code)
            self.assertEqual(0, rejected_response.json()["pagination"]["total"])
            self.assertEqual([], rejected_response.json()["runs"])

            # Invalid status should return 400.
            bad_response = client.get("/runs", params={"status": "nonsense"})
            self.assertEqual(400, bad_response.status_code)

            # Pagination: limit=1 should return at most 1 run with correct total.
            page_response = client.get("/runs", params={"limit": 1, "offset": 0})
            self.assertEqual(200, page_response.status_code)
            self.assertEqual(1, len(page_response.json()["runs"]))
            self.assertEqual(1, page_response.json()["pagination"]["total"])


    def test_monthly_cashflow_mart_endpoint_with_date_range_filters(self) -> None:
        with TemporaryDirectory() as temp_dir:
            transformation_service = TransformationService(DuckDBStore.memory())
            transformation_service.load_transactions(
                [
                    {
                        "booked_at": "2026-01-02",
                        "account_id": "CHK-001",
                        "counterparty_name": "Employer",
                        "amount": "2450.00",
                        "currency": "EUR",
                        "description": "Salary",
                    },
                    {
                        "booked_at": "2026-02-02",
                        "account_id": "CHK-001",
                        "counterparty_name": "Employer",
                        "amount": "2450.00",
                        "currency": "EUR",
                        "description": "Salary",
                    },
                ]
            )
            transformation_service.refresh_monthly_cashflow()

            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    transformation_service=transformation_service,
                )
            )

            # No filters — returns both months via mart path.
            resp = client.get("/reports/monthly-cashflow")
            self.assertEqual(200, resp.status_code)
            body = resp.json()
            self.assertIn("rows", body)
            self.assertEqual(2, len(body["rows"]))
            self.assertIsNone(body["from_month"])
            self.assertIsNone(body["to_month"])

            # from_month filter
            resp_feb = client.get("/reports/monthly-cashflow", params={"from_month": "2026-02"})
            self.assertEqual(200, resp_feb.status_code)
            feb_body = resp_feb.json()
            self.assertEqual(1, len(feb_body["rows"]))
            self.assertEqual("2026-02", feb_body["rows"][0]["booking_month"])
            self.assertEqual("2026-02", feb_body["from_month"])

            # to_month filter
            resp_jan = client.get("/reports/monthly-cashflow", params={"to_month": "2026-01"})
            self.assertEqual(200, resp_jan.status_code)
            self.assertEqual(1, len(resp_jan.json()["rows"]))

            bare_client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing2",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs2.db"
                        ),
                    )
                )
            )
            self.assertEqual(404, bare_client.get("/reports/monthly-cashflow").status_code)


    def test_counterparty_cashflow_and_transformation_audit_endpoints(self) -> None:
        with TemporaryDirectory() as temp_dir:
            transformation_service = TransformationService(DuckDBStore.memory())
            transformation_service.load_transactions(
                [
                    {
                        "booked_at": "2026-01-02",
                        "account_id": "CHK-001",
                        "counterparty_name": "Employer",
                        "amount": "2450.00",
                        "currency": "EUR",
                        "description": "Salary",
                    },
                    {
                        "booked_at": "2026-01-03",
                        "account_id": "CHK-001",
                        "counterparty_name": "Electric Utility",
                        "amount": "-84.15",
                        "currency": "EUR",
                        "description": "Bill",
                    },
                ],
                run_id="run-001",
            )
            transformation_service.refresh_monthly_cashflow_by_counterparty()

            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    transformation_service=transformation_service,
                )
            )

            # Counterparty breakdown endpoint
            resp = client.get("/reports/monthly-cashflow-by-counterparty")
            self.assertEqual(200, resp.status_code)
            body = resp.json()
            self.assertIn("rows", body)
            self.assertEqual(2, len(body["rows"]))
            counterparties = {r["counterparty_name"] for r in body["rows"]}
            self.assertEqual({"Employer", "Electric Utility"}, counterparties)

            # Filter by counterparty name
            resp_emp = client.get(
                "/reports/monthly-cashflow-by-counterparty",
                params={"counterparty": "Employer"},
            )
            self.assertEqual(200, resp_emp.status_code)
            self.assertEqual(1, len(resp_emp.json()["rows"]))
            self.assertEqual("Employer", resp_emp.json()["rows"][0]["counterparty_name"])

            # Transformation audit endpoint
            audit_resp = client.get("/transformation-audit")
            self.assertEqual(200, audit_resp.status_code)
            audit_body = audit_resp.json()
            self.assertIn("rows", audit_body)
            self.assertNotIn("audit", audit_body)
            self.assertEqual(1, len(audit_body["rows"]))
            self.assertEqual("run-001", audit_body["rows"][0]["input_run_id"])
            self.assertEqual(2, audit_body["rows"][0]["fact_rows"])

            # Filter audit by run_id
            audit_filtered = client.get("/transformation-audit", params={"run_id": "run-001"})
            self.assertEqual(200, audit_filtered.status_code)
            self.assertNotIn("audit", audit_filtered.json())
            self.assertEqual(1, len(audit_filtered.json()["rows"]))

            # Without transformation_service wired in, endpoints return 404
            bare_client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing2",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs2.db"
                        ),
                    )
                )
            )
            self.assertEqual(
                404,
                bare_client.get("/reports/monthly-cashflow-by-counterparty").status_code,
            )
            self.assertEqual(404, bare_client.get("/transformation-audit").status_code)

    def test_ingest_with_transformation_service_returns_promotion_in_response(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            store = DuckDBStore.open(str(Path(temp_dir) / "warehouse.duckdb"))
            transformation_service = TransformationService(store)
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    transformation_service=transformation_service,
                )
            )

            response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "promotion-test",
                },
            )

            self.assertEqual(201, response.status_code)
            body = response.json()
            self.assertIn("promotion", body)
            promo = body["promotion"]
            self.assertFalse(promo["skipped"])
            self.assertIsNone(promo["skip_reason"])
            self.assertGreater(promo["facts_loaded"], 0)
            self.assertIn("mart_monthly_cashflow", promo["marts_refreshed"])
            self.assertIn(
                "mart_monthly_cashflow_by_counterparty", promo["marts_refreshed"]
            )

    def test_ingest_without_transformation_service_has_no_promotion_in_response(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    )
                )
            )

            response = client.post(
                "/ingest",
                json={
                    "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "no-promo-test",
                },
            )

            self.assertEqual(201, response.status_code)
            self.assertNotIn("promotion", response.json())

    def test_configured_csv_ingest_with_transformation_service_returns_promotion(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            transformation_service = TransformationService(DuckDBStore.memory())
            config_repository = IngestionConfigRepository(temp_root / "config.db")
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_partner_export",
                    name="Bank Partner Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            config_repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=[
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                        DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
                        DatasetColumnConfig("description", ColumnType.STRING, required=False),
                    ],
                )
            )
            config_repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_partner_export_v1",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    version=1,
                    rules=[
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("currency", default_value="EUR"),
                        ColumnMappingRule("description", source_column="memo"),
                    ],
                )
            )
            config_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="bank_partner_transactions",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="bank_partner_export_v1",
                    name="Bank Partner Transactions",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                )
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=config_repository,
                    transformation_service=transformation_service,
                )
            )

            response = client.post(
                "/ingest/configured-csv",
                json={
                    "source_path": str(FIXTURES / "configured_account_transactions_source.csv"),
                    "source_asset_id": "bank_partner_transactions",
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "column_mapping_id": "bank_partner_export_v1",
                    "source_name": "manual-upload",
                },
            )

            self.assertEqual(201, response.status_code)
            body = response.json()
            self.assertIn("promotion", body)
            self.assertFalse(body["promotion"]["skipped"])
            self.assertGreater(body["promotion"]["facts_loaded"], 0)

    def test_process_ingestion_definition_with_transformation_service_returns_promotions(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            inbox_dir = temp_root / "configured-inbox"
            processed_dir = temp_root / "configured-processed"
            failed_dir = temp_root / "configured-failed"
            inbox_dir.mkdir()
            (inbox_dir / "valid.csv").write_text(
                (FIXTURES / "configured_account_transactions_source.csv").read_text()
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=temp_root / "landing",
                        metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
                    ),
                    config_repository=IngestionConfigRepository(temp_root / "config.db"),
                    transformation_service=TransformationService(DuckDBStore.memory()),
                    enable_unsafe_admin=True,
                )
            )

            client.post(
                "/config/source-systems",
                json={
                    "source_system_id": "bank_partner_export",
                    "name": "Bank Partner Export",
                    "source_type": "file-drop",
                    "transport": "filesystem",
                    "schedule_mode": "manual",
                },
            )
            client.post(
                "/config/dataset-contracts",
                json={
                    "dataset_contract_id": "household_account_transactions_v1",
                    "dataset_name": "household_account_transactions",
                    "version": 1,
                    "allow_extra_columns": False,
                    "columns": [
                        {"name": "booked_at", "type": "date", "required": True},
                        {"name": "account_id", "type": "string", "required": True},
                        {"name": "counterparty_name", "type": "string", "required": True},
                        {"name": "amount", "type": "decimal", "required": True},
                        {"name": "currency", "type": "string", "required": True},
                        {"name": "description", "type": "string", "required": False},
                    ],
                },
            )
            client.post(
                "/config/column-mappings",
                json={
                    "column_mapping_id": "bank_partner_export_v1",
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "version": 1,
                    "rules": [
                        {"target_column": "booked_at", "source_column": "booking_date"},
                        {"target_column": "account_id", "source_column": "account_number"},
                        {"target_column": "counterparty_name", "source_column": "payee"},
                        {"target_column": "amount", "source_column": "amount_eur"},
                        {"target_column": "currency", "default_value": "EUR"},
                        {"target_column": "description", "source_column": "memo"},
                    ],
                },
            )
            client.post(
                "/config/source-assets",
                json={
                    "source_asset_id": "bank_partner_transactions",
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "column_mapping_id": "bank_partner_export_v1",
                    "name": "Bank Partner Transactions",
                    "asset_type": "dataset",
                    "transformation_package_id": "builtin_account_transactions",
                },
            )
            client.post(
                "/config/ingestion-definitions",
                json={
                    "ingestion_definition_id": "bank_partner_watch_folder",
                    "source_asset_id": "bank_partner_transactions",
                    "transport": "filesystem",
                    "schedule_mode": "watch-folder",
                    "source_path": str(inbox_dir),
                    "file_pattern": "*.csv",
                    "processed_path": str(processed_dir),
                    "failed_path": str(failed_dir),
                    "poll_interval_seconds": 30,
                    "enabled": True,
                    "source_name": "folder-watch",
                },
            )

            response = client.post(
                "/ingest/ingestion-definitions/bank_partner_watch_folder/process"
            )

            self.assertEqual(201, response.status_code)
            body = response.json()
            self.assertEqual(1, body["result"]["processed_files"])
            self.assertEqual(1, len(body["promotions"]))
            self.assertFalse(body["promotions"][0]["skipped"])

    def test_subscription_ingest_and_summary_endpoints(self) -> None:
        with TemporaryDirectory() as temp_dir:
            landing = Path(temp_dir) / "landing"
            store = DuckDBStore.open(str(Path(temp_dir) / "warehouse.duckdb"))
            transformation_service = TransformationService(store)
            subscription_service = SubscriptionService(
                landing_root=landing,
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=landing,
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    transformation_service=transformation_service,
                    subscription_service=subscription_service,
                )
            )

            # Ingest subscriptions
            ingest_response = client.post(
                "/ingest/subscriptions",
                json={
                    "source_path": str(FIXTURES / "subscriptions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, ingest_response.status_code)
            body = ingest_response.json()
            self.assertEqual("landed", body["run"]["status"])
            self.assertIn("promotion", body)
            promo = body["promotion"]
            self.assertFalse(promo["skipped"])
            self.assertEqual(5, promo["facts_loaded"])
            self.assertIn("mart_subscription_summary", promo["marts_refreshed"])
            self.assertIn("mart_upcoming_fixed_costs_30d", promo["marts_refreshed"])

            # Query subscription summary mart
            summary_response = client.get("/reports/subscription-summary")
            self.assertEqual(200, summary_response.status_code)
            summary_body = summary_response.json()
            self.assertIn("rows", summary_body)
            self.assertEqual(5, len(summary_body["rows"]))

            # Filter by status=active
            active_response = client.get(
                "/reports/subscription-summary", params={"status": "active"}
            )
            self.assertEqual(200, active_response.status_code)
            active_rows = active_response.json()["rows"]
            self.assertTrue(all(r["status"] == "active" for r in active_rows))

    def test_subscription_ingest_without_subscription_service_returns_404(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=Path(temp_dir) / "landing",
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    )
                )
            )
            response = client.post(
                "/ingest/subscriptions",
                json={
                    "source_path": str(FIXTURES / "subscriptions_valid.csv"),
                },
            )
            self.assertEqual(404, response.status_code)

    def test_contract_price_ingest_and_reporting_endpoints(self) -> None:
        with TemporaryDirectory() as temp_dir:
            landing = Path(temp_dir) / "landing"
            store = DuckDBStore.open(str(Path(temp_dir) / "warehouse.duckdb"))
            transformation_service = TransformationService(store)
            contract_price_service = ContractPriceService(
                landing_root=landing,
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            client = TestClient(
                create_app(
                    AccountTransactionService(
                        landing_root=landing,
                        metadata_repository=RunMetadataRepository(
                            Path(temp_dir) / "runs.db"
                        ),
                    ),
                    transformation_service=transformation_service,
                    contract_price_service=contract_price_service,
                )
            )

            ingest_response = client.post(
                "/ingest/contract-prices",
                json={
                    "source_path": str(FIXTURES / "contract_prices_valid.csv"),
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, ingest_response.status_code)
            body = ingest_response.json()
            self.assertEqual("landed", body["run"]["status"])
            self.assertIn("promotion", body)
            self.assertEqual(4, body["promotion"]["facts_loaded"])
            self.assertIn("mart_contract_price_current", body["promotion"]["marts_refreshed"])

            contract_price_response = client.get("/reports/contract-prices")
            self.assertEqual(200, contract_price_response.status_code)
            self.assertEqual(3, len(contract_price_response.json()["rows"]))

            electricity_response = client.get("/reports/electricity-prices")
            self.assertEqual(200, electricity_response.status_code)
            electricity_rows = electricity_response.json()["rows"]
            self.assertEqual(2, len(electricity_rows))
            self.assertTrue(
                all(row["contract_type"] == "electricity" for row in electricity_rows)
            )


if __name__ == "__main__":
    unittest.main()
