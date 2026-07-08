#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "error: $*" >&2
  exit 1
}

warn() {
  echo "warning: $*" >&2
}

load_env() {
  cd "$ROOT"
  # shellcheck disable=SC1091
  source "$ROOT/.envrc"
  [[ -n "${SPRINTCTL_DB:-}" ]] || fail "SPRINTCTL_DB is not set after sourcing .envrc"
  [[ -n "${KCTL_DB:-}" ]] || fail "KCTL_DB is not set after sourcing .envrc"
}

require_var() {
  local name="$1"
  [[ -n "${!name:-}" ]] || fail "$name is required"
}

python_bin() {
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    echo "$ROOT/.venv/bin/python"
    return
  fi
  command -v python3 || command -v python
}

node_bin() {
  if command -v node >/dev/null 2>&1; then
    command -v node
    return
  fi
  if [[ -x "$ROOT/.tooling/node-v20.20.1-linux-x64/bin/node" ]]; then
    echo "$ROOT/.tooling/node-v20.20.1-linux-x64/bin/node"
    return
  fi
  return 1
}

runtime_session_id() {
  if [[ -n "${SPRINTCTL_RUNTIME_SESSION_ID:-}" ]]; then
    printf '%s' "$SPRINTCTL_RUNTIME_SESSION_ID"
    return
  fi
  if [[ -n "${CODEX_THREAD_ID:-}" ]]; then
    printf '%s' "$CODEX_THREAD_ID"
  fi
}

truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

remote_offline_allowed() {
  truthy "${ALLOW_OFFLINE_SPRINTCTL:-0}"
}

sprintctl_url_host_port() {
  require_var SPRINTCTL_URL
  "$(python_bin)" - "$SPRINTCTL_URL" <<'PY'
from __future__ import annotations

import sys
from urllib.parse import urlparse

url = urlparse(sys.argv[1])
host = url.hostname
port = url.port
if not host:
    raise SystemExit("SPRINTCTL_URL does not include a host")
if port is None:
    port = 5432 if url.scheme.startswith("postgres") else 443
print(f"{host} {port}")
PY
}

tcp_check_sprintctl_url() {
  local host port
  read -r host port < <(sprintctl_url_host_port)
  if command -v nc >/dev/null 2>&1; then
    nc -z -w "${SPRINTCTL_TCP_TIMEOUT:-3}" "$host" "$port" >/dev/null 2>&1 \
      || fail "sprintctl remote TCP check failed for ${host}:${port}"
  else
    timeout "${SPRINTCTL_TCP_TIMEOUT:-3}" bash -c ":</dev/tcp/$host/$port" >/dev/null 2>&1 \
      || fail "sprintctl remote TCP check failed for ${host}:${port}"
  fi
  echo "sprintctl remote TCP ok: ${host}:${port}"
}

run_sprintctl_or_offline() {
  local description="$1"
  shift
  if ( "$@" ); then
    return 0
  fi
  if remote_offline_allowed; then
    warn "$description failed; ALLOW_OFFLINE_SPRINTCTL=1 set, continuing in deferred sprintctl closeout mode"
    return 0
  fi
  fail "$description failed"
}

extract_claim_field() {
  local field="$1"
  local payload
  payload="$(cat)"
  CLAIM_JSON="$payload" "$(python_bin)" - "$field" <<'PY'
from __future__ import annotations

import json
import os
import sys

field = sys.argv[1]
data = json.loads(os.environ["CLAIM_JSON"])

def find(obj: object, names: tuple[str, ...]) -> object | None:
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] not in (None, ""):
                return obj[name]
        for value in obj.values():
            found = find(value, names)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find(value, names)
            if found not in (None, ""):
                return found
    return None

names = {
    "claim_id": ("claim_id", "id"),
    "claim_token": ("claim_token", "token"),
}[field]
value = find(data, names)
if value is None:
    raise SystemExit(f"could not find {field} in sprintctl output")
print(value)
PY
}

agent_preflight() {
  load_env
  py="$(python_bin)"
  echo "python: $("$py" --version 2>&1)"
  command -v sprintctl >/dev/null 2>&1 || fail "sprintctl is not on PATH"
  node="$(node_bin)" || fail "node is not on PATH and repo-local node is missing"
  echo "node: $("$node" --version 2>&1)"
  "$py" - <<'PY'
from __future__ import annotations

import importlib

modules = [
    "botocore.retries",
    "duckdb",
    "mypy",
    "mypy_extensions",
    "pluggy",
    "pytest",
    "ruff",
]
missing = []
for module in modules:
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 - preflight should classify setup failures.
        missing.append(f"{module}: {exc}")
if missing:
    raise SystemExit("missing or broken Python verification imports:\n" + "\n".join(missing))
PY
  sprintctl --help >/dev/null
  if ! "$py" - <<'PY'
from __future__ import annotations

import importlib

for module in ("psycopg",):
    importlib.import_module(module)
PY
  then
    fail "sprintctl remote extras appear unavailable; reinstall with sprintctl[remote]"
  fi
  run_sprintctl_or_offline "sprintctl health" sprintctl_health
}

sprintctl_health() {
  load_env
  command -v sprintctl >/dev/null 2>&1 || fail "sprintctl is not on PATH"
  tcp_check_sprintctl_url
  if [[ -n "${ITEM:-}" ]]; then
    sprintctl item show --id "$ITEM" --json >/dev/null
    echo "sprintctl item ok: $ITEM"
  else
    sprintctl sprint list --json >/dev/null
    echo "sprintctl sprint list ok"
  fi
}

