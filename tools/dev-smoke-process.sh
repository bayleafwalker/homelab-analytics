#!/usr/bin/env bash
# Process settlement and isolated environment shared by the smoke entrypoint
# and its real-child tests.

dev_process_group_state() {
  local pgid="$1" snapshot member_pgid member_state
  snapshot="$(ps -eo pgid=,stat=)" || return 2
  while read -r member_pgid member_state; do
    [[ "$member_pgid" == "$pgid" ]] || continue
    case "$member_state" in
      Z*|X*) ;;
      *) return 0 ;;
    esac
  done <<< "$snapshot"
  return 1
}

dev_wait_process_group_settled() {
  local pgid="$1" checks="$2" interval="$3" attempt state
  for ((attempt = 0; attempt < checks; attempt++)); do
    if dev_process_group_state "$pgid"; then
      sleep "$interval"
    else
      state=$?
      [[ "$state" == 1 ]] && return 0
      return 1
    fi
  done
  dev_process_group_state "$pgid"
  state=$?
  [[ "$state" == 1 ]]
}

dev_stop_process_group() {
  local pgid="$1" term_checks="${2:-30}" kill_checks="${3:-30}" interval="${4:-0.1}"
  local state
  if dev_process_group_state "$pgid"; then
    kill -TERM -- "-$pgid" 2>/dev/null || true
  else
    state=$?
    [[ "$state" == 1 ]] && return 0
    printf 'dev smoke cleanup error: could not inspect process group %s\n' "$pgid" >&2
    return 1
  fi
  if dev_wait_process_group_settled "$pgid" "$term_checks" "$interval"; then
    return 0
  fi

  if dev_process_group_state "$pgid"; then
    kill -KILL -- "-$pgid" 2>/dev/null || true
  else
    state=$?
    [[ "$state" == 1 ]] && return 0
    printf 'dev smoke cleanup error: could not inspect process group %s after SIGTERM\n' "$pgid" >&2
    return 1
  fi
  if dev_wait_process_group_settled "$pgid" "$kill_checks" "$interval"; then
    return 0
  fi

  printf 'dev smoke cleanup error: process group %s did not settle after bounded SIGTERM/SIGKILL waits\n' "$pgid" >&2
  return 1
}

dev_smoke_env() {
  local home="$1" tmpdir="$2" api_base_url="$3"
  shift 3
  env -i \
    "HOME=$home" \
    "PATH=$PATH" \
    "TMPDIR=$tmpdir" \
    "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}" \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    "HOMELAB_ANALYTICS_API_BASE_URL=$api_base_url" \
    HOMELAB_ANALYTICS_IDENTITY_MODE=disabled \
    "$@"
}

dev_smoke_launch() {
  local root="$1" home="$2" tmpdir="$3" api_base_url="$4"
  shift 4
  exec setsid bash -c '
    root="$1"; home="$2"; tmpdir="$3"; api_base_url="$4"
    shift 4
    source "$root/tools/dev-smoke-process.sh"
    dev_smoke_env "$home" "$tmpdir" "$api_base_url" "$@"
  ' _ "$root" "$home" "$tmpdir" "$api_base_url" "$@"
}

dev_smoke_cleanup() {
  local status=$? cleanup_failed=0 pgid
  trap - EXIT INT TERM
  for pgid in "${build_pid:-}" "${server_pid:-}" "${backend_pid:-}"; do
    [[ -n "$pgid" ]] || continue
    if dev_stop_process_group "$pgid"; then
      wait "$pgid" 2>/dev/null || true
    else
      cleanup_failed=1
    fi
  done
  [[ -z "${LOG:-}" ]] || rm -f "$LOG"
  [[ -z "${BACKEND_LOG:-}" ]] || rm -f "$BACKEND_LOG"
  [[ -z "${BUILD_LOG:-}" ]] || rm -f "$BUILD_LOG"
  [[ -z "${BACKEND_ENDPOINT_FILE:-}" ]] || rm -f "$BACKEND_ENDPOINT_FILE"
  if [[ "$cleanup_failed" == 1 ]]; then
    status=1
  fi
  exit "$status"
}

dev_smoke_install_traps() {
  trap dev_smoke_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
}
