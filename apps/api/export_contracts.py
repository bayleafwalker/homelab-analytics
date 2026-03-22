from __future__ import annotations

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.api.main import build_app
from apps.api.support import to_jsonable
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.platform.publication_contracts import build_publication_contract_catalog
from packages.shared.settings import AppSettings

DEFAULT_GENERATED_DIR = Path("apps/web/frontend/generated")


def export_contracts(output_dir: Path = DEFAULT_GENERATED_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="homelab-analytics-contracts-") as temp_dir:
        temp_path = Path(temp_dir)
        settings = AppSettings(
            data_dir=temp_path,
            landing_root=temp_path / "landing",
            metadata_database_path=temp_path / "metadata" / "runs.db",
            account_transactions_inbox_dir=temp_path / "inbox",
            processed_files_dir=temp_path / "processed",
            failed_files_dir=temp_path / "failed",
            api_host="127.0.0.1",
            api_port=8080,
            web_host="127.0.0.1",
            web_port=8081,
            worker_poll_interval_seconds=60,
            auth_mode="disabled",
            enable_unsafe_admin=True,
        )
        app = build_app(settings)

        openapi_path = output_dir / "openapi.json"
        publication_contracts_path = output_dir / "publication-contracts.json"

        openapi_payload = app.openapi()
        openapi_path.write_text(
            json.dumps(openapi_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        publication_catalog = build_publication_contract_catalog(
            (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK)
        )
        publication_contracts_path.write_text(
            json.dumps(publication_catalog, indent=2, sort_keys=True, default=to_jsonable)
            + "\n",
            encoding="utf-8",
        )


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    export_contracts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
