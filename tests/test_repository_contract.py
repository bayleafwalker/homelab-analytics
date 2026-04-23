import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_expected_directories_exist(self) -> None:
        expected = [
            ".agents/skills",
            ".agents/skills/domain-impact-scan",
            ".agents/skills/sprint-packet",
            ".agents/skills/code-change-verification",
            ".agents/skills/pr-handoff-summary",
            ".agents/skills/sprint-snapshot",
            ".agents/skills/kctl-extract",
            "apps/api",
            "apps/worker",
            "apps/web",
            "packages/connectors",
            "packages/pipelines",
            "packages/storage",

            "packages/shared",
            "charts/homelab-analytics",
            "infra/docker",
            "infra/examples",
            "docs/architecture",
            "docs/agents",
            "docs/decisions",
            "docs/knowledge",
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
            "docs/agent-guidance-refactor.md",
            "docs/README.md",
            "docs/knowledge/README.md",
            "docs/knowledge/knowledge-base.md",
            "docs/sprint-snapshots/sprint-current.txt",
            "docs/agents/planning.md",
            "docs/agents/implementation.md",
            "docs/agents/review.md",
            "docs/agents/release-ops.md",
            "docs/plans/homelab-analytics-platform-plan.md",
            "docs/architecture/contract-governance.md",
            "docs/architecture/data-platform-architecture.md",
            "docs/architecture/sqlite-control-plane-capability-matrix.md",
            "docs/decisions/compute-and-orchestration-options.md",
            "docs/notes/appservice-cluster-integration-notes.md",
            "docs/runbooks/operations.md",
            "docs/runbooks/backup-and-restore.md",
            "docs/runbooks/sprint-and-knowledge-operations.md",
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

    def test_tracked_symlinks_stay_within_repository(self) -> None:
        repo_root = ROOT.resolve()
        result = subprocess.run(
            ["git", "ls-files", "-s"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        tracked_symlinks = [
            Path(line.split(maxsplit=3)[3])
            for line in result.stdout.splitlines()
            if line.startswith("120000 ")
        ]

        escaped = []
        for path in tracked_symlinks:
            resolved = (ROOT / path).resolve(strict=False)
            try:
                resolved.relative_to(repo_root)
            except ValueError:
                escaped.append(f"{path} -> {resolved}")

        self.assertEqual(
            [],
            escaped,
            f"Tracked symlinks must not resolve outside the repository: {escaped}",
        )

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
