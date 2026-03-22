import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apps.web.main import build_runtime, main
from packages.shared.settings import AppSettings


class WebMainTests(unittest.TestCase):
    def test_build_runtime_returns_command_workdir_and_environment(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                api_base_url="http://api.internal:8090",
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )

            with patch("apps.web.main.build_web_command", return_value=["node", "server.js"]):
                command, workdir, environment = build_runtime(settings)

            self.assertEqual(["node", "server.js"], command)
            self.assertTrue(workdir.endswith("apps/web/frontend"))
            self.assertEqual("0.0.0.0", environment["HOSTNAME"])
            self.assertEqual("8081", environment["PORT"])
            self.assertEqual("http://api.internal:8090", environment["HOMELAB_ANALYTICS_API_BASE_URL"])
            self.assertEqual("disabled", environment["HOMELAB_ANALYTICS_AUTH_MODE"])
            self.assertEqual("disabled", environment["HOMELAB_ANALYTICS_IDENTITY_MODE"])

    def test_main_executes_next_runtime_command(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                api_base_url="http://api.internal:8090",
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )

            with patch("apps.web.main.AppSettings.from_env", return_value=settings), patch(
                "apps.web.main.build_runtime",
                return_value=(
                    ["node", "server.js"],
                    "/srv/web",
                    {"HOSTNAME": "0.0.0.0", "PORT": "8081"},
                ),
            ), patch("apps.web.main.subprocess.run") as subprocess_run:
                subprocess_run.return_value.returncode = 0

                exit_code = main()

            self.assertEqual(0, exit_code)
            subprocess_run.assert_called_once_with(
                ["node", "server.js"],
                cwd="/srv/web",
                env={"HOSTNAME": "0.0.0.0", "PORT": "8081"},
                check=False,
            )

    def test_build_runtime_normalizes_local_single_user_mode_for_frontend(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                api_base_url="http://api.internal:8090",
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
                auth_mode="local_single_user",
                session_secret="session-secret",
                break_glass_enabled=True,
            )

            with patch("apps.web.main.build_web_command", return_value=["node", "server.js"]):
                _, _, environment = build_runtime(settings)

            self.assertEqual("local", environment["HOMELAB_ANALYTICS_AUTH_MODE"])
            self.assertEqual(
                "local_single_user",
                environment["HOMELAB_ANALYTICS_IDENTITY_MODE"],
            )

    def test_build_runtime_rejects_oidc_without_required_settings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                api_base_url="http://api.internal:8090",
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
                auth_mode="oidc",
                session_secret="session-secret",
            )

            with self.assertRaisesRegex(ValueError, "OIDC auth requires settings"):
                build_runtime(settings)

    def test_build_runtime_rejects_proxy_mode_without_trusted_cidrs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                api_base_url="http://api.internal:8090",
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
                auth_mode="proxy",
            )

            with self.assertRaisesRegex(
                ValueError,
                "HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS",
            ):
                build_runtime(settings)

    def test_build_runtime_accepts_proxy_mode_with_trusted_cidrs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                api_base_url="http://api.internal:8090",
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
                auth_mode="proxy",
                proxy_trusted_cidrs=("10.0.0.0/8",),
            )

            with patch("apps.web.main.build_web_command", return_value=["node", "server.js"]):
                _, _, environment = build_runtime(settings)

            self.assertEqual("proxy", environment["HOMELAB_ANALYTICS_AUTH_MODE"])
            self.assertEqual("proxy", environment["HOMELAB_ANALYTICS_IDENTITY_MODE"])


if __name__ == "__main__":
    unittest.main()
