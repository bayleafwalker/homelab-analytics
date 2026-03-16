import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.extension_registries import load_pipeline_registries
from packages.pipelines.promotion_registry import PromotionRuntime
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import (
    ExtensionPublication,
    ExtensionRegistry,
    LayerExtension,
    load_extension_registry,
)
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class ExtensionRegistryTests(unittest.TestCase):
    def test_builtin_registry_covers_all_layers(self) -> None:
        registry = load_extension_registry()

        self.assertTrue(
            any(
                extension.key == "account_transactions_canonical"
                for extension in registry.list_extensions("transformation")
            )
        )
        self.assertTrue(
            any(
                extension.key == "monthly_cashflow_summary"
                for extension in registry.list_extensions("reporting")
            )
        )
        self.assertTrue(
            any(
                extension.key == "cashflow_dashboard"
                for extension in registry.list_extensions("application")
            )
        )

    def test_external_modules_can_register_extensions_from_custom_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            module_name = f"test_external_extension_{uuid4().hex}"
            module_path = Path(temp_dir) / f"{module_name}.py"
            module_path.write_text(
                "\n".join(
                    [
                        "from packages.shared.extensions import LayerExtension",
                        "",
                        "def register_extensions(registry):",
                        "    registry.register(",
                        "        LayerExtension(",
                        '            layer="reporting",',
                        '            key="external_budget_projection",',
                        '            kind="mart",',
                        '            description="External household budget projection mart.",',
                        f'            module="{module_name}",',
                        f'            source="{module_name}",',
                        "        )",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            registry = load_extension_registry(
                extension_paths=(Path(temp_dir),),
                extension_modules=(module_name,),
            )

            self.assertTrue(
                any(
                    extension.key == "external_budget_projection"
                    for extension in registry.list_extensions("reporting")
                )
            )
            self.assertIn(str(Path(temp_dir)), sys.path)
            sys.modules.pop(module_name, None)

    def test_external_modules_can_register_pipeline_registries_from_custom_paths(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            module_name = f"test_external_pipeline_{uuid4().hex}"
            module_path = Path(temp_dir) / f"{module_name}.py"
            module_path.write_text(
                "\n".join(
                    [
                        "from packages.pipelines.promotion_registry import PromotionHandler",
                        "from packages.pipelines.promotion_types import PromotionResult",
                        "",
                        "def register_pipeline_registries(*, promotion_handler_registry, publication_refresh_registry):",
                        "    publication_refresh_registry.register(",
                        '        "mart_budget_projection",',
                        "        lambda service: 0,",
                        "    )",
                        "    promotion_handler_registry.register(",
                        "        PromotionHandler(",
                        '            handler_key="custom_budget_transform",',
                        '            default_publications=("mart_budget_projection",),',
                        '            supported_publications=("mart_budget_projection",),',
                        "            runner=lambda runtime: PromotionResult(",
                        "                run_id=runtime.run_id,",
                        "                facts_loaded=0,",
                        "                marts_refreshed=runtime.transformation_service.refresh_publications([",
                        '                    "mart_budget_projection",',
                        "                ]),",
                        '                publication_keys=["mart_budget_projection"],',
                        "            ),",
                        "        )",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            registries = load_pipeline_registries(
                extension_paths=(Path(temp_dir),),
                extension_modules=(module_name,),
            )
            transformation_service = TransformationService(
                DuckDBStore.memory(),
                publication_refresh_registry=registries.publication_refresh_registry,
            )
            result = registries.promotion_handler_registry.get("custom_budget_transform").runner(
                PromotionRuntime(
                    run_id="run-123",
                    landing_root=Path(temp_dir),
                    metadata_repository=object(),  # type: ignore[arg-type]
                    config_repository=object(),  # type: ignore[arg-type]
                    transformation_service=transformation_service,
                )
            )

            self.assertEqual(["mart_budget_projection"], result.marts_refreshed)
            self.assertEqual(["mart_budget_projection"], result.publication_keys)
            sys.modules.pop(module_name, None)

    def test_builtin_transformation_and_reporting_extensions_execute(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            run = service.ingest_file(FIXTURES / "account_transactions_valid.csv")
            transformation_service = TransformationService(DuckDBStore.memory())
            transformation_service.load_transactions(
                [
                    {
                        "booked_at": str(transaction.booked_at),
                        "account_id": transaction.account_id,
                        "counterparty_name": transaction.counterparty_name,
                        "amount": str(transaction.amount),
                        "currency": transaction.currency,
                        "description": transaction.description or "",
                    }
                    for transaction in service.get_canonical_transactions(run.run_id)
                ],
                run_id=run.run_id,
            )
            transformation_service.refresh_monthly_cashflow()
            registry = load_extension_registry()

            transactions = registry.execute(
                "transformation",
                "account_transactions_canonical",
                service=service,
                run_id=run.run_id,
            )
            summaries = registry.execute(
                "reporting",
                "monthly_cashflow_summary",
                reporting_service=ReportingService(transformation_service),
            )

            self.assertEqual(2, len(transactions))
            self.assertEqual("CHK-001", transactions[0].account_id)
            self.assertEqual("2365.8500", str(summaries[0]["net"]))

    def test_builtin_reporting_extension_prefers_reporting_service(self) -> None:
        class ReportingServiceStub:
            def get_monthly_cashflow(self):
                return [{"booking_month": "2026-01", "net": "1600.0000"}]

        registry = load_extension_registry()

        result = registry.execute(
            "reporting",
            "monthly_cashflow_summary",
            reporting_service=ReportingServiceStub(),
            run_id="ignored-run-id",
        )

        self.assertEqual(
            [{"booking_month": "2026-01", "net": "1600.0000"}],
            result,
        )

    def test_external_reporting_extension_can_execute(self) -> None:
        with TemporaryDirectory() as temp_dir:
            module_name = f"test_external_runtime_{uuid4().hex}"
            module_path = Path(temp_dir) / f"{module_name}.py"
            module_path.write_text(
                "\n".join(
                    [
                        "from packages.shared.extensions import LayerExtension",
                        "",
                        "def run_projection(*, transformation_service, run_id):",
                        "    return {'run_id': run_id, 'status': 'projected'}",
                        "",
                        "def register_extensions(registry):",
                        "    registry.register(",
                        "        LayerExtension(",
                        '            layer="reporting",',
                        '            key="external_runtime_projection",',
                        '            kind="mart",',
                        '            description="External runtime report.",',
                        f'            module="{module_name}",',
                        f'            source="{module_name}",',
                        '            data_access="warehouse",',
                        "            handler=run_projection,",
                        "        )",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            registry = load_extension_registry(
                extension_paths=(Path(temp_dir),),
                extension_modules=(module_name,),
            )

            result = registry.execute(
                "reporting",
                "external_runtime_projection",
                transformation_service=object(),
                run_id="run-123",
            )

            self.assertEqual(
                {"run_id": "run-123", "status": "projected"},
                result,
            )
            sys.modules.pop(module_name, None)

    def test_executable_reporting_extensions_require_explicit_data_access(self) -> None:
        registry = ExtensionRegistry()

        with self.assertRaisesRegex(
            ValueError,
            "data_access='published' or 'warehouse'",
        ):
            registry.register(
                LayerExtension(
                    layer="reporting",
                    key="missing_contract",
                    kind="mart",
                    description="Missing reporting access contract.",
                    module="tests.missing_contract",
                    source="tests",
                    handler=lambda: None,
                )
            )

    def test_warehouse_reporting_extensions_require_transformation_service_at_execution(
        self,
    ) -> None:
        registry = ExtensionRegistry()
        registry.register(
            LayerExtension(
                layer="reporting",
                key="warehouse_projection",
                kind="mart",
                description="Warehouse-backed report.",
                module="tests.warehouse_projection",
                source="tests",
                data_access="warehouse",
                handler=lambda *, transformation_service: {"status": "ok"},
            )
        )

        with self.assertRaisesRegex(ValueError, "requires transformation_service"):
            registry.execute("reporting", "warehouse_projection")

    def test_reporting_publication_relations_must_use_unique_relation_names(self) -> None:
        registry = ExtensionRegistry()
        registry.register(
            LayerExtension(
                layer="reporting",
                key="published_projection_a",
                kind="mart",
                description="First published relation.",
                module="tests.published_projection_a",
                source="tests",
                data_access="published",
                publication_relations=(
                    ExtensionPublication(
                        relation_name="mart_budget_projection",
                        columns=(("booking_month", "VARCHAR NOT NULL"),),
                        source_query="SELECT '2026-01' AS booking_month",
                        order_by="booking_month",
                    ),
                ),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "already registered: mart_budget_projection",
        ):
            registry.register(
                LayerExtension(
                    layer="reporting",
                    key="published_projection_b",
                    kind="mart",
                    description="Duplicate published relation.",
                    module="tests.published_projection_b",
                    source="tests",
                    data_access="published",
                    publication_relations=(
                        ExtensionPublication(
                            relation_name="mart_budget_projection",
                            columns=(("booking_month", "VARCHAR NOT NULL"),),
                            source_query="SELECT '2026-02' AS booking_month",
                            order_by="booking_month",
                        ),
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
