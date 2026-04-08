#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "error: $*" >&2
  exit 1
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

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
  fail "usage: tools/workflow.sh <sprint-resume|claim-recover|claim-heartbeat|item-verify-auth|snapshot-refresh|knowledge-publish>"
fi
shift || true

case "$cmd" in
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
