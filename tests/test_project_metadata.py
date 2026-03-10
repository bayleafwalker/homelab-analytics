import tomllib
import unittest
from pathlib import Path

import yaml

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
            ".dockerignore",
            "infra/docker/Dockerfile",
            "infra/examples/compose.yaml",
        ]

        missing = [path for path in expected_files if not (ROOT / path).is_file()]
        self.assertEqual([], missing, f"Missing files: {missing}")

    def test_dockerignore_excludes_local_runtime_and_test_artifacts(self) -> None:
        content = (ROOT / ".dockerignore").read_text()

        for fragment in [
            ".git",
            ".venv",
            ".mypy_cache",
            ".pytest_cache",
            "tests/",
            "docs/",
            "requirements/",
        ]:
            self.assertIn(fragment, content)

    def test_example_compose_reuses_shared_application_image(self) -> None:
        content = (ROOT / "infra" / "examples" / "compose.yaml").read_text()

        self.assertEqual(3, content.count("image: homelab-analytics:latest"))

    def test_example_compose_pins_third_party_images(self) -> None:
        compose = yaml.safe_load((ROOT / "infra" / "examples" / "compose.yaml").read_text())
        services = compose["services"]

        self.assertEqual("postgres:16-alpine", services["postgres"]["image"])
        self.assertEqual(
            "minio/minio:RELEASE.2025-09-07T16-13-09Z-cpuv1",
            services["minio"]["image"],
        )
        self.assertNotIn(":latest", services["minio"]["image"])

    def test_example_compose_defines_api_and_web_healthchecks(self) -> None:
        content = (ROOT / "infra" / "examples" / "compose.yaml").read_text()

        self.assertIn("http://127.0.0.1:8080/health", content)
        self.assertIn("http://127.0.0.1:8081/health", content)
        self.assertGreaterEqual(content.count("healthcheck:"), 3)

    def test_example_compose_enforces_release_ops_dependency_contract(self) -> None:
        compose = yaml.safe_load((ROOT / "infra" / "examples" / "compose.yaml").read_text())
        services = compose["services"]

        for service_name in ["api", "web", "worker"]:
            service = services[service_name]
            self.assertEqual(
                "service_healthy",
                service["depends_on"]["postgres"]["condition"],
            )
            self.assertEqual(
                "service_started",
                service["depends_on"]["minio"]["condition"],
            )

        for service_name, port in [("api", 8080), ("web", 8081)]:
            healthcheck = services[service_name]["healthcheck"]
            self.assertEqual("5s", healthcheck["interval"])
            self.assertEqual("5s", healthcheck["timeout"])
            self.assertEqual(12, healthcheck["retries"])
            self.assertIn(
                f"http://127.0.0.1:{port}/health",
                " ".join(healthcheck["test"]),
            )


if __name__ == "__main__":
    unittest.main()
