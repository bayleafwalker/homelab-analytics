import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectMetadataTests(unittest.TestCase):
    def test_pyproject_declares_console_scripts(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

        project = pyproject["project"]
        scripts = project["scripts"]

        self.assertEqual("homelab-analytics", project["name"])
        self.assertIn("homelab-analytics-api", scripts)
        self.assertIn("homelab-analytics-web", scripts)
        self.assertIn("homelab-analytics-worker", scripts)
        self.assertEqual(
            "apps.api.main:main",
            scripts["homelab-analytics-api"],
        )
        self.assertEqual(
            "apps.web.main:main",
            scripts["homelab-analytics-web"],
        )
        self.assertEqual(
            "apps.worker.main:main",
            scripts["homelab-analytics-worker"],
        )

    def test_pyproject_uses_setuptools_package_discovery(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

        setuptools_config = pyproject["tool"]["setuptools"]
        self.assertIn("packages", setuptools_config)
        self.assertIn("find", setuptools_config["packages"])

    def test_pyproject_declares_runtime_dependencies(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

        dependencies = pyproject["project"]["dependencies"]
        self.assertTrue(any(dep.startswith("boto3") for dep in dependencies))
        self.assertTrue(any(dep.startswith("psycopg") for dep in dependencies))
        self.assertTrue(any(dep.startswith("duckdb") for dep in dependencies))
        self.assertTrue(any(dep.startswith("fastapi") for dep in dependencies))
        self.assertTrue(any(dep.startswith("polars") for dep in dependencies))
        self.assertTrue(any(dep.startswith("pyarrow") for dep in dependencies))
        self.assertTrue(
            any(dep.startswith("python-multipart") for dep in dependencies)
        )
        self.assertTrue(any(dep.startswith("uvicorn") for dep in dependencies))

    def test_runtime_bootstrap_files_exist(self) -> None:
        expected_files = [
            "pyproject.toml",
            ".env.example",
            "infra/docker/Dockerfile",
            "infra/examples/compose.yaml",
        ]

        missing = [path for path in expected_files if not (ROOT / path).is_file()]
        self.assertEqual([], missing, f"Missing files: {missing}")


if __name__ == "__main__":
    unittest.main()
