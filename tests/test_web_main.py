from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from apps.web.main import build_app
from packages.shared.settings import AppSettings


class WebMainTests(unittest.TestCase):
    def test_build_app_returns_wsgi_callable(self) -> None:
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

            app = build_app(settings)

            self.assertTrue(callable(app))


if __name__ == "__main__":
    unittest.main()
