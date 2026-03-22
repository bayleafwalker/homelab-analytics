from __future__ import annotations

import os
from pathlib import Path

from packages.shared.settings import AppSettings


def frontend_root() -> Path:
    return Path(__file__).resolve().parent / "frontend"


def standalone_root() -> Path:
    return frontend_root() / ".next" / "standalone"


def standalone_entrypoint() -> Path:
    return standalone_root() / "server.js"


def build_web_environment(
    settings: AppSettings,
    *,
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    environment = dict(environ or os.environ)
    environment["HOSTNAME"] = settings.web_host
    environment["PORT"] = str(settings.web_port)
    environment["HOMELAB_ANALYTICS_API_BASE_URL"] = settings.resolved_api_base_url
    environment["HOMELAB_ANALYTICS_AUTH_MODE"] = settings.resolved_auth_mode
    environment["HOMELAB_ANALYTICS_IDENTITY_MODE"] = settings.resolved_identity_mode
    environment.setdefault("NODE_ENV", "production")
    return environment


def build_web_command(settings: AppSettings) -> list[str]:
    entrypoint = standalone_entrypoint()
    if not entrypoint.is_file():
        raise FileNotFoundError(
            "Next.js web build not found. Build apps/web/frontend before starting the web workload."
        )
    return ["node", str(entrypoint)]
