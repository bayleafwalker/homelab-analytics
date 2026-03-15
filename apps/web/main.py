from __future__ import annotations

import logging
import subprocess

from apps.web.app import build_web_command, build_web_environment, frontend_root
from packages.shared.logging import configure_logging
from packages.shared.settings import AppSettings


def build_runtime(settings: AppSettings) -> tuple[list[str], str, dict[str, str]]:
    return (
        build_web_command(settings),
        str(frontend_root()),
        build_web_environment(settings),
    )


def main() -> int:
    settings = AppSettings.from_env()
    configure_logging()
    logger = logging.getLogger("homelab_analytics.web")
    command, working_directory, environment = build_runtime(settings)
    logger.info(
        "web server starting",
        extra={
            "host": settings.web_host,
            "port": settings.web_port,
            "api_base_url": settings.resolved_api_base_url,
        },
    )
    completed = subprocess.run(
        command,
        cwd=working_directory,
        env=environment,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
