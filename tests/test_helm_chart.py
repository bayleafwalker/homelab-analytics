import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = ROOT / "charts" / "homelab-analytics"
RUNTIME_SECRETS_EXAMPLE = CHART_DIR / "values.runtime-secrets-example.yaml"


@unittest.skipIf(shutil.which("helm") is None, "helm is not installed")
class HelmChartTests(unittest.TestCase):
    def _render_chart(self, *extra_args: str) -> str:
        return subprocess.check_output(
            ["helm", "template", "test-release", str(CHART_DIR), *extra_args],
            cwd=ROOT,
            text=True,
        )

    def _rendered_documents(self, *extra_args: str) -> list[dict]:
        rendered = self._render_chart(*extra_args)
        return [
            document
            for document in yaml.safe_load_all(rendered)
            if isinstance(document, dict)
        ]

    def test_chart_lints(self) -> None:
        completed = subprocess.run(
            ["helm", "lint", str(CHART_DIR)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_chart_renders_core_resources(self) -> None:
        rendered = self._render_chart()

        for fragment in [
            "kind: ConfigMap",
            "kind: PersistentVolumeClaim",
            "kind: Deployment",
            "name: test-release-homelab-analytics-api",
            "name: test-release-homelab-analytics-web",
            "name: test-release-homelab-analytics-worker",
            "kind: Service",
            "HOMELAB_ANALYTICS_DATA_DIR",
            "HOMELAB_ANALYTICS_AUTH_MODE",
            "HOMELAB_ANALYTICS_WEB_PORT",
            "watch-schedule-dispatches",
        ]:
            self.assertIn(fragment, rendered)

    def test_chart_renders_expected_workload_images_and_commands(self) -> None:
        documents = self._rendered_documents(
            "--set",
            "image.tag=2026.03.10",
            "--set",
            "webImage.tag=2026.03.10",
            "--set",
            "api.replicas=2",
            "--set",
            "web.replicas=3",
        )

        deployments = {
            document["metadata"]["name"]: document
            for document in documents
            if document.get("kind") == "Deployment"
        }

        api = deployments["test-release-homelab-analytics-api"]
        web = deployments["test-release-homelab-analytics-web"]
        worker = deployments["test-release-homelab-analytics-worker"]

        self.assertEqual(2, api["spec"]["replicas"])
        self.assertEqual(3, web["spec"]["replicas"])
        self.assertEqual(1, worker["spec"]["replicas"])
        self.assertEqual(
            "ghcr.io/bayleafwalker/homelab-analytics:2026.03.10",
            api["spec"]["template"]["spec"]["containers"][0]["image"],
        )
        self.assertEqual(
            ["homelab-analytics-api"],
            api["spec"]["template"]["spec"]["containers"][0]["command"],
        )
        self.assertEqual(
            "ghcr.io/bayleafwalker/homelab-analytics-web:2026.03.10",
            web["spec"]["template"]["spec"]["containers"][0]["image"],
        )
        self.assertNotIn(
            "command",
            web["spec"]["template"]["spec"]["containers"][0],
        )
        self.assertEqual(
            ["homelab-analytics-worker", "watch-schedule-dispatches"],
            worker["spec"]["template"]["spec"]["containers"][0]["command"],
        )
        self.assertIn(
            {
                "name": "HOMELAB_ANALYTICS_API_BASE_URL",
                "value": "http://test-release-homelab-analytics-api:8080",
            },
            web["spec"]["template"]["spec"]["containers"][0]["env"],
        )

    def test_chart_uses_secret_refs_without_rendering_inline_credentials(self) -> None:
        fake_dsn = "postgresql://inline-user:inline-password@db:5432/homelab"
        fake_access_key = "minio-inline-secret"
        rendered = self._render_chart(
            "--set",
            "api.secretEnvFrom[0]=api-runtime-secrets",
            "--set",
            "web.secretEnvFrom[0]=web-runtime-secrets",
            "--set",
            "worker.secretEnvFrom[0]=worker-runtime-secrets",
        )
        documents = [
            document
            for document in yaml.safe_load_all(rendered)
            if isinstance(document, dict)
        ]

        deployments = {
            document["metadata"]["name"]: document
            for document in documents
            if document.get("kind") == "Deployment"
        }

        self.assertIn('name: "api-runtime-secrets"', rendered)
        self.assertIn('name: "web-runtime-secrets"', rendered)
        self.assertIn('name: "worker-runtime-secrets"', rendered)
        self.assertNotIn(fake_dsn, rendered)
        self.assertNotIn(fake_access_key, rendered)
        self.assertNotIn("kind: Secret", rendered)

        self.assertIn(
            {"secretRef": {"name": "api-runtime-secrets"}},
            deployments["test-release-homelab-analytics-api"]["spec"]["template"][
                "spec"
            ]["containers"][0]["envFrom"],
        )
        self.assertIn(
            {"secretRef": {"name": "web-runtime-secrets"}},
            deployments["test-release-homelab-analytics-web"]["spec"]["template"][
                "spec"
            ]["containers"][0]["envFrom"],
        )
        self.assertIn(
            {"secretRef": {"name": "worker-runtime-secrets"}},
            deployments["test-release-homelab-analytics-worker"]["spec"]["template"][
                "spec"
            ]["containers"][0]["envFrom"],
        )

    def test_chart_runtime_secret_example_isolates_workload_credentials(self) -> None:
        documents = self._rendered_documents("-f", str(RUNTIME_SECRETS_EXAMPLE))

        deployments = {
            document["metadata"]["name"]: document
            for document in documents
            if document.get("kind") == "Deployment"
        }

        api_env_from = deployments["test-release-homelab-analytics-api"]["spec"][
            "template"
        ]["spec"]["containers"][0]["envFrom"]
        web_env_from = deployments["test-release-homelab-analytics-web"]["spec"][
            "template"
        ]["spec"]["containers"][0]["envFrom"]
        worker_env_from = deployments["test-release-homelab-analytics-worker"]["spec"][
            "template"
        ]["spec"]["containers"][0]["envFrom"]

        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-reporting-read"}},
            api_env_from,
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-auth-local"}},
            api_env_from,
        )
        self.assertEqual(api_env_from, web_env_from)
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-landing-write"}},
            worker_env_from,
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-transformation-write"}},
            worker_env_from,
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-auth-local"}},
            worker_env_from,
        )
        self.assertNotIn(
            {"secretRef": {"name": "homelab-analytics-landing-write"}},
            api_env_from,
        )


if __name__ == "__main__":
    unittest.main()
