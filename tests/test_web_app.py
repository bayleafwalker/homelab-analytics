import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from wsgiref.util import setup_testing_defaults

from apps.web.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.promotion import promote_run
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def invoke_wsgi_app(app, method: str, path: str) -> tuple[int, dict[str, str], str]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    environ["wsgi.input"] = io.BytesIO(b"")
    environ["CONTENT_LENGTH"] = "0"

    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    response_iterable = app(environ, start_response)
    response_body = b"".join(response_iterable).decode("utf-8")
    status_code = int(str(captured["status"]).split()[0])
    headers = captured["headers"]
    return status_code, headers, response_body


class WebAppTests(unittest.TestCase):
    def test_dashboard_renders_empty_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            app = create_app(service)

            status_code, headers, body = invoke_wsgi_app(app, "GET", "/")

            self.assertEqual(200, status_code)
            self.assertEqual("text/html; charset=utf-8", headers["Content-Type"])
            self.assertIn("Homelab Analytics", body)
            self.assertIn("No successful imports yet.", body)

    def test_dashboard_renders_latest_cashflow_and_recent_runs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            transformation_service = TransformationService(
                DuckDBStore.open(str(Path(temp_dir) / "warehouse.duckdb"))
            )
            valid_run = service.ingest_file(FIXTURES / "account_transactions_valid.csv")
            service.ingest_file(FIXTURES / "account_transactions_invalid_values.csv")
            promote_run(
                valid_run.run_id,
                account_service=service,
                transformation_service=transformation_service,
            )
            app = create_app(service, transformation_service=transformation_service)

            status_code, _, body = invoke_wsgi_app(app, "GET", "/")

            self.assertEqual(200, status_code)
            self.assertIn("2365.85", body)
            self.assertIn("Recent ingestion runs", body)
            self.assertIn("rejected", body)
            self.assertIn("landed", body)


if __name__ == "__main__":
    unittest.main()
