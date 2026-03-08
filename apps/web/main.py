from __future__ import annotations

from wsgiref.simple_server import make_server

from apps.web.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.settings import AppSettings
from packages.storage.run_metadata import RunMetadataRepository


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=RunMetadataRepository(settings.metadata_database_path),
    )


def build_app(settings: AppSettings | None = None):
    resolved_settings = settings or AppSettings.from_env()
    return create_app(build_service(resolved_settings))


def main() -> int:
    settings = AppSettings.from_env()
    app = build_app(settings)
    with make_server(settings.web_host, settings.web_port, app) as server:
        print(
            f"Serving homelab-analytics web on http://{settings.web_host}:{settings.web_port}"
        )
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
