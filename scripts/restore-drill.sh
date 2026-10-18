#!/usr/bin/env bash
# Restore drill for worker backup bundles (docs/runbooks/backup-and-restore.md#restore-drill).
#
# Restores the newest scheduled bundle (or --bundle DIR) into a scratch
# directory, checks it, records restore-drill-status.json next to the bundles,
# and prints a one-line summary. Never touches the live stores.
#
# Usage (inside the worker container, or any host with the same release):
#   scripts/restore-drill.sh [--backup-dir DIR] [--bundle DIR] [--scratch-dir DIR] [--keep-scratch]
set -euo pipefail

worker=(homelab-analytics-worker)
if ! command -v homelab-analytics-worker >/dev/null 2>&1; then
  worker=("${PYTHON:-python}" -m apps.worker.main)
fi

receipt="$(mktemp)"
trap 'rm -f "$receipt"' EXIT

status=0
"${worker[@]}" restore-drill "$@" >"$receipt" || status=$?

"${PYTHON:-python}" - "$receipt" <<'PY'
import json
import sys

text = open(sys.argv[1]).read()
start = text.find('{"restore_drill"')
if start < 0:
    print("restore drill: no receipt produced")
    sys.exit(0)
receipt = json.JSONDecoder().raw_decode(text[start:])[0]["restore_drill"]
tables = receipt.get("warehouse_tables", {})
print(
    "restore drill: {verdict} bundle={bundle} tables={tables} rows={rows} "
    "landing_files={landing} duration={duration}s".format(
        verdict="PASSED" if receipt["passed"] else "FAILED",
        bundle=receipt.get("bundle"),
        tables=len(tables),
        rows=sum(tables.values()),
        landing=receipt.get("landing_files"),
        duration=receipt.get("duration_seconds"),
    )
)
for error in receipt.get("errors", []):
    print(f"  error: {error}")
PY

exit "$status"
