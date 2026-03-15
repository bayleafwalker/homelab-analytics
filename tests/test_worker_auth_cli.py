from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.worker.main import main
from packages.shared.auth import verify_password
from packages.shared.settings import AppSettings
from packages.storage.ingestion_config import IngestionConfigRepository


def _build_settings(temp_dir: str) -> AppSettings:
    return AppSettings(
        data_dir=Path(temp_dir),
        landing_root=Path(temp_dir) / "landing",
        metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
        account_transactions_inbox_dir=Path(temp_dir) / "inbox" / "account-transactions",
        processed_files_dir=Path(temp_dir) / "processed" / "account-transactions",
        failed_files_dir=Path(temp_dir) / "failed" / "account-transactions",
        api_host="127.0.0.1",
        api_port=8080,
        web_host="127.0.0.1",
        web_port=8081,
        worker_poll_interval_seconds=30,
    )


def test_worker_cli_manages_local_admin_users() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = main(
            ["create-local-admin-user", "admin", "admin-password"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["user"]["role"] == "admin"

        stdout = io.StringIO()
        exit_code = main(
            ["list-local-users"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["users"][0]["username"] == "admin"

        repository = IngestionConfigRepository(settings.resolved_config_database_path)
        initial_hash = repository.get_local_user_by_username("admin").password_hash

        stdout = io.StringIO()
        exit_code = main(
            ["reset-local-user-password", "admin", "rotated-password"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0

        rotated_user = repository.get_local_user_by_username("admin")
        assert rotated_user.password_hash != initial_hash
        assert verify_password("rotated-password", rotated_user.password_hash)


def test_worker_cli_bootstraps_local_admin_from_settings() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        settings = AppSettings(
            **{
                **settings.__dict__,
                "auth_mode": "local",
                "bootstrap_admin_username": "bootstrap-admin",
                "bootstrap_admin_password": "bootstrap-password",
            }
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = main(
            ["list-local-users"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["users"][0]["username"] == "bootstrap-admin"


def test_worker_cli_manages_service_tokens() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = main(
            [
                "create-service-token",
                "home-assistant",
                "--role",
                "operator",
                "--scope",
                "reports:read",
                "--scope",
                "ingest:write",
            ],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        created = json.loads(stdout.getvalue())
        assert created["service_token"]["token_name"] == "home-assistant"
        assert created["token_value"].startswith("hst_")
        token_id = created["service_token"]["token_id"]

        stdout = io.StringIO()
        exit_code = main(
            ["list-service-tokens", "--include-revoked"],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["service_tokens"][0]["token_id"] == token_id

        stdout = io.StringIO()
        exit_code = main(
            ["revoke-service-token", token_id],
            stdout=stdout,
            stderr=stderr,
            settings=settings,
        )
        assert exit_code == 0
        assert json.loads(stdout.getvalue())["service_token"]["revoked"] is True
