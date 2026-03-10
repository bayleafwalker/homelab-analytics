import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = ROOT / "charts" / "homelab-analytics"


@unittest.skipIf(shutil.which("helm") is None, "helm is not installed")
class HelmChartTests(unittest.TestCase):
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
        rendered = subprocess.check_output(
            ["helm", "template", "test-release", str(CHART_DIR)],
            cwd=ROOT,
            text=True,
        )

        for fragment in [
            "kind: ConfigMap",
            "kind: PersistentVolumeClaim",
            "kind: Deployment",
            "name: test-release-homelab-analytics-api",
            "name: test-release-homelab-analytics-web",
            "name: test-release-homelab-analytics-worker",
            "kind: Service",
            "HOMELAB_ANALYTICS_DATA_DIR",
            "HOMELAB_ANALYTICS_WEB_PORT",
            "watch-account-transactions-inbox",
        ]:
            self.assertIn(fragment, rendered)


if __name__ == "__main__":
    unittest.main()