claim_start_preflight() {
  load_env
  require_var ITEM
  require_var ACTOR
  sprintctl_health
  mkdir -p "$ROOT/.sprintctl/claims"
  output="$(mktemp)"
  args=(claim start --item-id "$ITEM" --actor "$ACTOR" --json)
  if [[ -n "${CLAIM_TTL:-}" ]]; then
    args+=(--ttl "$CLAIM_TTL")
  fi
  if [[ -n "${SPRINTCTL_INSTANCE_ID:-}" ]]; then
    args+=(--instance-id "$SPRINTCTL_INSTANCE_ID")
  fi
  session_id="$(runtime_session_id)"
  if [[ -n "$session_id" ]]; then
    args+=(--runtime-session-id "$session_id")
  fi
  sprintctl "${args[@]}" | tee "$output"
  claim_id="$(extract_claim_field claim_id < "$output")"
  claim_token="$(extract_claim_field claim_token < "$output")"
  token_file="$ROOT/.sprintctl/claims/claim-${ITEM}.token"
  umask 077
  printf '%s\n' "$claim_token" > "$token_file"
  rm -f "$output"
  echo "claim token saved: $token_file" >&2
  echo "claim id: $claim_id" >&2
}

claim_close() {
  load_env
  require_var ITEM
  local claim="${CLAIM:-${CLAIM_ID:-}}"
  [[ -n "$claim" ]] || fail "CLAIM or CLAIM_ID is required"
  local token_file="${TOKEN_FILE:-$ROOT/.sprintctl/claims/claim-${ITEM}.token}"
  local token="${CLAIM_TOKEN:-}"
  if [[ -z "$token" ]]; then
    [[ -f "$token_file" ]] || fail "CLAIM_TOKEN is not set and TOKEN_FILE does not exist: $token_file"
    token="$(<"$token_file")"
  fi
  sprintctl_health
  sprintctl item done-from-claim \
    --id "$ITEM" \
    --claim-id "$claim" \
    --claim-token "$token" \
    --json
  rm -f "$token_file"
  echo "removed claim token file: $token_file" >&2
}

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
  fail "usage: tools/workflow.sh <agent-preflight|sprintctl-health|sprintctl-preflight|sprintctl-close|sprint-resume|claim-recover|claim-heartbeat|item-verify-auth|snapshot-refresh|knowledge-publish>"
fi
shift || true

case "$cmd" in
  agent-preflight)
    agent_preflight
    ;;
  sprintctl-health)
    sprintctl_health
    ;;
  sprintctl-preflight)
    claim_start_preflight
    ;;
  sprintctl-close)
    claim_close
    ;;
  sprint-resume)
    load_env
    args=(claim resume --json)
    if [[ -n "${ITEM:-}" ]]; then
      args+=(--item-id "$ITEM")
    fi
    if [[ -n "${SPRINTCTL_INSTANCE_ID:-}" ]]; then
      args+=(--instance-id "$SPRINTCTL_INSTANCE_ID")
    fi
    session_id="$(runtime_session_id)"
    if [[ -n "$session_id" ]]; then
      args+=(--runtime-session-id "$session_id")
    fi
    if [[ -z "${SPRINTCTL_INSTANCE_ID:-}" && -z "$session_id" ]]; then
      fail "set SPRINTCTL_INSTANCE_ID or SPRINTCTL_RUNTIME_SESSION_ID (or CODEX_THREAD_ID) before sprint-resume"
    fi
    sprintctl "${args[@]}"
    ;;
  claim-recover)
    load_env
    require_var ITEM
    sprintctl claim recover --item-id "$ITEM" --json
    ;;
  claim-heartbeat)
    load_env
    require_var CLAIM_ID
    require_var CLAIM_TOKEN
    args=(claim heartbeat --id "$CLAIM_ID" --claim-token "$CLAIM_TOKEN" --json)
    if [[ -n "${ACTOR:-}" ]]; then
      args+=(--actor "$ACTOR")
    fi
    if [[ -n "${CLAIM_TTL:-}" ]]; then
      args+=(--ttl "$CLAIM_TTL")
    fi
    if [[ -n "${SPRINTCTL_INSTANCE_ID:-}" ]]; then
      args+=(--instance-id "$SPRINTCTL_INSTANCE_ID")
    fi
    session_id="$(runtime_session_id)"
    if [[ -n "$session_id" ]]; then
      args+=(--runtime-session-id "$session_id")
    fi
    sprintctl "${args[@]}"
    ;;
  item-verify-auth)
    load_env
    require_var PY_FILES
    require_var TESTS
    py="$(python_bin)"
    read -r -a py_files <<< "${PY_FILES}"
    read -r -a tests <<< "${TESTS}"
    "$py" -m ruff check "${py_files[@]}"
    "$py" -m mypy "${py_files[@]}"
    "$py" -m pytest "${tests[@]}" -x --tb=short
    "$py" -m pytest tests/test_architecture_contract.py -x --tb=short
    ;;
  snapshot-refresh)
    load_env
    args=(render --output "$ROOT/docs/sprint-snapshots/sprint-current.txt")
    if [[ -n "${SPRINT_ID:-}" ]]; then
      args+=(--sprint-id "$SPRINT_ID")
    fi
    sprintctl "${args[@]}"
    ;;
  knowledge-publish)
    load_env
    require_var CANDIDATE
    require_var CATEGORY
    require_var BODY
    args=(publish --id "$CANDIDATE" --body "$BODY" --category "$CATEGORY")
    if [[ -n "${TITLE:-}" ]]; then
      args+=(--title "$TITLE")
    fi
    if [[ -n "${TAGS:-}" ]]; then
      args+=(--tags "$TAGS")
    fi
    if truthy "${COORDINATION:-0}"; then
      args+=(--coordination)
    fi
    kctl "${args[@]}"
    kctl render --output "$ROOT/docs/knowledge/knowledge-base.md"
    ;;
  *)
    fail "unknown command: $cmd"
    ;;
esac
