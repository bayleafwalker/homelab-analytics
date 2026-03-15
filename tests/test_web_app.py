import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apps.web.app import (
    build_web_command,
    build_web_environment,
    frontend_root,
    standalone_entrypoint,
)
from packages.shared.settings import AppSettings


class WebAppTests(unittest.TestCase):
    def test_frontend_root_points_to_nextjs_app(self) -> None:
        root = frontend_root()

        self.assertTrue((root / "package.json").is_file())
        self.assertTrue((root / "app" / "page.js").is_file())
        self.assertTrue((root / "app" / "login" / "page.js").is_file())

    def test_build_web_environment_sets_hostname_port_and_api_base_url(self) -> None:
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

            environment = build_web_environment(settings, environ={"NODE_ENV": "production"})

            self.assertEqual("0.0.0.0", environment["HOSTNAME"])
            self.assertEqual("8081", environment["PORT"])
            self.assertEqual("http://api.internal:8090", environment["HOMELAB_ANALYTICS_API_BASE_URL"])
            self.assertEqual("production", environment["NODE_ENV"])

    def test_build_web_command_requires_standalone_build_output(self) -> None:
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
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )

            with self.assertRaises(FileNotFoundError):
                build_web_command(settings)

    def test_build_web_command_points_to_next_standalone_server(self) -> None:
        with TemporaryDirectory() as temp_dir:
            entrypoint = Path(temp_dir) / "server.js"
            entrypoint.write_text("console.log('ok');")
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
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )

            with patch("apps.web.app.standalone_entrypoint", return_value=entrypoint):
                command = build_web_command(settings)

            self.assertEqual(["node", str(entrypoint)], command)

    def test_standalone_entrypoint_matches_next_output_layout(self) -> None:
        self.assertEqual(
            frontend_root() / ".next" / "standalone" / "server.js",
            standalone_entrypoint(),
        )


if __name__ == "__main__":
    unittest.main()
