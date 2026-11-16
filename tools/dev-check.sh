#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=tools/dev-env.sh
source "$ROOT/tools/dev-env.sh"
dev_prepare_env "$ROOT"
dev_require_python_env "$ROOT"
[[ -x "$ROOT/apps/web/frontend/node_modules/.bin/tsc" ]] \
  || dev_fail "frontend dependencies are missing; run 'make dev-setup'"
ESBUILD="$ROOT/apps/web/frontend/node_modules/@esbuild/linux-x64/bin/esbuild"
[[ -x "$ESBUILD" ]] && "$ESBUILD" --version >/dev/null 2>&1 \
  || dev_fail "frontend esbuild native executable is missing or unusable; run 'make dev-setup' and check platform package availability"

cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
printf 'Running the existing Python checks (ruff and not-slow pytest)...\n'
"$PYTHON" -m ruff check .
"$PYTHON" -m pytest -q -m 'not slow'
printf 'Running focused frontend token, transport, and type checks...\n'
npm --prefix apps/web/frontend run tokens:check
npm --prefix apps/web/frontend run contracts:check
npm --prefix apps/web/frontend run typecheck
