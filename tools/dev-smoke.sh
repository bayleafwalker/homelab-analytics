#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=tools/dev-env.sh
source "$ROOT/tools/dev-env.sh"
dev_prepare_env "$ROOT"
dev_require_python_env "$ROOT"
[[ -x "$ROOT/apps/web/frontend/node_modules/.bin/next" ]] \
  || dev_fail "frontend dependencies are missing; run 'make dev-setup'"
command -v setsid >/dev/null 2>&1 || dev_fail "setsid is required to clean up the smoke server and its Node child"

cd "$ROOT"
PORT="$(.venv/bin/python - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
BASE_URL="http://127.0.0.1:$PORT"
LOG="$(mktemp)"
server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill -- "-$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -f "$LOG"
}
trap cleanup EXIT

printf 'Building existing standalone web target...\n'
npm --prefix apps/web/frontend run build
standalone="apps/web/frontend/.next/standalone"
[[ -f "$standalone/server.js" ]] || dev_fail "Next.js build did not create the standalone server"
mkdir -p "$standalone/.next"
rm -rf "$standalone/.next/static" "$standalone/public"
cp -R apps/web/frontend/.next/static "$standalone/.next/static"
cp -R apps/web/frontend/public "$standalone/public"

setsid env \
  HOMELAB_ANALYTICS_WEB_HOST=127.0.0.1 \
  HOMELAB_ANALYTICS_WEB_PORT="$PORT" \
  .venv/bin/python -m apps.web.main >"$LOG" 2>&1 &
server_pid=$!
ready=0
for attempt in $(seq 1 60); do
  if .venv/bin/python - "$BASE_URL" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=1) as response:
    response.read(1)
PY
  then
    ready=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    cat "$LOG" >&2
    dev_fail "web server exited before becoming ready"
  fi
  sleep 0.5
done
[[ "$ready" == 1 ]] || { cat "$LOG" >&2; dev_fail "web server did not become ready at $BASE_URL"; }

.venv/bin/python - "$BASE_URL" <<'PY'
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import urlopen

base = sys.argv[1]
with urlopen(base, timeout=5) as response:
    html = response.read().decode("utf-8")
    if response.status != 200:
        raise SystemExit(f"page returned HTTP {response.status}")

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for key in ("src", "href"):
            value = values.get(key, "")
            if value.startswith("/_next/static/"):
                self.urls.append(value)

assets = Assets()
assets.feed(html)
if not assets.urls:
    raise SystemExit("rendered page did not reference a Next.js static asset")
asset_url = urljoin(base, assets.urls[0])
with urlopen(asset_url, timeout=5) as response:
    body = response.read()
    if response.status != 200 or not body:
        raise SystemExit(f"static asset failed: {asset_url} returned HTTP {response.status}")
print(f"Standalone web smoke passed: page and {assets.urls[0]} returned HTTP 200")
PY
