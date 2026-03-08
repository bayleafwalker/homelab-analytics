from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_expected_directories_exist(self) -> None:
        expected = [
            "apps/api",
            "apps/worker",
            "apps/web",
            "packages/connectors",
            "packages/pipelines",
            "packages/storage",
            "packages/analytics",
            "packages/shared",
            "charts/homelab-analytics",
            "infra/docker",
            "infra/examples",
            "docs/architecture",
            "docs/decisions",
            "docs/notes",
            "docs/plans",
            "tests",
        ]

        missing = [path for path in expected if not (ROOT / path).is_dir()]
        self.assertEqual([], missing, f"Missing directories: {missing}")

    def test_expected_docs_exist(self) -> None:
        expected = [
            "README.md",
            "AGENTS.md",
            "docs/README.md",
            "docs/plans/homelab-analytics-platform-plan.md",
            "docs/architecture/data-platform-architecture.md",
            "docs/decisions/compute-and-orchestration-options.md",
            "docs/notes/appservice-cluster-integration-notes.md",
        ]

        missing = [path for path in expected if not (ROOT / path).is_file()]
        self.assertEqual([], missing, f"Missing files: {missing}")

    def test_architecture_doc_covers_core_layers(self) -> None:
        content = (ROOT / "docs/architecture/data-platform-architecture.md").read_text()

        for term in [
            "landing",
            "transformation",
            "reporting",
            "bronze",
            "silver",
            "gold",
            "SCD",
            "data quality",
            "contract",
            "API",
            "dashboard",
        ]:
            self.assertIn(term, content, f"Architecture doc missing term: {term}")

    def test_plan_mentions_security_and_release_path(self) -> None:
        content = (ROOT / "docs/plans/homelab-analytics-platform-plan.md").read_text()

        for term in [
            "OIDC",
            "External Secrets",
            "Helm",
            "Docker",
            "OneDrive",
            "Nextcloud",
            "Google Drive",
            "Home Assistant",
        ]:
            self.assertIn(term, content, f"Plan missing term: {term}")


if __name__ == "__main__":
    unittest.main()
