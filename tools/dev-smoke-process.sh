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

dev_process_identity() {
  local pid="$1" stat rest
  local -a fields=()
  [[ -e "/proc/$pid/stat" ]] || return 1
  [[ -r "/proc/$pid/stat" ]] || return 2
  IFS= read -r stat <"/proc/$pid/stat" || return 2
  rest="${stat##*) }"
  read -r -a fields <<< "$rest"
  [[ "${#fields[@]}" -ge 20 ]] || return 2
  printf '%s %s\n' "${fields[19]}" "${fields[0]}"
}

dev_capture_process_tree() {
  local root_pid="$1" snapshot pid parent state identity status changed
  local -A parents=() tree=()
  snapshot="$(ps -eo pid=,ppid=,stat=)" || return 2
  while read -r pid parent state; do
    [[ "$pid" =~ ^[0-9]+$ && "$parent" =~ ^[0-9]+$ ]] || continue
    parents["$pid"]="$parent"
  done <<< "$snapshot"

  identity="$(dev_process_identity "$root_pid")"
  status=$?
  if [[ "$status" == 0 ]]; then
    tree["$root_pid"]="${identity%% *}"
  elif [[ "$status" == 2 ]]; then
    return 2
  else
    return 0
  fi

  changed=1
  while [[ "$changed" == 1 ]]; do
    changed=0
    for pid in "${!parents[@]}"; do
      parent="${parents[$pid]}"
      [[ -n "${tree[$parent]+present}" && -z "${tree[$pid]+present}" ]] || continue
      identity="$(dev_process_identity "$pid")"
      status=$?
      if [[ "$status" == 0 ]]; then
        tree["$pid"]="${identity%% *}"
        changed=1
      elif [[ "$status" == 2 ]]; then
        return 2
      fi
    done
  done
  for pid in "${!tree[@]}"; do
    printf '%s %s\n' "$pid" "${tree[$pid]}"
  done
}

dev_owned_process_alive() {
  local pid="$1" expected_start="$2" identity start_time state
  identity="$(dev_process_identity "$pid")"
  case "$?" in
    0) ;;
    1) return 1 ;;
    *) return 2 ;;
  esac
  read -r start_time state <<< "$identity"
  [[ "$start_time" == "$expected_start" ]] || return 1
  case "$state" in
    Z*|X*) return 1 ;;
    *) return 0 ;;
  esac
}

dev_stop_unestablished_process() {
  local root_pid="$1" term_checks="$2" kill_checks="$3" interval="$4"
  local attempt snapshot pid start_time alive status signal_name checks
  local -A tracked=()
  for signal_name in TERM KILL; do
    if [[ "$signal_name" == TERM ]]; then
      checks="$term_checks"
    else
      checks="$kill_checks"
    fi
    for ((attempt = 0; attempt < checks; attempt++)); do
      snapshot="$(dev_capture_process_tree "$root_pid")"
      status=$?
      if [[ "$status" != 0 ]]; then
        printf 'dev smoke cleanup error: could not inspect startup process tree %s\n' "$root_pid" >&2
        return 1
      fi
      while read -r pid start_time; do
        [[ "$pid" =~ ^[0-9]+$ && "$start_time" =~ ^[0-9]+$ ]] \
          && tracked["$pid"]="$start_time"
      done <<< "$snapshot"

      # Signal descendants by PID while the launcher still lacks its own
      # process group. Never signal the caller's process group by accident.
      for pid in "${!tracked[@]}"; do
        [[ "$pid" == "$root_pid" ]] && continue
        if dev_owned_process_alive "$pid" "${tracked[$pid]}"; then
          kill -"$signal_name" "$pid" 2>/dev/null || true
        else
          status=$?
          if [[ "$status" == 2 ]]; then
            printf 'dev smoke cleanup error: could not inspect owned startup descendant %s\n' "$pid" >&2
            return 1
          fi
        fi
      done
      if dev_owned_process_alive "$root_pid" "${tracked[$root_pid]:-}"; then
        kill -"$signal_name" "$root_pid" 2>/dev/null || true
      else
        status=$?
        if [[ "$status" == 2 ]]; then
          printf 'dev smoke cleanup error: could not inspect startup process %s\n' "$root_pid" >&2
          return 1
        fi
      fi

      alive=0
      for pid in "${!tracked[@]}"; do
        if dev_owned_process_alive "$pid" "${tracked[$pid]}"; then
          alive=1
        else
          status=$?
          if [[ "$status" == 2 ]]; then
            printf 'dev smoke cleanup error: could not verify startup process %s\n' "$pid" >&2
            return 1
          fi
        fi
      done
      [[ "$alive" == 0 ]] && return 0
      sleep "$interval"
    done
  done
  printf 'dev smoke cleanup error: startup process tree %s did not settle after bounded SIGTERM/SIGKILL waits\n' "$root_pid" >&2
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
  local state identity pid_state expected_start process_group group_visible
  if dev_process_group_state "$pgid"; then
    group_visible=1
  else
    state=$?
    if [[ "$state" == 1 ]]; then
      identity="$(dev_process_identity "$pgid")"
      pid_state=$?
      if [[ "$pid_state" == 1 ]]; then
        return 0
      elif [[ "$pid_state" != 0 ]]; then
        printf 'dev smoke cleanup error: could not inspect process %s without a process group\n' "$pgid" >&2
        return 1
      fi
      expected_start="${identity%% *}"
      if dev_owned_process_alive "$pgid" "$expected_start"; then
        process_group="$(ps -o pgid= -p "$pgid" 2>/dev/null | tr -d '[:space:]')"
        if [[ -z "$process_group" ]]; then
          printf 'dev smoke cleanup error: could not inspect startup process group %s\n' "$pgid" >&2
          return 1
        fi
        if [[ "$process_group" != "$pgid" ]]; then
          dev_stop_unestablished_process "$pgid" "$term_checks" "$kill_checks" "$interval"
          return $?
        fi
        if dev_process_group_state "$pgid"; then
          group_visible=1
        else
          state=$?
          [[ "$state" == 1 ]] \
            && { printf 'dev smoke cleanup error: process group %s is not observable while its leader is alive\n' "$pgid" >&2; return 1; }
          printf 'dev smoke cleanup error: could not inspect process group %s\n' "$pgid" >&2
          return 1
        fi
      else
        pid_state=$?
        [[ "$pid_state" == 1 ]] && return 0
        printf 'dev smoke cleanup error: could not inspect process %s without a process group\n' "$pgid" >&2
        return 1
      fi
    elif [[ "$state" == 2 ]]; then
      printf 'dev smoke cleanup error: could not inspect process group %s\n' "$pgid" >&2
      return 1
    fi
  fi
  [[ "$group_visible" == 1 ]] || return 1
  kill -TERM -- "-$pgid" 2>/dev/null || true
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
