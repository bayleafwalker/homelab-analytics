"""``upgrade-reporting``: supported upgrade to currency-separated reporting.

Runs on settings alone, before the worker runtime is built, so it needs no
control plane, run-metadata store or extension registry. Exit codes: 0 complete
(or ``--check`` found nothing refused), 1 failed part-way (re-run), 2 refused
before any change.
"""
from __future__ import annotations

from argparse import Namespace
from typing import TextIO

from apps.worker.serialization import _write_json
from packages.pipelines.reporting_upgrade import run_upgrade
from packages.shared.settings import AppSettings


def handle_upgrade_reporting(
    args: Namespace, settings: AppSettings, output: TextIO, error_output: TextIO
) -> int:
    code, receipt = run_upgrade(settings, check_only=bool(args.check))
    _write_json(output, receipt)
    if code != 0:
        detail = receipt.get("error") or "; ".join(receipt.get("refusals") or [])
        error_output.write(f"upgrade-reporting {receipt['status']}: {detail}\n")
        if receipt.get("next_step"):
            error_output.write(f"{receipt['next_step']}\n")
    return code
