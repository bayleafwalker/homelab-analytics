import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.extensions import load_extension_registry
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

    def test_builtin_transformation_and_reporting_extensions_execute(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            run = service.ingest_file(FIXTURES / "account_transactions_valid.csv")
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
                service=service,
                run_id=run.run_id,
            )

            self.assertEqual(2, len(transactions))
            self.assertEqual("CHK-001", transactions[0].account_id)
            self.assertEqual("2365.85", str(summaries[0].net))

    def test_external_reporting_extension_can_execute(self) -> None:
        with TemporaryDirectory() as temp_dir:
            module_name = f"test_external_runtime_{uuid4().hex}"
            module_path = Path(temp_dir) / f"{module_name}.py"
            module_path.write_text(
                "\n".join(
                    [
                        "from packages.shared.extensions import LayerExtension",
                        "",
                        "def run_projection(*, service, run_id):",
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
                service=object(),
                run_id="run-123",
            )

            self.assertEqual(
                {"run_id": "run-123", "status": "projected"},
                result,
            )
            sys.modules.pop(module_name, None)


if __name__ == "__main__":
    unittest.main()
