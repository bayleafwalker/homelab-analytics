from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.shared.external_registry import (
    EXTERNAL_REGISTRY_MANIFEST_FILENAME,
    _build_git_environment,
    load_extension_registry_manifest,
    sync_extension_registry_source,
)
from packages.shared.secrets import EnvironmentSecretResolver
from packages.storage.ingestion_config import (
    ExtensionRegistrySourceCreate,
    ExtensionRegistrySourceRecord,
    IngestionConfigRepository,
)
from tests.external_registry_test_support import create_git_extension_repository


class ExternalRegistrySupportTests(unittest.TestCase):
    def test_manifest_loader_parses_extension_and_function_modules(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / EXTERNAL_REGISTRY_MANIFEST_FILENAME).write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "import_paths": ["."],
                        "extension_modules": ["household.extensions"],
                        "function_modules": ["household.functions"],
                        "minimum_platform_version": "0.1.0",
                    }
                ),
                encoding="utf-8",
            )

            manifest = load_extension_registry_manifest(root)

            self.assertEqual(("household.extensions",), manifest.extension_modules)
            self.assertEqual(("household.functions",), manifest.function_modules)
            self.assertEqual((".",), manifest.import_paths)

    def test_sync_records_failed_revision_when_manifest_is_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            repository.create_extension_registry_source(
                ExtensionRegistrySourceCreate(
                    extension_registry_source_id="missing-manifest",
                    name="Missing Manifest",
                    source_kind="path",
                    location=str(Path(temp_dir) / "extensions"),
                )
            )
            (Path(temp_dir) / "extensions").mkdir(parents=True, exist_ok=True)

            result = sync_extension_registry_source(repository, "missing-manifest")

            self.assertFalse(result.passed)
            self.assertEqual("failed", result.revision.sync_status)
            self.assertIn("manifest not found", result.revision.validation_error.lower())
            self.assertEqual(
                [result.revision.extension_registry_revision_id],
                [
                    record.extension_registry_revision_id
                    for record in repository.list_extension_registry_revisions(
                        extension_registry_source_id="missing-manifest"
                    )
                ],
            )

    def test_sync_materializes_git_revision_with_resolved_commit_sha(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            git_repository = create_git_extension_repository(
                temp_root,
                module_name="custom_git_extension",
                extension_key="git_loaded_projection",
            )
            repository = IngestionConfigRepository(temp_root / "config.db")
            repository.create_extension_registry_source(
                ExtensionRegistrySourceCreate(
                    extension_registry_source_id="git-source",
                    name="Git Source",
                    source_kind="git",
                    location=str(git_repository.repo_root),
                    desired_ref="main",
                )
            )

            result = sync_extension_registry_source(
                repository,
                "git-source",
                cache_root=temp_root / "external-registry-cache",
            )

            self.assertTrue(result.passed)
            self.assertEqual(git_repository.commit_sha, result.revision.resolved_ref)
            self.assertEqual(git_repository.commit_sha, result.revision.content_fingerprint)
            self.assertTrue(Path(result.revision.runtime_path).is_dir())
            self.assertTrue(Path(result.revision.manifest_path).is_file())

    def test_git_environment_uses_secret_reference_for_http_auth(self) -> None:
        environment = _build_git_environment(
            ExtensionRegistrySourceRecord(
                extension_registry_source_id="github-source",
                name="GitHub Source",
                source_kind="git",
                location="https://github.com/example/private-repo.git",
                desired_ref="main",
                subdirectory=None,
                auth_secret_name="github-registry",
                auth_secret_key="token",
                enabled=True,
                archived=False,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            secret_resolver=EnvironmentSecretResolver(
                {
                    "HOMELAB_ANALYTICS_SECRET__GITHUB_REGISTRY__TOKEN": "ghp_example_token"
                }
            ),
        )

        self.assertEqual("0", environment["GIT_TERMINAL_PROMPT"])
        self.assertEqual("1", environment["GIT_CONFIG_COUNT"])
        self.assertEqual("http.extraHeader", environment["GIT_CONFIG_KEY_0"])
        self.assertTrue(
            environment["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
        )


if __name__ == "__main__":
    unittest.main()
