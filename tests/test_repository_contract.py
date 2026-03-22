import unittest
from pathlib import Path

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
            "docs/agents",
            "docs/decisions",
            "docs/notes",
            "docs/plans",
            "docs/runbooks",
            "tests",
        ]

        missing = [path for path in expected if not (ROOT / path).is_dir()]
        self.assertEqual([], missing, f"Missing directories: {missing}")

    def test_expected_docs_exist(self) -> None:
        expected = [
            "README.md",
            "AGENTS.md",
            "docs/README.md",
            "docs/agents/planning.md",
            "docs/agents/implementation.md",
            "docs/agents/review.md",
            "docs/agents/release-ops.md",
            "docs/plans/homelab-analytics-platform-plan.md",
            "docs/architecture/data-platform-architecture.md",
            "docs/decisions/compute-and-orchestration-options.md",
            "docs/notes/appservice-cluster-integration-notes.md",
            "docs/runbooks/operations.md",
            "docs/runbooks/backup-and-restore.md",
        ]

        missing = [path for path in expected if not (ROOT / path).is_file()]
        self.assertEqual([], missing, f"Missing files: {missing}")

    def test_frontend_contract_artifacts_exist(self) -> None:
        expected = [
            "apps/web/frontend/tsconfig.json",
            "apps/web/frontend/next-env.d.ts",
            "apps/web/frontend/scripts/codegen.mjs",
            "apps/web/frontend/generated/openapi.json",
            "apps/web/frontend/generated/publication-contracts.json",
            "apps/web/frontend/generated/api.d.ts",
            "apps/web/frontend/generated/publication-contracts.ts",
        ]

        missing = [path for path in expected if not (ROOT / path).is_file()]
        self.assertEqual([], missing, f"Missing frontend contract artifacts: {missing}")

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
            "extension",
            "external",
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
            "custom paths",
            "external repositories",
        ]:
            self.assertIn(term, content, f"Plan missing term: {term}")


if __name__ == "__main__":
    unittest.main()
