"""Recapture docs/product/screenshots/finance-loop/ from a throwaway demo instance.

Reproduces the walkthrough's section 0 in a temporary data directory, so your
own .local data is never touched:

1. ``seed-demo-data`` from infra/examples/demo-data and a local admin user;
2. the API and the web workload (``python -m apps.web.main``) on free-standing
   ports, identity mode ``local``;
3. two upload files derived from the seeded OP personal-account export: a
   new period (the first two January rows moved to 2026, so the upload lands
   instead of being refused as a duplicate) and one of those rows with its
   amount left empty (the run lands as ``rejected`` with a
   ``missing_required_value`` issue; dropping the column instead is refused
   before any run is recorded);
4. scripts/capture_finance_loop_screenshots.mjs (Playwright, Chromium,
   1440x1000), which signs in, walks the loop and writes the eight images.

Prerequisites: ``uv sync --extra dev``; ``make web-local`` (a Next.js standalone
build with its static assets copied beside server.js, or pass ``--build``);
``npm --prefix apps/web/frontend ci`` and, once,
``npx --prefix apps/web/frontend playwright install chromium``.

Run from the repo root:

    python scripts/capture_finance_loop_screenshots.py
    python scripts/capture_finance_loop_screenshots.py --out-dir /tmp/finance-loop

The images are walkthrough reference images, not visual-test baselines; this
never touches apps/web/frontend/playwright/*-snapshots/.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "apps" / "web" / "frontend"
STANDALONE = FRONTEND / ".next" / "standalone"
DEMO_DATA = REPO_ROOT / "infra" / "examples" / "demo-data"
OP_EXPORT = DEMO_DATA / "sources" / "personal account" / "tapahtumat20250101-20251231.csv"
CAPTURE_JS = REPO_ROOT / "scripts" / "capture_finance_loop_screenshots.mjs"
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "product" / "screenshots" / "finance-loop"
ADMIN_USERNAME = "demo-admin"
ADMIN_PASSWORD = "finance-loop-capture-pass"  # throwaway instance only
AMOUNT_COLUMN = "Määrä EUROA"


def write_upload_files(directory: Path) -> tuple[Path, Path]:
    """A new-period CSV and a one-row CSV with an empty amount (OP layout)."""
    lines = OP_EXPORT.read_text(encoding="utf-8").splitlines()
    header, rows = lines[0], [line for line in lines[1:] if line.startswith('"2025-01-')]
    moved = [
        row.replace('"2025-01-', '"2026-01-').replace('"202501', '"202601') for row in rows[:2]
    ]
    good = directory / "tapahtumat20260101-20260131.csv"
    good.write_text("\n".join([header, *moved]) + "\n", encoding="utf-8")

    amount = header.split(";").index(f'"{AMOUNT_COLUMN}"')
    fields = moved[0].split(";")
    fields[amount] = '""'
    bad = directory / "op-personal-broken.csv"
    bad.write_text("\n".join([header, ";".join(fields)]) + "\n", encoding="utf-8")
    return good, bad


def ensure_web_build(*, build: bool) -> None:
    ready = (STANDALONE / "server.js").is_file() and (STANDALONE / ".next" / "static").is_dir()
    if ready and not build:
        return
    if not build:
        raise SystemExit(
            "No standalone web build with static assets. Run `make web-local` first, "
            "or pass --build."
        )
    subprocess.run(["npm", "--prefix", str(FRONTEND), "run", "build"], check=True)
    for target in (STANDALONE / ".next" / "static", STANDALONE / "public"):
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(FRONTEND / ".next" / "static", STANDALONE / ".next" / "static")
    shutil.copytree(FRONTEND / "public", STANDALONE / "public")


def wait_for(url: str, *, timeout: float, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"{process.args!r} exited with {process.returncode} before {url} answered.")
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except urllib.error.HTTPError:
            return  # it answered; a 3xx/4xx still means it is up
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise SystemExit(f"Timed out waiting for {url}.")


def _stop_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except ProcessLookupError:
        return
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--api-port", type=int, default=18080)
    parser.add_argument("--web-port", type=int, default=18081)
    parser.add_argument("--build", action="store_true", help="rebuild the web frontend first")
    parser.add_argument("--keep-data", action="store_true", help="keep the temporary data dir")
    args = parser.parse_args(argv)

    ensure_web_build(build=args.build)
    data_dir = Path(tempfile.mkdtemp(prefix="finance-loop-capture-"))
    env = {
        **os.environ,
        "HOMELAB_ANALYTICS_DATA_DIR": str(data_dir / "data"),
        "HOMELAB_ANALYTICS_IDENTITY_MODE": "local",
        "HOMELAB_ANALYTICS_SESSION_SECRET": "finance-loop-capture-session-secret",
        "HOMELAB_ANALYTICS_API_HOST": "127.0.0.1",
        "HOMELAB_ANALYTICS_API_PORT": str(args.api_port),
        "HOMELAB_ANALYTICS_WEB_HOST": "127.0.0.1",
        "HOMELAB_ANALYTICS_WEB_PORT": str(args.web_port),
        "HOMELAB_ANALYTICS_API_BASE_URL": f"http://127.0.0.1:{args.api_port}",
    }
    # A developer shell may point these at real stores; the capture never should.
    for key in (
        "HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND",
        "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN",
        "HOMELAB_ANALYTICS_POSTGRES_DSN",
        "HOMELAB_ANALYTICS_REPORTING_BACKEND",
        "HOMELAB_ANALYTICS_BLOB_BACKEND",
    ):
        env.pop(key, None)
    python = sys.executable
    processes: list[subprocess.Popen[bytes]] = []
    try:
        subprocess.run(
            [python, "-m", "apps.worker.main", "seed-demo-data", "--input-dir", str(DEMO_DATA)],
            cwd=REPO_ROOT, env=env, check=True, stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [python, "-m", "apps.worker.main", "create-local-admin-user", ADMIN_USERNAME, ADMIN_PASSWORD],
            cwd=REPO_ROOT, env=env, check=True, stdout=subprocess.DEVNULL,
        )
        good, bad = write_upload_files(data_dir)

        # Own process groups: apps.web.main runs `node server.js` as a child,
        # and the whole group is stopped on the way out.
        api = subprocess.Popen(
            [python, "-m", "apps.api.main"], cwd=REPO_ROOT, env=env, start_new_session=True
        )
        processes.append(api)
        wait_for(f"http://127.0.0.1:{args.api_port}/health", timeout=60, process=api)
        web = subprocess.Popen(
            [python, "-m", "apps.web.main"], cwd=REPO_ROOT, env=env, start_new_session=True
        )
        processes.append(web)
        wait_for(f"http://127.0.0.1:{args.web_port}/login", timeout=60, process=web)

        capture_env = {
            **env,
            "FINANCE_LOOP_BASE_URL": f"http://localhost:{args.web_port}",
            "FINANCE_LOOP_USERNAME": ADMIN_USERNAME,
            "FINANCE_LOOP_PASSWORD": ADMIN_PASSWORD,
            "FINANCE_LOOP_GOOD_CSV": str(good),
            "FINANCE_LOOP_BAD_CSV": str(bad),
            "FINANCE_LOOP_OUT_DIR": str(args.out_dir.resolve()),
        }
        return subprocess.run(["node", str(CAPTURE_JS)], cwd=REPO_ROOT, env=capture_env).returncode
    finally:
        for process in reversed(processes):
            _stop_group(process)
        if args.keep_data:
            print(f"Kept demo data in {data_dir}")
        else:
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
