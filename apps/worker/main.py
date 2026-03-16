from __future__ import annotations

import logging
import sys
from typing import TextIO

from apps.worker.command_handlers import dispatch_worker_command
from apps.worker.command_parser import build_parser as _build_parser
from apps.worker.control_plane import _watch_schedule_dispatches
from apps.worker.runtime import (
    build_extension_registry,
    build_service,
    build_worker_runtime,
)
from packages.shared.logging import configure_logging
from packages.shared.settings import AppSettings

__all__ = [
    "_watch_schedule_dispatches",
    "build_extension_registry",
    "build_service",
    "main",
]


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    settings: AppSettings | None = None,
) -> int:
    configure_logging()
    logger = logging.getLogger("homelab_analytics.worker")
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    resolved_settings = settings or AppSettings.from_env()
    parser = _build_parser()
    args = parser.parse_args(argv)
    logger.info("worker command starting", extra={"command": args.command})
    runtime = build_worker_runtime(
        settings=resolved_settings,
        output=output,
        error_output=error_output,
        logger=logger,
    )

    try:
        exit_code = dispatch_worker_command(args, runtime)
        if exit_code is not None:
            return exit_code
    except (FileNotFoundError, KeyError, ValueError) as exc:
        error_output.write(f"{exc}\n")
        return 1

    error_output.write("Unknown command\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
