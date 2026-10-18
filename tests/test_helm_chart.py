import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = ROOT / "charts" / "homelab-analytics"
RUNTIME_SECRETS_EXAMPLE = CHART_DIR / "values.runtime-secrets-example.yaml"
OIDC_INGRESS_EXAMPLE = CHART_DIR / "values.oidc-ingress-example.yaml"


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
            "HOMELAB_ANALYTICS_IDENTITY_MODE",
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
            "/health",
            api["spec"]["template"]["spec"]["containers"][0]["livenessProbe"]["httpGet"]["path"],
        )
        self.assertEqual(
            "/ready",
            api["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["httpGet"]["path"],
        )
        self.assertEqual(
            ["homelab-analytics-api"],
            api["spec"]["template"]["spec"]["containers"][0]["command"],
        )
        self.assertEqual(
            "ghcr.io/bayleafwalker/homelab-analytics-web:2026.03.10",
            web["spec"]["template"]["spec"]["containers"][0]["image"],
        )
        self.assertEqual(
            "/ready",
            web["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["httpGet"]["path"],
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
            {"secretRef": {"name": "homelab-analytics-api-database"}},
            api_env_from,
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-blob-storage"}},
            api_env_from,
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-auth-oidc"}},
            api_env_from,
        )
        self.assertEqual(
            {"secretRef": {"name": "homelab-analytics-auth-oidc"}},
            web_env_from[-1],
        )
        self.assertEqual(2, len(web_env_from))
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-worker-database"}},
            worker_env_from,
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-blob-storage"}},
            worker_env_from,
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-landing-write"}},
            worker_env_from,
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-transformation-write"}},
            worker_env_from,
        )
        self.assertNotIn(
            {"secretRef": {"name": "homelab-analytics-landing-write"}},
            api_env_from,
        )

    def test_chart_oidc_ingress_example_renders_ingress_and_alert_rules(self) -> None:
        documents = self._rendered_documents("-f", str(OIDC_INGRESS_EXAMPLE))

        resources = {
            (document["kind"], document["metadata"]["name"]): document
            for document in documents
        }

        ingress = resources[("Ingress", "test-release-homelab-analytics")]
        rule = resources[("PrometheusRule", "test-release-homelab-analytics")]
        api = resources[("Deployment", "test-release-homelab-analytics-api")]
        web = resources[("Deployment", "test-release-homelab-analytics-web")]
        worker = resources[("Deployment", "test-release-homelab-analytics-worker")]

        self.assertEqual("nginx", ingress["spec"]["ingressClassName"])
        self.assertEqual("analytics.example.internal", ingress["spec"]["rules"][0]["host"])
        self.assertEqual(
            "homelab-analytics-web-tls",
            ingress["spec"]["tls"][0]["secretName"],
        )
        expressions = [entry["expr"] for entry in rule["spec"]["groups"][0]["rules"]]
        self.assertTrue(
            any("worker_stale_dispatches > 0" in expression for expression in expressions)
        )
        self.assertTrue(
            any("auth_service_tokens_expiring_7d" in expression for expression in expressions)
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-api-database"}},
            api["spec"]["template"]["spec"]["containers"][0]["envFrom"],
        )
        self.assertEqual(
            {"secretRef": {"name": "homelab-analytics-auth-oidc"}},
            web["spec"]["template"]["spec"]["containers"][0]["envFrom"][-1],
        )
        self.assertEqual(
            2,
            len(web["spec"]["template"]["spec"]["containers"][0]["envFrom"]),
        )
        self.assertIn(
            {"secretRef": {"name": "homelab-analytics-worker-database"}},
            worker["spec"]["template"]["spec"]["containers"][0]["envFrom"],
        )

    def test_chart_pins_images_by_digest_when_configured(self) -> None:
        documents = self._rendered_documents(
            "--set",
            "image.digest=sha256:1111111111111111111111111111111111111111111111111111111111111111",
            "--set",
            "webImage.digest=sha256:2222222222222222222222222222222222222222222222222222222222222222",
            "--set",
            "image.tag=ignored",
            "--set",
            "webImage.tag=ignored",
        )
        deployments = {
            document["metadata"]["name"]: document
            for document in documents
            if document.get("kind") == "Deployment"
        }

        for name in (
            "test-release-homelab-analytics-api",
            "test-release-homelab-analytics-worker",
        ):
            self.assertEqual(
                "ghcr.io/bayleafwalker/homelab-analytics@sha256:"
                "1111111111111111111111111111111111111111111111111111111111111111",
                deployments[name]["spec"]["template"]["spec"]["containers"][0]["image"],
            )
        self.assertEqual(
            "ghcr.io/bayleafwalker/homelab-analytics-web@sha256:"
            "2222222222222222222222222222222222222222222222222222222222222222",
            deployments["test-release-homelab-analytics-web"]["spec"]["template"]["spec"][
                "containers"
            ][0]["image"],
        )

    def test_web_workload_stays_off_the_data_claim_by_default(self) -> None:
        documents = self._rendered_documents()
        deployments = {
            document["metadata"]["name"]: document
            for document in documents
            if document.get("kind") == "Deployment"
        }

        web_spec = deployments["test-release-homelab-analytics-web"]["spec"]["template"][
            "spec"
        ]
        self.assertNotIn("volumes", web_spec)
        self.assertNotIn("volumeMounts", web_spec["containers"][0])

        for name in (
            "test-release-homelab-analytics-api",
            "test-release-homelab-analytics-worker",
        ):
            workload = deployments[name]["spec"]["template"]["spec"]
            self.assertEqual(
                "test-release-homelab-analytics-data",
                workload["volumes"][0]["persistentVolumeClaim"]["claimName"],
            )

    def test_web_workload_can_opt_into_the_data_claim(self) -> None:
        documents = self._rendered_documents("--set", "web.mountData=true")
        web = next(
            document
            for document in documents
            if document.get("kind") == "Deployment"
            and document["metadata"]["name"] == "test-release-homelab-analytics-web"
        )

        self.assertEqual(
            "test-release-homelab-analytics-data",
            web["spec"]["template"]["spec"]["volumes"][0]["persistentVolumeClaim"][
                "claimName"
            ],
        )
        self.assertEqual(
            "/data",
            web["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0][
                "mountPath"
            ],
        )

    def test_observability_and_backup_resources_render_when_enabled(self) -> None:
        import json

        documents = self._rendered_documents(
            "--set", "monitoring.prometheusRule.enabled=true",
            "--set", "monitoring.podMonitor.enabled=true",
            "--set", "monitoring.podMonitor.scrapeTokenSecret.name=metrics-token",
            "--set", "monitoring.grafanaDashboard.enabled=true",
            "--set", "backup.intervalSeconds=86400",
        )
        by_kind_name = {
            (document["kind"], document["metadata"]["name"]): document
            for document in documents
        }

        rule = by_kind_name[("PrometheusRule", "test-release-homelab-analytics")]
        slo_group = rule["spec"]["groups"][1]
        self.assertTrue(slo_group["name"].endswith(".slo"))
        alerts = {entry.get("alert") for entry in slo_group["rules"]}
        for alert in (
            "HomelabAnalyticsApiErrorBudgetFastBurn",
            "HomelabAnalyticsSourceOverdue",
            "HomelabAnalyticsPublicationRefreshFailing",
            "HomelabAnalyticsWorkerLoopStalled",
            "HomelabAnalyticsBackupStale",
        ):
            self.assertIn(alert, alerts)

        monitor = by_kind_name[("PodMonitor", "test-release-homelab-analytics")]
        endpoints = monitor["spec"]["podMetricsEndpoints"]
        self.assertEqual(["http", "metrics"], [endpoint["port"] for endpoint in endpoints])
        self.assertEqual("Metrics", endpoints[0]["authorization"]["type"])

        dashboard = by_kind_name[
            ("ConfigMap", "test-release-homelab-analytics-ops-dashboard")
        ]
        self.assertEqual("1", dashboard["metadata"]["labels"]["grafana_dashboard"])
        parsed = json.loads(dashboard["data"]["homelab-analytics-ops.json"])
        self.assertEqual("homelab-analytics-ops", parsed["uid"])

        config = by_kind_name[("ConfigMap", "test-release-homelab-analytics-config")]
        self.assertEqual("86400", config["data"]["HOMELAB_ANALYTICS_BACKUP_INTERVAL_SECONDS"])
        worker = by_kind_name[("Deployment", "test-release-homelab-analytics-worker")]
        container = worker["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(9464, container["ports"][0]["containerPort"])
        self.assertIn(
            {"name": "HOMELAB_ANALYTICS_WORKER_METRICS_PORT", "value": "9464"},
            container["env"],
        )

    def test_observability_resources_are_off_by_default(self) -> None:
        kinds = {document["kind"] for document in self._rendered_documents()}
        self.assertNotIn("PodMonitor", kinds)
        self.assertNotIn("PrometheusRule", kinds)
        config = next(
            document
            for document in self._rendered_documents()
            if document["kind"] == "ConfigMap"
        )
        self.assertNotIn("HOMELAB_ANALYTICS_BACKUP_INTERVAL_SECONDS", config["data"])

    def _config_data(self, *extra_args: str) -> dict:
        return next(
            document["data"]
            for document in self._rendered_documents(*extra_args)
            if document["kind"] == "ConfigMap"
            and document["metadata"]["name"] == "test-release-homelab-analytics-config"
        )

    def test_oidc_values_are_off_until_configured(self) -> None:
        data = self._config_data()
        self.assertEqual("oidc", data["HOMELAB_ANALYTICS_IDENTITY_MODE"])
        self.assertEqual([], [key for key in data if key.startswith("HOMELAB_ANALYTICS_OIDC_")])

    def test_oidc_values_render_env_the_application_parses(self) -> None:
        from tempfile import TemporaryDirectory

        from packages.shared.settings import AppSettings

        oidc_values = {
            "oidc": {
                "issuerUrl": "https://auth.example.test/application/o/homelab-analytics/",
                "discoveryUrl": "https://auth.example.test/discovery",
                "redirectUri": "https://analytics.example.test/auth/callback",
                "postLogoutRedirectUri": "https://analytics.example.test/login",
                "apiAudience": "homelab-analytics-api",
                "scopes": ["openid", "profile", "email", "groups"],
                "usernameClaim": "preferred_username",
                "groupsClaim": "groups",
                "permissionsClaim": "hla_permissions",
                "permissionGroupMappings": [
                    "hla-auditors=control.policy.read",
                    "hla-ops=reports.read,control.action_proposals.draft",
                ],
                "readerGroups": ["hla-readers"],
                "operatorGroups": ["hla-operators", "hla-oncall"],
                "adminGroups": ["hla-admins"],
                "clientSecretRef": "authentik-hla/client_secret",
                "jwksCacheSeconds": 600,
                "clockSkewSeconds": "30",
            }
        }
        with TemporaryDirectory() as tmp:
            values_file = Path(tmp) / "oidc-values.yaml"
            values_file.write_text(yaml.safe_dump(oidc_values))
            data = self._config_data("-f", str(values_file))

            # The ConfigMap carries no credentials: client id and secret stay in Secrets.
            self.assertNotIn("HOMELAB_ANALYTICS_OIDC_CLIENT_ID", data)
            self.assertNotIn("HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET", data)
            self.assertEqual("600", data["HOMELAB_ANALYTICS_OIDC_JWKS_CACHE_SECONDS"])
            self.assertEqual(
                "hla-auditors=control.policy.read;hla-ops=reports.read,control.action_proposals.draft",
                data["HOMELAB_ANALYTICS_OIDC_PERMISSION_GROUP_MAPPINGS"],
            )

            settings = AppSettings.from_env({**data, "HOMELAB_ANALYTICS_DATA_DIR": tmp})
        self.assertEqual(oidc_values["oidc"]["issuerUrl"], settings.oidc_issuer_url)
        self.assertEqual("https://auth.example.test/discovery", settings.oidc_discovery_url)
        self.assertEqual(
            "https://analytics.example.test/auth/callback", settings.oidc_redirect_uri
        )
        self.assertEqual(
            "https://analytics.example.test/login", settings.oidc_post_logout_redirect_uri
        )
        self.assertEqual("homelab-analytics-api", settings.oidc_api_audience)
        self.assertEqual(("openid", "profile", "email", "groups"), settings.oidc_scopes)
        self.assertEqual("hla_permissions", settings.oidc_permissions_claim)
        self.assertEqual(
            (
                "hla-auditors=control.policy.read",
                "hla-ops=reports.read,control.action_proposals.draft",
            ),
            settings.oidc_permission_group_mappings,
        )
        self.assertEqual(("hla-readers",), settings.oidc_reader_groups)
        self.assertEqual(("hla-operators", "hla-oncall"), settings.oidc_operator_groups)
        self.assertEqual(("hla-admins",), settings.oidc_admin_groups)
        self.assertEqual("authentik-hla/client_secret", settings.oidc_client_secret_ref)
        self.assertEqual(600, settings.oidc_jwks_cache_seconds)
        self.assertEqual(30, settings.oidc_clock_skew_seconds)

    def test_oidc_values_are_skipped_outside_oidc_mode_and_never_duplicate_common_env(
        self,
    ) -> None:
        local = self._config_data(
            "--set",
            "commonEnv.HOMELAB_ANALYTICS_IDENTITY_MODE=local_single_user",
            "--set",
            "oidc.issuerUrl=https://auth.example.test/",
        )
        self.assertNotIn("HOMELAB_ANALYTICS_OIDC_ISSUER_URL", local)

        rendered = self._render_chart(
            "--set",
            "commonEnv.HOMELAB_ANALYTICS_OIDC_ISSUER_URL=https://from-common-env.test/",
            "--set",
            "oidc.issuerUrl=https://from-oidc-values.test/",
        )
        self.assertEqual(1, rendered.count("HOMELAB_ANALYTICS_OIDC_ISSUER_URL:"))
        self.assertIn("https://from-common-env.test/", rendered)
        self.assertNotIn("https://from-oidc-values.test/", rendered)


if __name__ == "__main__":
    unittest.main()
