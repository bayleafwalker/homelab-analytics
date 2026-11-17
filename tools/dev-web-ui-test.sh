#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/tools/dev-env.sh"
source "$ROOT/tools/dev-check-runtime.sh"
source "$ROOT/tools/dev-browser.sh"

dev_prepare_env "$ROOT"
dev_require_owned_path "$ROOT" "apps/web/frontend/node_modules" "frontend dependencies"
dev_prepare_browser_env "$ROOT"

NODE="$ROOT/.tooling/node-v20.20.1-linux-x64/bin/node"
"$NODE" "$ROOT/tools/dev-playwright-preflight.cjs" \
  "$ROOT/apps/web/frontend/node_modules/playwright"
npm --prefix "$ROOT/apps/web/frontend" run ui:test
